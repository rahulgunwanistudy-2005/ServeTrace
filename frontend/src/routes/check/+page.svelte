<script lang="ts">
	/**
	 * The three-step check. Bible §14.2–§14.4.
	 *
	 * One route rather than three, because the steps share one case and a URL per step
	 * would imply a resumable thing that does not exist — there is no case id, because
	 * nothing is stored on a server (bible §16). Back is a button, and it preserves
	 * everything because every field is written straight into the store rather than into
	 * local state that unmounting would drop.
	 *
	 * Saving is opt-in and its absence is the path that works. Ticking the box writes the
	 * case to IndexedDB in this browser; not ticking it means the case lives as long as
	 * the tab does, which is what the privacy page promises by default.
	 */
	import { goto } from '$app/navigation';
	import { api, ApiError, type DocumentExtraction, type Health, type PageType } from '$lib/api/client';
	import { caseStore, save, restore, forget } from '$lib/case/store.svelte';
	import AffidavitReview from '$lib/check/AffidavitReview.svelte';
	import {
		attemptsFrom,
		changedPages,
		mergeRetag,
		retagPages,
		startReviewTimer,
		valuesFrom,
		type AttemptValues
	} from '$lib/check/review';
	import { loadSampleExtraction } from '$lib/demo/cases';
	import HouseholdStep from '$lib/check/HouseholdStep.svelte';
	import LocationStep from '$lib/check/LocationStep.svelte';
	import Button from '$lib/ui/Button.svelte';
	import Callout from '$lib/ui/Callout.svelte';
	import CheckBox from '$lib/ui/CheckBox.svelte';
	import FileDrop from '$lib/ui/FileDrop.svelte';
	import StepHeader from '$lib/ui/StepHeader.svelte';
	import TextField from '$lib/ui/TextField.svelte';
	import { buildAffidavit } from '$lib/check/affidavit';
	import { steps, upload, wizard, common } from '$copy/en';

	let step = $state(1);
	let busy = $state(false);
	let failure = $state<string | null>(null);
	let blocked = $state<string | null>(null);
	let savedNotice = $state<string | null>(null);
	let offerRestore = $state(false);

	/**
	 * The affidavit fields, as strings, because that is what an input holds and what an
	 * imperfect read produces. They become an `Affidavit` once, in `toAffidavit`.
	 */
	let values = $state<Record<string, string>>(valuesFrom(null));
	let attempts = $state<AttemptValues[]>([]);
	/** Flagged fields the person has accepted or changed. "Confirm all" waits on these. */
	let resolved = $state<string[]>([]);
	/** Which affidavit in the file is about this person. */
	let selected = $state(0);
	/**
	 * Reading a field.
	 *
	 * `values` is an index signature because the review card walks it by name, and under
	 * `noUncheckedIndexedAccess` every lookup is `string | undefined`. That is not the
	 * compiler being pedantic — a key typo really would read undefined — so the default
	 * lives in one place rather than at each of the dozen call sites.
	 */
	const v = (key: string): string => values[key] ?? '';

	/** The upload, kept in this tab only so a re-tag can send the same file back. */
	let lastFile = $state.raw<File | null>(null);
	let retagging = $state(false);
	let sample = $state(false);

	/**
	 * Build prompt §2.3: until the deployment says real papers may go to its reader, the
	 * upload is behind a notice the person has to acknowledge. If we cannot ask the server,
	 * we assume the stricter answer.
	 */
	let health = $state<Health | null>(null);
	let acknowledged = $state(false);
	const realAllowed = $derived(health?.llm_real_data_allowed === true);
	const uploadOpen = $derived(realAllowed || acknowledged);
	const PROVIDERS: Record<string, string> = { gemini: 'Google Gemini', anthropic: 'Anthropic' };
	$effect(() => {
		void api
			.health()
			.then((h) => (health = h))
			.catch(() => (health = null));
	});

	/** Development builds time each review; the target is under two minutes. */
	let timer: ReturnType<typeof startReviewTimer> | null = null;

	/** Put one affidavit from an extraction into the form, as read. */
	function load(extraction: DocumentExtraction, index = 0) {
		caseStore.extraction = extraction;
		const count = extraction.affidavits?.length ?? 0;
		selected = Math.min(index, Math.max(0, count - 1));
		const draft = extraction.affidavits?.[selected]?.draft;
		values = valuesFrom(draft);
		attempts = attemptsFrom(draft);
		resolved = [];
		confirmed = false;
		if (extraction.judgment_entry_date && !judgmentDate) {
			judgmentDate = extraction.judgment_entry_date;
		}
		if (import.meta.env.DEV) timer = startReviewTimer();
	}

	const judgmentNote = $derived.by(() => {
		const read = caseStore.extraction;
		const evidence = read?.judgment_evidence;
		if (!read?.judgment_entry_date || !evidence?.quote || judgmentDate !== read.judgment_entry_date)
			return undefined;
		return upload.review.judgmentRead((evidence.page ?? 0) + 1, evidence.quote);
	});

	let confirmed = $state(false);
	let knowledgeDate = $state('');
	let judgmentDate = $state('');
	let saveHere = $state(false);

	/** A saved case is offered, never loaded behind the person's back. */
	$effect(() => {
		void (async () => {
			if (await restore()) offerRestore = caseStore.affidavit !== null;
		})();
	});

	async function upload_(file: File) {
		busy = true;
		failure = null;
		sample = false;
		try {
			const extracted = await api.extract(file);
			lastFile = file;
			load(extracted);
		} catch (error) {
			failure = error instanceof ApiError ? error.message : upload.readFailed;
		} finally {
			busy = false;
		}
	}

	async function useSample() {
		failure = null;
		lastFile = null;
		load(await loadSampleExtraction());
		sample = true;
	}

	/** Re-read only the pages whose label the person changed, and the affidavits on them. */
	async function retag(pageTypes: PageType[]) {
		const current = caseStore.extraction;
		if (!current || !lastFile) return;
		const pages = retagPages(current, changedPages(current.page_types, pageTypes));
		retagging = true;
		failure = null;
		try {
			const reread = await api.extract(lastFile, { pageTypes, pages });
			load(mergeRetag(current, reread, pages), selected);
		} catch (error) {
			failure = error instanceof ApiError ? error.message : upload.readFailed;
		} finally {
			retagging = false;
		}
	}

	/**
	 * The typed fields as the contract wants them (`lib/check/affidavit.ts`, shared with
	 * the advocate batch). A failure to place the address is reported as a problem with
	 * that field, not as a failed analysis.
	 */
	async function toAffidavit() {
		const draft = caseStore.extraction?.affidavits?.[selected]?.draft;
		return (await buildAffidavit({
			values,
			attempts,
			draft,
			sourceSha256: caseStore.extraction?.source_sha256,
			geocode: async (address) => (await api.geocode(address)).result?.location ?? null
		})) as NonNullable<typeof caseStore.affidavit>;
	}

	/** Step 1 is done when the fields the engine cannot work without are present. */
	function step1Ready(): string | null {
		if (!confirmed) return wizard.needAffidavit;
		if (!v('served_address').trim()) return upload.addressNeeded;
		if (!v('served_date')) return upload.timeNeeded;
		return null;
	}

	async function leaveStep1() {
		const problem = step1Ready();
		if (problem) {
			blocked = problem;
			return;
		}
		busy = true;
		blocked = null;
		failure = null;
		try {
			caseStore.affidavit = await toAffidavit();
			caseStore.confirmed = true;
			caseStore.knowledgeDate = knowledgeDate || null;
			caseStore.persisted = saveHere;
			savedNotice = saveHere ? ((await save()) ? wizard.saved : wizard.saveFailed) : null;
			step = 2;
		} catch (error) {
			failure = error instanceof ApiError ? error.message : String(error);
		} finally {
			busy = false;
		}
	}

	function leaveStep2() {
		if (caseStore.fixes.length === 0) {
			blocked = wizard.needFixes;
			return;
		}
		blocked = null;
		step = 3;
	}

	async function run() {
		caseStore.judgmentDate = judgmentDate || null;
		// A check built on the sample affidavit is a demo: it says so on the result and is
		// counted apart from real use.
		caseStore.isDemo = sample;
		if (caseStore.persisted) await save();
		await goto('/result');
	}

	/** The sworn moments the ingest step windows around (bible §13). */
	const claims = $derived(caseStore.affidavit ? [caseStore.affidavit.served_at] : []);
</script>

<svelte:head><title>{steps.one.title} — ServeTrace</title></svelte:head>

<div
	class="st-shell py-12 sm:py-16 {step === 1 && caseStore.extraction?.previews?.length ? '' : 'st-shell-prose'}"
>
	<StepHeader
		step={step}
		total={3}
		title={step === 1 ? steps.one.title : step === 2 ? steps.two.title : steps.three.title}
		hint={step === 1 ? steps.one.hint : step === 2 ? steps.two.hint : steps.three.hint}
	/>

	{#if offerRestore}
		<div class="mb-8">
			<Callout tone="neutral" title={wizard.restoreFound}>
				<div class="mt-3 flex flex-wrap gap-3">
					<Button
						onclick={() => {
							offerRestore = false;
							if (caseStore.isAnalysable) void goto('/result');
						}}
					>
						{wizard.restore}
					</Button>
					<Button
						variant="quiet"
						onclick={() => {
							caseStore.reset();
							void forget();
							offerRestore = false;
						}}
					>
						{wizard.discard}
					</Button>
				</div>
			</Callout>
		</div>
	{/if}

	{#if failure}
		<div class="mb-8"><Callout tone="contradicted" title={common.failedTitle}>{failure}</Callout></div>
	{/if}
	{#if blocked}
		<div class="mb-8"><Callout tone="caution">{blocked}</Callout></div>
	{/if}

	{#if step === 1}
		<p class="text-lg leading-relaxed text-muted">{upload.prompt}</p>

		<details class="group mt-6 rounded-card bg-surface">
			<summary
				class="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 px-5
				       font-medium [&::-webkit-details-marker]:hidden"
			>
				{upload.whereDoIGetIt}
				<span
					aria-hidden="true"
					class="grid size-6 shrink-0 place-items-center rounded-full border border-line-strong
					       transition-transform group-open:rotate-45"
				>
					<svg viewBox="0 0 16 16" class="size-3" fill="none">
						<path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
					</svg>
				</span>
			</summary>
			<p class="px-5 pb-5 leading-relaxed text-muted">{upload.whereDoIGetItBody}</p>
		</details>

		<div class="mt-6 space-y-4">
			{#if realAllowed && health && health.llm_provider !== 'none'}
				<Callout tone="neutral">
					{upload.realDataAllowed(PROVIDERS[health.llm_provider] ?? health.llm_provider)}
				</Callout>
			{:else if !realAllowed}
				<Callout tone="caution" title={upload.realDataBlocked}>
					<div class="mt-3">
						<CheckBox id="real-data-ack" bind:checked={acknowledged} label={upload.realDataAck} />
					</div>
				</Callout>
			{/if}

			{#if uploadOpen}
				<FileDrop
					accept=".pdf,image/*,.heic,.heif"
					label={busy ? upload.reading : upload.prompt}
					hint="A PDF or a photo, up to 15 MB."
					{busy}
					onfile={upload_}
				/>
			{/if}
			<p>
				<Button variant="quiet" onclick={useSample}>{upload.sample}</Button>
			</p>
			{#if sample}
				<p class="text-sm text-muted">{upload.sampleNote}</p>
			{/if}
		</div>

		<div class="mt-10">
			<AffidavitReview
				extraction={caseStore.extraction}
				{selected}
				bind:values
				bind:attempts
				bind:resolved
				bind:confirmed
				{retagging}
				onselect={(i) => caseStore.extraction && load(caseStore.extraction, i)}
				onretag={lastFile ? retag : undefined}
				onconfirm={() => timer?.stop(sample ? 'sample' : (caseStore.extraction?.source_sha256.slice(0, 8) ?? 'manual'))}
			/>
		</div>

		<div class="mt-8 space-y-5 border-t border-line pt-8">
			<TextField
				id="knowledge-date"
				label={upload.knowledgeQuestion}
				bind:value={knowledgeDate}
				type="date"
				hint={upload.knowledgeHint}
			/>
			<CheckBox id="save-here" bind:checked={saveHere} label={wizard.saveHere} hint={wizard.saveHint} />
		</div>

		<div class="mt-8 flex flex-wrap gap-3">
			<Button onclick={leaveStep1} disabled={busy} size="lg" arrow>{wizard.next}</Button>
		</div>
	{:else if step === 2}
		<LocationStep {claims} bind:fixes={caseStore.fixes} bind:summary={caseStore.ingest} />

		<div class="mt-8 flex flex-wrap gap-3">
			<Button onclick={leaveStep2} size="lg" arrow>{wizard.next}</Button>
			<Button variant="quiet" onclick={() => (step = 1)}>{wizard.back}</Button>
		</div>
	{:else}
		<HouseholdStep bind:members={caseStore.household} />

		<div class="mt-8">
			<TextField
				id="judgment-date"
				label={upload.judgmentQuestion}
				bind:value={judgmentDate}
				type="date"
				hint={upload.judgmentHint}
				invalid={Boolean(judgmentNote)}
				note={judgmentNote}
			/>
		</div>

		<div class="mt-8 flex flex-wrap gap-3">
			<Button onclick={run} disabled={busy} size="lg" arrow>
				{busy ? wizard.running : wizard.run}
			</Button>
			<Button variant="quiet" onclick={() => (step = 2)}>{wizard.back}</Button>
		</div>
	{/if}

	{#if savedNotice}
		<p class="mt-6 text-sm text-muted">{savedNotice}</p>
	{/if}
</div>
