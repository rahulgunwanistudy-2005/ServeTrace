<script lang="ts">
	/**
	 * The batch report on screen: agencies ranked, how often each rule fired, servers
	 * ranked, and one server's day on the map. Build prompt §6.3–6.4.
	 *
	 * Agencies first, because an agency is what a complaint names; the server table and
	 * map below are the evidence behind each agency's row. The PDF is the same report the
	 * browser already holds, posted back with a picture of whichever server's map is open.
	 */
	import { api, ApiError, type BatchExportKind, type BatchReport, type RuleRate } from '$lib/api/client';
	import { advocate } from '$copy/en';
	import ServerDetail from './ServerDetail.svelte';
	import ServerTable from './ServerTable.svelte';
	import Button from '$lib/ui/Button.svelte';
	import Callout from '$lib/ui/Callout.svelte';
	import Card from '$lib/ui/Card.svelte';
	import Eyebrow from '$lib/ui/Eyebrow.svelte';
	import { saveBlob } from '$lib/download';

	let {
		report,
		unconfirmed,
		failed,
		onback
	}: {
		report: BatchReport;
		/** Rows still waiting for a person, left out of the analysis. */
		unconfirmed: number;
		/** Files that could not be read at all. */
		failed: number;
		onback: () => void;
	} = $props();

	const words = advocate.batch;

	/** The person's pick, else the worst server: the one they came to look at. */
	let picked = $state<string | null>(null);
	const selected = $derived(picked ?? report.servers[0]?.server_id ?? null);
	let capture = $state<(() => string | null) | null>(null);
	let busy = $state(false);
	let failure = $state<string | null>(null);

	const selectedReport = $derived(report.servers.find((s) => s.server_id === selected) ?? null);
	const mappable = $derived(new Set((report.records ?? []).map((r) => r.server_id)));
	const analysed = $derived(report.n_affidavits - report.rejected.length);

	function flagged(rates: RuleRate[]): number {
		return rates.reduce((sum, rate) => sum + rate.flagged, 0);
	}

	function describe(error: unknown): string {
		return error instanceof ApiError ? error.message : 'Something went wrong.';
	}

	async function csv(kind: BatchExportKind) {
		failure = null;
		try {
			saveBlob(await api.advocate.batchCsv(report, kind), `servetrace-batch-${kind}.csv`);
		} catch (error) {
			failure = describe(error);
		}
	}

	async function pdf() {
		busy = true;
		failure = null;
		try {
			// The map open on screen goes on its agency's page, read at the moment of the
			// press so it shows what the person is looking at.
			const map_images: Record<string, string> = {};
			const image = capture?.() ?? null;
			const owner = report.agencies.find((a) => selected && a.servers.includes(selected));
			if (image && owner) map_images[owner.agency_key] = image;
			const blob = await api.advocate.batchPdf({ report, map_images, unconfirmed, failed });
			saveBlob(blob, 'servetrace-agency-report.pdf');
		} catch (error) {
			failure = describe(error);
		} finally {
			busy = false;
		}
	}
</script>

<div class="space-y-10">
	{#if failure}
		<Callout tone="contradicted" title="That did not work">{failure}</Callout>
	{/if}

	<section class="space-y-4">
		<div class="flex flex-wrap items-start justify-between gap-3">
			<div>
				<h2 class="st-display-sm text-xl sm:text-2xl">{words.reportTitle}</h2>
				<p class="mt-1.5 max-w-2xl text-sm text-muted">{words.reportHint}</p>
			</div>
			<div class="flex flex-wrap gap-2">
				<Button id="batch-pdf" onclick={pdf} disabled={busy}>
					{busy ? words.downloadingPdf : words.downloadPdf}
				</Button>
				<Button variant="quiet" onclick={onback}>{words.backToQueue}</Button>
			</div>
		</div>
		<p class="text-sm text-muted">
			{words.totals(analysed, report.servers.length, report.agencies.length)}
		</p>

		<div class="relative overflow-x-auto rounded-card bg-surface">
			<table class="w-full border-collapse text-sm" id="agency-table">
				<caption class="sr-only">{words.reportTitle}. {words.reportHint}</caption>
				<thead>
					<tr class="st-eyebrow border-b border-line-strong text-left">
						<th scope="col" class="px-4 py-3 font-semibold">{words.agencyColumns.rank}</th>
						<th scope="col" class="px-4 py-3 font-semibold">{words.agencyColumns.agency}</th>
						<th scope="col" class="px-4 py-3 text-right font-semibold">
							{words.agencyColumns.affidavits}
						</th>
						<th scope="col" class="px-4 py-3 text-right font-semibold">
							{words.agencyColumns.pairs}
						</th>
						<th scope="col" class="px-4 py-3 text-right font-semibold">
							{words.agencyColumns.descriptions}
						</th>
						<th scope="col" class="px-4 py-3 text-right font-semibold">
							{words.agencyColumns.flags}
						</th>
					</tr>
				</thead>
				<tbody>
					{#each report.agencies as agency (agency.agency_key)}
						{@const flags = flagged(agency.rule_rates)}
						{@const any = agency.impossible_pairs > 0 || agency.repeated_descriptions.length > 0 || flags > 0}
						<tr class="border-b border-line align-top last:border-0">
							<td class="px-4 py-3 font-semibold tabular-nums {any ? 'text-contradicted' : 'text-muted'}">
								{agency.risk_rank}
							</td>
							<td class="px-4 py-3">
								<span class="font-medium">{agency.agency_display}</span>
								<span class="block text-xs text-faint">{agency.servers.join(' · ')}</span>
							</td>
							<td class="px-4 py-3 text-right tabular-nums text-muted">{agency.n_affidavits}</td>
							<td class="px-4 py-3 text-right tabular-nums {agency.impossible_pairs ? 'font-semibold text-contradicted' : 'text-faint'}">
								{agency.impossible_pairs}
							</td>
							<td class="px-4 py-3 text-right tabular-nums {agency.repeated_descriptions.length ? 'font-semibold text-caution' : 'text-faint'}">
								{agency.repeated_descriptions.length}
							</td>
							<td class="px-4 py-3 text-right">
								{#if flags}
									<ul class="space-y-0.5 text-xs">
										{#each agency.rule_rates.filter((r) => r.flagged) as rate (rate.rule_code)}
											<li>
												<span class="font-semibold text-caution">{rate.rule_code}</span>
												<span class="tabular-nums text-muted">{rate.flagged}/{rate.applicable}</span>
											</li>
										{/each}
									</ul>
								{:else}
									<span class="text-faint">0</span>
								{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		<div class="flex flex-wrap gap-2">
			<Button variant="secondary" onclick={() => csv('agencies')}>{words.downloadAgencies}</Button>
			<Button variant="secondary" onclick={() => csv('flags')}>{words.downloadFlags}</Button>
			<Button variant="secondary" onclick={() => csv('pairs')}>{words.downloadPairs}</Button>
		</div>
	</section>

	<section class="space-y-4">
		<div>
			<h2 class="st-display-sm text-xl sm:text-2xl">{words.ratesTitle}</h2>
			<p class="mt-1.5 max-w-2xl text-sm text-muted">{words.ratesHint}</p>
		</div>
		<ul class="grid gap-3 sm:grid-cols-2">
			{#each report.rule_rates as rate (rate.rule_code)}
				<li>
					<Card tone={rate.flagged ? 'caution' : undefined}>
						<p class="st-eyebrow">{rate.rule_code}</p>
						<p class="mt-1 font-medium">{words.ruleNames[rate.rule_code] ?? rate.rule_code}</p>
						<p class="mt-2 text-sm tabular-nums text-muted">
							<span class="text-lg font-semibold text-ink">{Math.round(rate.rate * 100)}%</span>
							· {words.rate(rate.flagged, rate.applicable)}
						</p>
					</Card>
				</li>
			{/each}
		</ul>
	</section>

	{#if report.rejected.length || unconfirmed || failed}
		<details class="rounded-card border border-caution/30 bg-caution-quiet p-4 text-sm sm:p-5">
			<summary class="cursor-pointer font-semibold text-caution">
				{report.rejected.length
					? words.leftOutTitle(report.rejected.length)
					: words.unreadTitle(unconfirmed + failed)}
			</summary>
			<p class="mt-2 text-muted">{words.leftOutBody}</p>
			{#if unconfirmed || failed}
				<p class="mt-2 text-muted">{words.unreadTitle(unconfirmed + failed)}.</p>
			{/if}
			<ul class="mt-3 max-h-64 space-y-1 overflow-auto">
				{#each report.rejected as row (row.index)}
					<li class="flex gap-3">
						<span class="w-28 shrink-0 font-medium tabular-nums">{words.leftOutRow(row.index + 1)}</span>
						<span class="text-muted">{row.reason}</span>
					</li>
				{/each}
			</ul>
		</details>
	{/if}

	<section class="space-y-4">
		<div>
			<h2 class="st-display-sm text-xl sm:text-2xl">{words.serversTitle}</h2>
			<p class="mt-1.5 text-sm text-muted">{words.mapInPdf}</p>
		</div>
		<ServerTable reports={report.servers} {selected} {mappable} onselect={(id) => (picked = id)} />
	</section>

	{#if selectedReport}
		<ServerDetail
			report={selectedReport}
			records={report.records ?? []}
			onmap={(fn) => (capture = fn)}
		/>
	{/if}

	<Card>
		<Eyebrow>{advocate.gpsTitle}</Eyebrow>
		<p class="mt-3 text-sm leading-relaxed text-muted">{advocate.gpsBody}</p>
		<p class="mt-3 text-sm leading-relaxed text-muted">{advocate.dcwpNote}</p>
	</Card>

	<p class="text-sm leading-relaxed text-muted">{words.footer}</p>
	<p class="border-t border-line pt-5 text-xs text-faint">
		app {report.app_version} · engine {report.engine_version} · params {report.params_version}
	</p>
</div>
