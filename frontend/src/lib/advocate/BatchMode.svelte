<script lang="ts">
	/**
	 * Advocate mode, attorney edition: a folder of affidavits in, agencies ranked out.
	 * Build prompt §6.
	 *
	 * The browser drives it. Files are read three at a time through the same `/api/extract`
	 * the defendant flow uses, each read becomes one row per affidavit, a person confirms
	 * every row (in one press for the rows the reader was sure of), and only confirmed
	 * affidavits are sent for the comparison. Nothing is kept anywhere but this tab
	 * (bible §16), which is why the queue asks for the tab to stay open.
	 */
	import { api, ApiError, type Affidavit, type BatchReport, type Health } from '$lib/api/client';
	import { advocate, upload } from '$copy/en';
	import AffidavitReview from '$lib/check/AffidavitReview.svelte';
	import { buildAffidavit, type Geocoder } from '$lib/check/affidavit';
	import Button from '$lib/ui/Button.svelte';
	import Callout from '$lib/ui/Callout.svelte';
	import CheckBox from '$lib/ui/CheckBox.svelte';
	import DemoNote from '$lib/ui/DemoNote.svelte';
	import FileDrop from '$lib/ui/FileDrop.svelte';
	import BatchQueue from './BatchQueue.svelte';
	import BatchReportView from './BatchReportView.svelte';
	import {
		CONCURRENCY,
		MAX_FILES,
		MAX_PAGES,
		admit,
		draftOf,
		fromExtraction,
		manual,
		pool,
		queued,
		tally,
		withRetry,
		type QueueItem
	} from './batch';
	import { loadSampleBatch } from './sampleBatch';

	let { onsample }: { onsample?: (on: boolean) => void } = $props();

	const words = advocate.batch;

	let items = $state<QueueItem[]>([]);
	/** The confirmed affidavit for each confirmed row, as it will be sent. */
	let built = $state<Record<string, Affidavit>>({});
	let openId = $state<string | null>(null);
	let pagesRead = 0;
	let refused = $state(0);
	let confirming = $state(false);
	let analysing = $state(false);
	let failure = $state<string | null>(null);
	let report = $state.raw<BatchReport | null>(null);
	let sample = $state(false);

	/** The same gate as the defendant upload: real papers only where the deployment allows. */
	let health = $state<Health | null>(null);
	let acknowledged = $state(false);
	const realAllowed = $derived(health?.llm_real_data_allowed === true);
	$effect(() => {
		void api
			.health()
			.then((h) => (health = h))
			.catch(() => (health = null));
	});

	const counts = $derived(tally(items));
	const openItem = $derived(items.find((item) => item.id === openId) ?? null);
	const nConfirmed = $derived(items.filter((i) => i.status === 'confirmed' && built[i.id]).length);

	function describe(error: unknown): string {
		return error instanceof ApiError ? error.message : upload.readFailed;
	}

	function patch(id: string, change: Partial<QueueItem>) {
		const at = items.findIndex((item) => item.id === id);
		if (at >= 0) items[at] = { ...items[at]!, ...change };
	}

	function replace(id: string, rows: QueueItem[]) {
		items = items.flatMap((item) => (item.id === id ? rows : [item]));
	}

	/** One file through the reader, once retried on a rate limit or an outage. */
	async function readOne(id: string) {
		const item = items.find((i) => i.id === id);
		if (!item?.file) return;
		if (pagesRead >= MAX_PAGES) {
			patch(id, { status: 'failed', fail: 'page_cap' });
			return;
		}
		patch(id, { status: 'reading', fail: null, message: null });
		try {
			const file = item.file;
			const extraction = await withRetry(() => api.extract(file));
			pagesRead += extraction.n_pages;
			const current = items.find((i) => i.id === id);
			if (current) replace(id, fromExtraction(current, extraction));
		} catch (error) {
			patch(id, { status: 'failed', fail: 'read', message: describe(error) });
		}
	}

	async function add(files: File[]) {
		failure = null;
		if (sample) startOver();
		const { accepted, refused: over } = admit(items.length, files);
		refused = over;
		const fresh = accepted.map(queued);
		items = [...items, ...fresh];
		await pool(
			fresh.map((item) => item.id),
			CONCURRENCY,
			readOne
		);
	}

	async function useSample() {
		failure = null;
		startOver();
		try {
			const files = await loadSampleBatch();
			items = files.flatMap(({ name, extraction }) =>
				fromExtraction({ ...queued(new File([], name)), file: null }, extraction)
			);
			sample = true;
			onsample?.(true);
		} catch {
			failure = 'The sample batch could not be loaded.';
		}
	}

	function retry(id: string) {
		void pool([id], 1, readOne);
	}

	function typeIn(id: string) {
		const item = items.find((i) => i.id === id);
		if (!item) return;
		patch(id, manual(item));
		openId = id;
	}

	/** Lookups only for addresses the person changed; the reader already placed the rest. */
	const geocode: Geocoder = async (address) =>
		(await withRetry(() => api.geocode(address))).result?.location ?? null;

	async function confirm(id: string): Promise<boolean> {
		const item = items.find((i) => i.id === id);
		if (!item) return false;
		try {
			const affidavit = await buildAffidavit({
				values: item.values,
				attempts: item.attempts,
				draft: draftOf(item),
				sourceSha256: item.extraction?.source_sha256,
				geocode
			});
			built[id] = affidavit;
			patch(id, { status: 'confirmed', message: null });
			return true;
		} catch (error) {
			delete built[id];
			patch(id, { status: 'review', message: describe(error) });
			return false;
		}
	}

	function unconfirm(id: string) {
		delete built[id];
		patch(id, { status: 'review' });
	}

	async function confirmClean() {
		confirming = true;
		const ready = items.filter((i) => i.status === 'ok').map((i) => i.id);
		await pool(ready, CONCURRENCY, async (id) => void (await confirm(id)));
		confirming = false;
	}

	async function analyse() {
		analysing = true;
		failure = null;
		try {
			const confirmed = items
				.filter((i) => i.status === 'confirmed')
				.map((i) => built[i.id])
				.filter((a): a is Affidavit => Boolean(a));
			report = await api.advocate.batch(confirmed, sample);
			openId = null;
		} catch (error) {
			failure = describe(error);
		} finally {
			analysing = false;
		}
	}

	function startOver() {
		items = [];
		built = {};
		openId = null;
		pagesRead = 0;
		refused = 0;
		report = null;
		sample = false;
		onsample?.(false);
	}
</script>

{#snippet detail(row: QueueItem)}
	{@const id = row.id}
	<!-- Pinned to the left edge of the table's scroller and no wider than the screen, so the
	     review reads without scrolling sideways even when the queue table itself does. -->
	<div
		class="sticky left-0 max-w-[min(64rem,calc(100vw-4rem))]"
		role="region"
		aria-label={words.review}
	>
		{#if openItem?.message}
			<div class="mb-4"><Callout tone="caution">{openItem.message}</Callout></div>
		{/if}
		{#if openItem}
			{#key id}
				<AffidavitReview
					extraction={openItem.extraction}
					selected={openItem.index}
					voice="advocate"
					bind:values={openItem.values}
					bind:attempts={openItem.attempts}
					bind:resolved={openItem.resolved}
					bind:confirmed={
						() => openItem?.status === 'confirmed',
						(value) => {
							if (!value && openItem?.status === 'confirmed') unconfirm(id);
						}
					}
					onconfirm={() => void confirm(id)}
				/>
			{/key}
		{/if}
	</div>
{/snippet}

{#if report}
	<BatchReportView
		{report}
		unconfirmed={counts.ok + counts.review}
		failed={counts.failed}
		onback={() => (report = null)}
	/>
{:else}
	<div class="space-y-6">
		{#if failure}
			<Callout tone="contradicted" title="That did not work">{failure}</Callout>
		{/if}

		{#if !realAllowed}
			<Callout tone="caution" title={upload.realDataBlocked}>
				<div class="mt-3">
					<CheckBox id="batch-real-data-ack" bind:checked={acknowledged} label={upload.realDataAck} />
				</div>
			</Callout>
		{/if}

		{#if realAllowed || acknowledged}
			<FileDrop
				accept=".pdf,image/*,.heic,.heif"
				multiple
				label={words.upload}
				hint={words.uploadHint(MAX_FILES, MAX_PAGES)}
				onfiles={(files) => void add(files)}
			/>
		{/if}
		<div class="flex flex-wrap items-center gap-3">
			<Button variant="secondary" onclick={useSample}>{words.sample}</Button>
			<p class="text-sm text-muted">{words.sampleNote}</p>
		</div>
		{#if refused}
			<Callout tone="caution">{words.refused(refused, MAX_FILES)}</Callout>
		{/if}

		{#if items.length}
			<section class="space-y-4">
				{#if sample}<DemoNote />{/if}
				<div class="flex flex-wrap items-end justify-between gap-3">
					<div>
						<h2 class="st-display-sm text-xl sm:text-2xl">{words.queueTitle}</h2>
						<p class="mt-1.5 max-w-2xl text-sm text-muted">{words.queueHint}</p>
						<p class="mt-2 text-sm font-medium" id="batch-tally" aria-live="polite">
							{words.tally(
								counts.ok,
								counts.review,
								counts.failed,
								counts.confirmed,
								counts.queued + counts.reading
							)}
						</p>
					</div>
					<div class="flex flex-wrap gap-2">
						<Button
							id="confirm-clean"
							variant="secondary"
							onclick={confirmClean}
							disabled={confirming || counts.ok === 0}
						>
							{confirming ? words.confirming : words.confirmClean(counts.ok)}
						</Button>
						<Button
							id="batch-analyse"
							onclick={analyse}
							disabled={analysing || nConfirmed === 0 || counts.queued + counts.reading > 0}
						>
							{analysing ? words.analysing : words.analyse(nConfirmed)}
						</Button>
						<Button variant="quiet" onclick={startOver}>{words.startOver}</Button>
					</div>
				</div>
				<p class="text-xs text-faint">{words.confirmCleanHint}</p>
				{#if nConfirmed && counts.ok + counts.review}
					<p class="text-sm text-caution">{words.unconfirmedLeft(counts.ok + counts.review)}</p>
				{/if}

				<BatchQueue
					{items}
					open={openId}
					onopen={(id) => (openId = openId === id ? null : id)}
					onretry={retry}
					onmanual={typeIn}
					{detail}
				/>
			</section>
		{/if}

	</div>
{/if}
