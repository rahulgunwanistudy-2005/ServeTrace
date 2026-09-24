<script lang="ts">
	/**
	 * Step 3 of 3: what we found. Bible §14.5.
	 *
	 * Composed entirely from primitives S6 already built — `VerdictCard`, `ClaimTable`,
	 * `FindingList`, `DeadlineCard`, `Callout`, `ActionRow` — because the visual system is
	 * settled and this screen's job is to arrange it, not to invent more of it.
	 *
	 * The order is deliberate and it is the order a person asks the questions in: what is
	 * the answer, where were you, what exactly did it look at, what did it find, what does
	 * that mean and not mean, how long do you have, what can you do now.
	 */
	import { goto } from '$app/navigation';
	import { caseStore } from '$lib/case/store.svelte';
	import { api, ApiError, type AffiantStatement, type CaseAnalysis } from '$lib/api/client';
	import ActionRow from '$lib/ui/ActionRow.svelte';
	import Button from '$lib/ui/Button.svelte';
	import Callout from '$lib/ui/Callout.svelte';
	import Card from '$lib/ui/Card.svelte';
	import ClaimTable from '$lib/ui/ClaimTable.svelte';
	import DeadlineCard from '$lib/ui/DeadlineCard.svelte';
	import DemoNote from '$lib/ui/DemoNote.svelte';
	import Eyebrow from '$lib/ui/Eyebrow.svelte';
	import FindingList from '$lib/ui/FindingList.svelte';
	import LimitationNote from '$lib/ui/LimitationNote.svelte';
	import VerdictCard from '$lib/ui/VerdictCard.svelte';
	import AffiantForm from '$lib/ui/AffiantForm.svelte';
	import ResultMap from '$lib/map/ResultMap.svelte';
	import { result } from '$copy/en';

	let analysis = $state<CaseAnalysis | null>(caseStore.analysis);
	let failure = $state<string | null>(null);
	let busy = $state(false);
	/** Asks the map for its canvas, at the moment the packet is built (bible §15). */
	let captureMap = $state<(() => string | null) | null>(null);
	let downloading = $state<'packet' | 'affidavit' | null>(null);
	/** The draft affidavit cannot be written until the person has answered its ticks. */
	let askingAffiant = $state(false);

	/**
	 * Run the engine if we arrived with a case but no answer — which is what happens
	 * coming from `/demo`, and from the wizard's last step.
	 */
	$effect(() => {
		if (analysis || busy || !caseStore.isAnalysable) return;
		void run();
	});

	async function run() {
		busy = true;
		failure = null;
		try {
			const answer = await api.analyze(caseStore.toRequest());
			caseStore.analysis = answer;
			analysis = answer;
		} catch (error) {
			failure = error instanceof ApiError ? error.message : String(error);
		} finally {
			busy = false;
		}
	}

	/** The body under "what this means" depends on the answer, not on the layout. */
	const meaning = $derived.by(() => {
		switch (analysis?.overall) {
			case 'contradicted':
				return result.whatThisMeansBody;
			case 'consistent':
				return result.consistentMeansBody;
			case 'no_data':
				return result.noDataMeansBody;
			default:
				return result.inconclusiveMeansBody;
		}
	});

	function deliver(blob: Blob, filename: string) {
		const url = URL.createObjectURL(blob);
		const link = document.createElement('a');
		link.href = url;
		link.download = filename;
		link.click();
		URL.revokeObjectURL(url);
	}

	async function downloadPacket() {
		if (!analysis) return;
		downloading = 'packet';
		failure = null;
		try {
			deliver(
				await api.documents.packet(analysis, captureMap?.() ?? null, caseStore.fixes),
				'servetrace-evidence-packet.pdf'
			);
		} catch (error) {
			failure = error instanceof ApiError ? error.message : String(error);
		} finally {
			downloading = null;
		}
	}

	async function downloadAffidavit(affiant: AffiantStatement) {
		if (!analysis) return;
		downloading = 'affidavit';
		failure = null;
		try {
			deliver(await api.documents.affidavit(analysis, affiant), 'servetrace-draft-affidavit.pdf');
			askingAffiant = false;
		} catch (error) {
			failure = error instanceof ApiError ? error.message : String(error);
		} finally {
			downloading = null;
		}
	}
</script>

<svelte:head><title>{result.findings} — ServeTrace</title></svelte:head>

<div class="st-shell py-12 sm:py-16">
	{#if !analysis && !busy && !caseStore.isAnalysable}
		<!-- Reachable from a bookmark and from the nav. It cannot throw and it cannot show
		     an empty verdict card, so it says what happened and points at the two doors. -->
		<div class="st-shell-prose">
			<Eyebrow>Step 03 / 03</Eyebrow>
			<h1 class="st-display mt-5 text-3xl sm:text-5xl">{result.emptyTitle}</h1>
			<p class="mt-5 text-lg leading-relaxed text-muted">{result.emptyBody}</p>
			<div class="mt-8 grid max-w-xl gap-3 sm:grid-cols-2">
				<ActionRow href="/check" label="Start a check" />
				<ActionRow href="/demo" label="See a worked example" />
			</div>
		</div>
	{:else}
		{#if caseStore.isDemo}<div class="mb-6"><DemoNote /></div>{/if}

		{#if failure}
			<div class="mb-8">
				<Callout tone="contradicted" title="That did not work">{failure}</Callout>
			</div>
		{/if}

		{#if busy && !analysis}
			<p class="text-lg text-muted">Working it out…</p>
		{/if}

		{#if analysis}
			<div class="space-y-12">
				<VerdictCard {analysis} />

				<section>
					<h2 class="st-display-sm text-xl sm:text-2xl">{result.yourTrail}</h2>
					<div class="mt-5">
						<ResultMap {analysis} fixes={caseStore.fixes} onReady={(fn) => (captureMap = fn)} />
					</div>
				</section>

				<section>
					<h2 class="st-display-sm text-xl sm:text-2xl">{result.claimsTitle}</h2>
					<div class="mt-5"><ClaimTable verdicts={analysis.verdicts} /></div>
				</section>

				<!-- `FindingList` carries its own heading and its own `aria-labelledby`, so
				     wrapping it in a second one printed "What we found" twice. -->
				<FindingList findings={analysis.findings} />

				<!-- Bible §6: both halves, together, and never one without the other. -->
				<section class="grid gap-5 sm:grid-cols-2">
					<Card>
						<Eyebrow>{result.whatThisMeans}</Eyebrow>
						<p class="mt-3 leading-relaxed text-muted">{meaning}</p>
					</Card>
					<Card>
						<Eyebrow>{result.whatItDoesNot}</Eyebrow>
						<p class="mt-3 leading-relaxed text-muted">{result.whatItDoesNotBody}</p>
					</Card>
				</section>

				<DeadlineCard deadlines={analysis.deadlines} />

				<section>
					<h2 class="st-display-sm text-xl sm:text-2xl">{result.nextTitle}</h2>
					<div class="mt-5 grid gap-3 sm:grid-cols-2">
						<ActionRow
							label={downloading === 'packet' ? 'Preparing…' : result.downloadPacket}
							disabled={downloading !== null}
							onclick={downloadPacket}
						/>
						<ActionRow
							label={result.downloadAffidavit}
							disabled={downloading !== null || askingAffiant}
							onclick={() => (askingAffiant = true)}
						/>
					</div>

					{#if askingAffiant}
						<div class="mt-5">
							<AffiantForm
								defaultName={analysis.affidavit.defendant_name}
								busy={downloading === 'affidavit'}
								onsubmit={downloadAffidavit}
								oncancel={() => (askingAffiant = false)}
							/>
						</div>
					{/if}

					<div class="mt-5">
						<Callout tone="neutral" title={result.askForGps}>{result.askForGpsWhy}</Callout>
					</div>

					<div class="mt-5 flex flex-wrap gap-3">
						<Button href="/methodology" variant="secondary">{result.sourceHint}</Button>
						<Button
							variant="quiet"
							onclick={() => {
								caseStore.reset();
								void goto('/check');
							}}
						>
							{result.startOver}
						</Button>
					</div>
				</section>

				<div>
					<LimitationNote />
					<p class="mt-4 text-xs text-faint">
						engine {analysis.engine_version} · thresholds {analysis.params_version}
					</p>
				</div>
			</div>
		{/if}
	{/if}
</div>
