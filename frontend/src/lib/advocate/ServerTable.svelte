<script lang="ts">
	/**
	 * Servers ranked by how much of their own filing history does not fit together.
	 *
	 * A real table on every width rather than cards on a phone: this is Dev's desktop
	 * tool (bible §4), and the comparison between rows *is* the information — a column of
	 * cards makes "four and this one has none" much harder to see than a column of
	 * numbers does.
	 *
	 * Rows are buttons, not links. Selecting a server changes what the map beside it
	 * draws; it does not navigate, and nothing about this report survives a reload,
	 * because nothing about it was stored.
	 */
	import type { ServerReport } from '$lib/api/client';
	import { advocate } from '$copy/en';

	let {
		reports,
		selected,
		mappable,
		onselect
	}: {
		reports: ServerReport[];
		selected: string | null;
		/** Server ids whose filings came back, so a row can say when its day is not drawable. */
		mappable: Set<string>;
		onselect: (serverId: string) => void;
	} = $props();

	function flagged(report: ServerReport): boolean {
		return report.impossible_pairs.length > 0 || report.repeated_descriptions.length > 0;
	}
</script>

<div class="overflow-x-auto rounded-card bg-surface">
	<table class="w-full border-collapse text-sm">
		<caption class="sr-only">{advocate.riskTable}. {advocate.riskTableHint}</caption>
		<thead>
			<tr class="st-eyebrow border-b border-line-strong text-left">
				<th scope="col" class="px-4 py-3 font-semibold">{advocate.columns.rank}</th>
				<th scope="col" class="px-4 py-3 font-semibold">{advocate.columns.server}</th>
				<th scope="col" class="px-4 py-3 text-right font-semibold">
					{advocate.columns.filings}
				</th>
				<th scope="col" class="px-4 py-3 text-right font-semibold">
					{advocate.columns.impossible}
				</th>
				<th scope="col" class="px-4 py-3 text-right font-semibold">
					{advocate.columns.descriptions}
				</th>
				<th scope="col" class="px-4 py-3 text-right font-semibold">
					{advocate.columns.busiest}
				</th>
			</tr>
		</thead>
		<tbody>
			{#each reports as report (report.server_id)}
				{@const isSelected = report.server_id === selected}
				<tr class="border-b border-line last:border-0 {isSelected ? 'bg-accent-quiet' : ''}">
					<td class="px-4 py-0">
						<button
							type="button"
							onclick={() => onselect(report.server_id)}
							aria-pressed={isSelected}
							class="-mx-2 w-full px-2 py-3 text-left font-semibold tabular-nums
							       {flagged(report) ? 'text-contradicted' : 'text-muted'}"
						>
							{report.risk_rank}
						</button>
					</td>
					<td class="px-4 py-3">
						<button
							type="button"
							onclick={() => onselect(report.server_id)}
							class="text-left font-medium text-ink underline decoration-line-strong
							       underline-offset-4 hover:decoration-ink"
						>
							{report.server_id}
						</button>
						{#if !mappable.has(report.server_id)}
							<span class="block text-xs text-faint">not on the map</span>
						{/if}
					</td>
					<td class="px-4 py-3 text-right tabular-nums text-muted">{report.n_records}</td>
					<td class="px-4 py-3 text-right tabular-nums">
						{#if report.impossible_pairs.length}
							<span class="font-semibold text-contradicted">
								{report.impossible_pairs.length}
							</span>
						{:else}
							<span class="text-muted">—</span>
						{/if}
					</td>
					<td class="px-4 py-3 text-right tabular-nums">
						{#if report.repeated_descriptions.length}
							<span class="font-semibold text-caution">
								{report.repeated_descriptions.length}
							</span>
						{:else}
							<span class="text-muted">—</span>
						{/if}
					</td>
					<td class="px-4 py-3 text-right tabular-nums text-muted">
						{report.max_services_per_hour}
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>
