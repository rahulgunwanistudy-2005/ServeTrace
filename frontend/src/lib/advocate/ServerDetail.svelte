<script lang="ts">
	/**
	 * One server, read closely: the map, the sequences, the reused descriptions.
	 *
	 * The order is deliberate. The map first, because the picture is what makes the
	 * argument; then every flagged sequence in words with its numbers, because that is
	 * what goes into a complaint and a picture cannot be quoted; then the alternative
	 * table, which is also the accessibility route into the map (bible §14).
	 */
	import type { ServerReport, ServiceRecord } from '$lib/api/client';
	import { advocate } from '$copy/en';
	import AdvocateMap from '$lib/map/AdvocateMap.svelte';
	import Callout from '$lib/ui/Callout.svelte';
	import Card from '$lib/ui/Card.svelte';
	import { formatDateTime, formatKm, formatSpeed } from '$lib/ui/tone';

	let { report, records }: { report: ServerReport; records: ServiceRecord[] } = $props();

	const mine = $derived(records.filter((record) => record.server_id === report.server_id));
	const ordered = $derived([...mine].sort((a, b) => a.at.localeCompare(b.at)));
	const busy = $derived(report.max_services_per_hour > 12);
</script>

<div class="space-y-6">
	<div>
		<h2 class="text-xl font-semibold sm:text-2xl">
			{advocate.mapTitle} — {report.server_id}
		</h2>
		<p class="mt-1 text-sm text-muted">
			{report.n_records} filings ·
			{report.impossible_pairs.length} sequences that do not add up ·
			rank {report.risk_rank}
		</p>
	</div>

	{#if mine.length}
		<AdvocateMap {report} records={mine} />
	{:else}
		<Callout tone="neutral">
			This server's filings were not among those sent back for the map, so their day
			cannot be drawn. The numbers in the table and the export are complete.
		</Callout>
	{/if}

	{#if report.impossible_pairs.length}
		<section>
			<h3 class="text-lg font-semibold">{advocate.impossiblePairs}</h3>
			<ol class="mt-3 space-y-3">
				{#each report.impossible_pairs as pair, index (index)}
					<li>
						<Card tone="contradicted">
							<p class="font-medium">
								{advocate.pairSummary(
									formatKm(pair.distance_km),
									`${Math.round(pair.minutes)} min`,
									formatSpeed(pair.required_speed_kmh)
								)}
							</p>
							<dl class="mt-3 grid gap-3 text-sm sm:grid-cols-2">
								{#each [pair.a, pair.b] as record, position (position)}
									<div class="rounded-lg bg-sunken p-3">
										<dt class="text-xs tracking-wide text-muted uppercase">
											{position === 0 ? 'First filing' : 'Next filing'}
										</dt>
										<dd class="mt-1 font-medium">{formatDateTime(record.at)}</dd>
										{#if record.address}
											<dd class="text-muted">{record.address}</dd>
										{/if}
										{#if record.case_ref}
											<dd class="text-xs text-muted">{record.case_ref}</dd>
										{/if}
									</div>
								{/each}
							</dl>
						</Card>
					</li>
				{/each}
			</ol>
		</section>
	{/if}

	{#if report.repeated_descriptions.length}
		<section>
			<h3 class="text-lg font-semibold">{advocate.repeatedTitle}</h3>
			<ul class="mt-3 space-y-3">
				{#each report.repeated_descriptions as [description, doors] (description)}
					<li>
						<Card tone="caution">
							<p class="font-mono text-sm break-all">{description}</p>
							<p class="mt-2 text-sm text-muted">{advocate.repeatedBody(doors)}</p>
						</Card>
					</li>
				{/each}
			</ul>
			<p class="mt-3 text-sm text-muted">{advocate.repeatedNote}</p>
		</section>
	{/if}

	<section>
		<h3 class="text-lg font-semibold">{advocate.busiestHourTitle}</h3>
		<p class="mt-2 text-muted">
			{busy ? advocate.busiestHour(report.max_services_per_hour) : advocate.busiestHourOk}
		</p>
	</section>

	{#if ordered.length}
		<details class="rounded-card border border-line bg-surface shadow-card">
			<summary class="cursor-pointer px-5 py-4 font-medium">
				{advocate.mapAlternative}
			</summary>
			<div class="max-h-96 overflow-auto border-t border-line">
				<table class="w-full border-collapse text-sm">
					<thead class="sticky top-0 bg-surface">
						<tr class="border-b border-line text-left text-xs tracking-wide text-muted uppercase">
							<th scope="col" class="px-4 py-2 font-semibold">When</th>
							<th scope="col" class="px-4 py-2 font-semibold">Address</th>
							<th scope="col" class="px-4 py-2 font-semibold">Outcome</th>
							<th scope="col" class="px-4 py-2 font-semibold">Case</th>
						</tr>
					</thead>
					<tbody>
						{#each ordered as record, index (index)}
							<tr class="border-b border-line/60 last:border-0">
								<td class="px-4 py-2 whitespace-nowrap">{formatDateTime(record.at)}</td>
								<td class="px-4 py-2 text-muted">{record.address ?? '—'}</td>
								<td class="px-4 py-2 text-muted">{record.outcome ?? '—'}</td>
								<td class="px-4 py-2 text-muted">{record.case_ref ?? '—'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</details>
	{/if}
</div>
