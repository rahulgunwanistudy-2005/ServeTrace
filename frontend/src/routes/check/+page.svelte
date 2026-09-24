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
	import { api, ApiError } from '$lib/api/client';
	import { caseStore, save, restore, forget } from '$lib/case/store.svelte';
	import AffidavitReview from '$lib/check/AffidavitReview.svelte';
	import HouseholdStep from '$lib/check/HouseholdStep.svelte';
	import LocationStep from '$lib/check/LocationStep.svelte';
	import Button from '$lib/ui/Button.svelte';
	import Callout from '$lib/ui/Callout.svelte';
	import CheckBox from '$lib/ui/CheckBox.svelte';
	import FileDrop from '$lib/ui/FileDrop.svelte';
	import StepHeader from '$lib/ui/StepHeader.svelte';
	import TextField from '$lib/ui/TextField.svelte';
	import { nyLocalToInstant } from '$lib/ingest/tz';
	import { steps, upload, wizard } from '$copy/en';

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
	let values = $state<Record<string, string>>({
		method: 'unknown',
		defendant_name: '',
		served_address: '',
		served_date: '',
		served_time: '',
		recipient_name: '',
		recipient_relationship: '',
		index_number: '',
		court: '',
		plaintiff: '',
		mailing_date: '',
		proof_filed_date: '',
		server_name: ''
	});
	/**
	 * Reading a field.
	 *
	 * `values` is an index signature because the review card walks it by name, and under
	 * `noUncheckedIndexedAccess` every lookup is `string | undefined`. That is not the
	 * compiler being pedantic — a key typo really would read undefined — so the default
	 * lives in one place rather than at each of the dozen call sites.
	 */
	const v = (key: string): string => values[key] ?? '';

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
		try {
			const extracted = await api.extract(file);
			caseStore.extraction = extracted;
			const draft = extracted.draft as unknown as Record<string, unknown>;
			for (const key of Object.keys(values)) {
				const read = draft[key];
				if (typeof read === 'string' && read) values[key] = read;
			}
			if (draft.served_at && typeof draft.served_at === 'string') {
				const at = new Date(draft.served_at);
				values.served_date ||= at.toISOString().slice(0, 10);
				values.served_time ||= at.toISOString().slice(11, 16);
			}
		} catch (error) {
			failure = error instanceof ApiError ? error.message : upload.readFailed;
		} finally {
			busy = false;
		}
	}

	/**
	 * The typed fields as the contract wants them.
	 *
	 * The address is geocoded here rather than in the engine because §11 measures from a
	 * point, and a person typing an address has no way to supply one. A failure to resolve
	 * is reported as a problem with that field, not as a failed analysis.
	 */
	async function toAffidavit() {
		/**
		 * The time on an affidavit is New York wall-clock, and `new Date('2025-06-12T19:42')`
		 * reads it as the *browser's* wall clock.
		 *
		 * A first cut did exactly that, and on a machine set to IST a service typed as
		 * 19:42 reached the engine as 10:12 AM — a nine-and-a-half hour error that moved
		 * the claimed moment to a different part of the day and would have produced a
		 * confident, wrong verdict for anyone not sitting in New York. `nyLocalToInstant`
		 * is session 3's answer to this and already handles both DST edges.
		 */
		const local = nyLocalToInstant(v('served_date'), v('served_time') || '00:00');
		if (!local) throw new ApiError('bad_input', 400, upload.timeNeeded);
		const resolved = await api.geocode(v('served_address').trim());
		if (!resolved.result) throw new ApiError('bad_input', 400, upload.addressNotFound);
		return {
			index_number: v('index_number') || null,
			court: v('court') || null,
			plaintiff: v('plaintiff') || null,
			defendant_name: v('defendant_name'),
			server_name: v('server_name') || null,
			server_license: null,
			agency_license: null,
			method: v('method'),
			served_at: local.iso,
			served_address: v('served_address').trim(),
			served_location: resolved.result.location,
			recipient_name: v('recipient_name') || null,
			recipient_relationship: v('recipient_relationship') || null,
			recipient_description: caseStore.extraction?.draft.recipient_description ?? null,
			attempts: [],
			mailing_date: v('mailing_date') || null,
			mailing_address: null,
			proof_filed_date: v('proof_filed_date') || null,
			source_sha256: caseStore.extraction?.source_sha256 ?? '0'.repeat(64),
			field_confidence: caseStore.extraction?.draft.field_confidence ?? {},
			user_confirmed: true
		} as NonNullable<typeof caseStore.affidavit>;
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
		caseStore.isDemo = false;
		if (caseStore.persisted) await save();
		await goto('/result');
	}

	/** The sworn moments the ingest step windows around (bible §13). */
	const claims = $derived(caseStore.affidavit ? [caseStore.affidavit.served_at] : []);
</script>

<svelte:head><title>{steps.one.title} — ServeTrace</title></svelte:head>

<div class="st-shell st-shell-prose py-12 sm:py-16">
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
		<div class="mb-8"><Callout tone="contradicted" title="That did not work">{failure}</Callout></div>
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

		<div class="mt-6">
			<FileDrop
				accept=".pdf,image/*"
				label={busy ? upload.reading : upload.prompt}
				hint="A PDF or a photo, up to 15 MB."
				{busy}
				onfile={upload_}
			/>
		</div>

		<div class="mt-10">
			<AffidavitReview extraction={caseStore.extraction} bind:values bind:confirmed />
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
