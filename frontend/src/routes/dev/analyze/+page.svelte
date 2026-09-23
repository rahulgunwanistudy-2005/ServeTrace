<script lang="ts">
	import { api, ApiError, type AnalyzeRequest, type CaseAnalysis } from '$lib/api/client';
	import { DEMO_CASES, demoJson, groundTruth, type DemoCase } from '$lib/ingest/demoFixtures';
	import Button from '$lib/ui/Button.svelte';
	import Callout from '$lib/ui/Callout.svelte';
	import ClaimTable from '$lib/ui/ClaimTable.svelte';
	import DeadlineCard from '$lib/ui/DeadlineCard.svelte';
	import DemoChip from '$lib/ui/DemoChip.svelte';
	import FindingList from '$lib/ui/FindingList.svelte';
	import VerdictCard from '$lib/ui/VerdictCard.svelte';
	import { result } from '$copy/en';

	let selected = $state<DemoCase>('maria_contradicted');
	let analysis = $state<CaseAnalysis | null>(null);
	let failure = $state<string | null>(null);
	let busy = $state(false);

	const truth = $derived(groundTruth(selected));

	function buildRequest(name: DemoCase): AnalyzeRequest {
		const affidavit = demoJson<AnalyzeRequest['affidavit']>(name, 'affidavit.json');
		return {
			// The wizard will set this when the user ticks the box. Here it stands in for
			// that tick, which the route refuses to proceed without.
			affidavit: { ...affidavit, user_confirmed: true },
			fixes: demoJson<AnalyzeRequest['fixes']>(name, 'fixes.json'),
			household: demoJson<NonNullable<AnalyzeRequest['household']>>(name, 'household.json'),
			knowledge_date: '2026-06-01',
			judgment_entry_date: '2025-08-20'
		};
	}

	async function run() {
		busy = true;
		failure = null;
		try {
			analysis = await api.analyze(buildRequest(selected));
		} catch (err) {
			analysis = null;
			failure = err instanceof ApiError ? `${err.code}: ${err.message}` : String(err);
		} finally {
			busy = false;
		}
	}
</script>

<svelte:head><title>Engine workbench</title></svelte:head>

<DemoChip />
<h1 class="mt-4 text-2xl font-semibold">Engine workbench</h1>
<p class="mt-2 text-muted">
	Runs a committed demo case through the real <code>POST /api/analyze</code>.
</p>

<div class="mt-6 flex flex-wrap items-end gap-3">
	<label class="text-sm">
		<span class="block font-medium">Demo case</span>
		<select
			bind:value={selected}
			class="mt-1 min-h-11 rounded-lg border border-line-strong bg-surface px-3"
		>
			{#each DEMO_CASES as name (name)}<option value={name}>{name}</option>{/each}
		</select>
	</label>
	<Button onclick={run} disabled={busy}>{busy ? 'Analysing…' : 'Analyse'}</Button>
</div>

<p class="mt-3 text-sm text-muted">
	Generator says: <strong class="text-ink">{truth.true_tier}</strong> · {truth.method} ·
	{truth.n_fixes} fixes · claimed {truth.claimed_at}
</p>

{#if failure}
	<div class="mt-6"><Callout tone="contradicted" title="The request failed">{failure}</Callout></div>
{/if}

{#if analysis}
	<div class="mt-8 space-y-8">
		{#if analysis.overall !== truth.true_tier}
			<Callout tone="caution" title="Engine and generator disagree">
				The generator built this as <strong>{truth.true_tier}</strong> and the engine answered
				<strong>{analysis.overall}</strong>. For a 308(4) case that can be the prior attempts
				rather than a mistake — check the claims table below.
			</Callout>
		{/if}

		<VerdictCard {analysis} />

		<section>
			<h2 class="mb-3 text-xl font-semibold">{result.claimsTitle}</h2>
			<ClaimTable verdicts={analysis.verdicts} />
		</section>

		<FindingList findings={analysis.findings} />
		<DeadlineCard deadlines={analysis.deadlines} />

		<p class="text-xs text-muted">
			engine {analysis.engine_version} · params {analysis.params_version} · generated
			{analysis.generated_at}
		</p>
	</div>
{/if}
