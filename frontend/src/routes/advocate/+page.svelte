<script lang="ts">
	/**
	 * Advocate mode: a spreadsheet of filings in, servers ranked by impossibility out.
	 *
	 * Three states on one route rather than three routes, because the whole thing is one
	 * sitting and nothing here survives a reload — there is no case id, because nothing
	 * is stored (bible §16). A URL that looked resumable would be a lie about that.
	 *
	 * Desktop-first, unlike the rest of the product. This is Dev's tool (bible §4): a
	 * paralegal at a legal-aid office with a spreadsheet and two monitors. It still works
	 * at 375 px, because "works on a phone" and "designed for one" are different claims.
	 */
	import { api, ApiError, type AdvocateAnalysis, type AdvocateColumnMapping } from '$lib/api/client';
	import { advocate } from '$copy/en';
	import ColumnMapper from '$lib/advocate/ColumnMapper.svelte';
	import ServerDetail from '$lib/advocate/ServerDetail.svelte';
	import ServerTable from '$lib/advocate/ServerTable.svelte';
	import { guessColumns, isComplete } from '$lib/advocate/mapping';
	import { loadDemoFile } from '$lib/advocate/demoFile';
	import Button from '$lib/ui/Button.svelte';
	import Eyebrow from '$lib/ui/Eyebrow.svelte';
	import Callout from '$lib/ui/Callout.svelte';
	import Card from '$lib/ui/Card.svelte';
	import DemoChip from '$lib/ui/DemoChip.svelte';
	import FileDrop from '$lib/ui/FileDrop.svelte';

	type Stage = 'choose' | 'map' | 'report';

	let stage = $state<Stage>('choose');
	let file = $state<File | null>(null);
	let headers = $state<string[]>([]);
	let mapping = $state<AdvocateColumnMapping>({ server_id: '' });
	let analysis = $state<AdvocateAnalysis | null>(null);
	let selected = $state<string | null>(null);
	let busy = $state(false);
	let failure = $state<string | null>(null);
	/** Bible §16: every screen built on the bundled fixture says so, in as many words. */
	let isDemo = $state(false);

	const selectedReport = $derived(
		analysis?.reports.find((report) => report.server_id === selected) ?? null
	);

	/** Which servers the map can actually draw, so a row can say when it cannot. */
	const mappable = $derived(new Set((analysis?.records ?? []).map((record) => record.server_id)));

	const anythingFound = $derived(
		(analysis?.reports ?? []).some(
			(report) => report.impossible_pairs.length > 0 || report.repeated_descriptions.length > 0
		)
	);

	function describe(error: unknown): string {
		return error instanceof ApiError ? error.message : 'Something went wrong reading that file.';
	}

	async function useDemoFile() {
		busy = true;
		failure = null;
		try {
			isDemo = true;
			await chooseFile(await loadDemoFile());
		} catch {
			isDemo = false;
			failure = 'The example file could not be loaded.';
		} finally {
			busy = false;
		}
	}

	async function chooseFile(chosen: File) {
		busy = true;
		failure = null;
		try {
			const { columns } = await api.advocate.columns(chosen);
			file = chosen;
			headers = columns;
			mapping = guessColumns(columns);
			stage = 'map';
		} catch (error) {
			failure = describe(error);
		} finally {
			busy = false;
		}
	}

	async function run() {
		if (!file || !isComplete(mapping)) return;
		busy = true;
		failure = null;
		try {
			const result = await api.advocate.analyze(file, mapping);
			analysis = result;
			// Open on the worst server, because that is the one they came to look at.
			selected = result.reports[0]?.server_id ?? null;
			stage = 'report';
		} catch (error) {
			failure = describe(error);
		} finally {
			busy = false;
		}
	}

	async function download(kind: 'pairs' | 'servers') {
		if (!analysis) return;
		try {
			const blob = await api.advocate.exportCsv(analysis.reports, kind);
			const url = URL.createObjectURL(blob);
			const link = document.createElement('a');
			link.href = url;
			link.download =
				kind === 'servers' ? 'servetrace-servers.csv' : 'servetrace-impossible-pairs.csv';
			link.click();
			URL.revokeObjectURL(url);
		} catch (error) {
			failure = describe(error);
		}
	}

	function startOver() {
		stage = 'choose';
		file = null;
		headers = [];
		analysis = null;
		selected = null;
		failure = null;
		isDemo = false;
	}
</script>

<svelte:head><title>{advocate.title} — ServeTrace</title></svelte:head>

<section class="st-panel st-iridescent rounded-none">
	<div class="st-shell py-12 sm:py-16">
		{#if isDemo}<div class="mb-5"><DemoChip invert /></div>{:else}<Eyebrow>For legal advocates</Eyebrow>{/if}
		<h1 class="st-display mt-4 max-w-3xl text-3xl text-panel-ink sm:text-5xl">{advocate.title}</h1>
		<p class="mt-5 max-w-2xl text-lg leading-relaxed text-panel-muted">{advocate.sub}</p>
	</div>
</section>

<div class="st-shell space-y-8 py-12 sm:py-16">

	{#if failure}
		<Callout tone="contradicted" title="That did not work">{failure}</Callout>
	{/if}

	{#if stage === 'choose'}
		<div class="grid gap-8 lg:grid-cols-[minmax(0,1fr)_20rem]">
			<div class="space-y-5">
				<FileDrop
					accept=".csv,.xlsx,.xlsm,text/csv"
					label={busy ? advocate.reading : advocate.upload}
					hint={advocate.uploadHint}
					{busy}
					onfile={(chosen) => {
						isDemo = false;
						return chooseFile(chosen);
					}}
				/>

				<div class="flex flex-wrap items-center gap-3">
					<Button variant="secondary" onclick={useDemoFile} disabled={busy}>
						{advocate.orTryDemo}
					</Button>
					<p class="text-sm text-muted">{advocate.demoFileNote}</p>
				</div>
			</div>

			<aside class="space-y-4">
				<Card>
					<Eyebrow>{advocate.premiseTitle}</Eyebrow>
					<p class="mt-3 text-sm leading-relaxed text-muted">{advocate.premiseBody}</p>
				</Card>
				<Callout tone="neutral" title={advocate.gpsTitle}>
					{advocate.gpsBody}
				</Callout>
			</aside>
		</div>
	{:else if stage === 'map'}
		<Card>
			<div class="flex flex-wrap items-baseline justify-between gap-3">
				<div>
					<h2 class="st-display-sm text-xl sm:text-2xl">{advocate.mapColumns}</h2>
					<p class="mt-1.5 text-sm text-muted">{advocate.mapColumnsHint}</p>
				</div>
				<p class="text-sm text-muted">{file?.name}</p>
			</div>

			<div class="mt-6">
				<ColumnMapper {headers} bind:mapping />
			</div>

			<div class="mt-8 flex flex-wrap gap-3">
				<Button onclick={run} disabled={busy || !isComplete(mapping)} size="lg">
					{busy ? advocate.analysing : advocate.analyse}
				</Button>
				<Button variant="quiet" onclick={startOver}>{advocate.back}</Button>
			</div>
		</Card>
	{:else if analysis}
		<div class="space-y-4">
			<div class="flex flex-wrap items-center justify-between gap-3">
				<div>
					<h2 class="st-display-sm text-xl sm:text-2xl">{advocate.riskTable}</h2>
					<p class="mt-1.5 text-sm text-muted">{advocate.riskTableHint}</p>
				</div>
				<div class="flex flex-wrap gap-2">
					<Button variant="secondary" onclick={() => download('pairs')}>
						{advocate.exportCsv}
					</Button>
					<Button variant="secondary" onclick={() => download('servers')}>
						{advocate.exportServers}
					</Button>
					<Button variant="quiet" onclick={startOver}>{advocate.back}</Button>
				</div>
			</div>

			<p class="text-sm text-muted">
				{advocate.statsLine(
					analysis.stats.records,
					analysis.stats.rows_read,
					analysis.stats.servers
				)}
			</p>

			<ServerTable
				reports={analysis.reports}
				{selected}
				{mappable}
				onselect={(id) => (selected = id)}
			/>

			{#if !anythingFound}
				<Callout tone="consistent" title={advocate.nothingFound}>
					{advocate.nothingFoundBody}
				</Callout>
			{/if}

			{#if analysis.rejected.length}
				<details class="rounded-card border border-caution/30 bg-caution-quiet p-4 text-sm sm:p-5">
					<summary class="cursor-pointer font-semibold text-caution">
						{advocate.rejectedTitle(analysis.rejected.length)}
					</summary>
					<p class="mt-2 text-muted">{advocate.rejectedBody}</p>
					<ul class="mt-3 max-h-64 space-y-1 overflow-auto">
						{#each analysis.rejected as row (row.row)}
							<li class="flex gap-3">
								<span class="w-20 shrink-0 font-medium tabular-nums">
									{advocate.rejectedRow(row.row)}
								</span>
								<span class="text-muted">{row.reason}</span>
							</li>
						{/each}
					</ul>
				</details>
			{/if}
		</div>

		{#if selectedReport}
			<ServerDetail report={selectedReport} records={analysis.records} />
		{:else}
			<p class="text-muted">{advocate.selectServer}</p>
		{/if}

		<Card>
			<Eyebrow>{advocate.gpsTitle}</Eyebrow>
			<p class="mt-3 text-sm leading-relaxed text-muted">{advocate.gpsBody}</p>
			<p class="mt-3 text-sm leading-relaxed text-muted">{advocate.dcwpNote}</p>
		</Card>

		<p class="text-sm leading-relaxed text-muted">{advocate.limitation}</p>

		<p class="border-t border-line pt-5 text-xs text-faint">
			engine {analysis.stats.engine_version} · params {analysis.stats.params_version}
		</p>
	{/if}
</div>
