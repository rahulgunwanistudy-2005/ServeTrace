<script lang="ts">
	import type { ClaimVerdict } from '$lib/api/client';
	import { result } from '$copy/en';
	import { formatDateTime, formatKm, formatSpeed } from './tone';
	import TierBadge from './TierBadge.svelte';

	let { verdicts }: { verdicts: ClaimVerdict[] } = $props();

	// Bible §14: the map has a text alternative table. This is it, and it is also what a
	// judge reads in the printed packet, where there is no map to hover over.
	const label = (ref: string) => (ref === 'served_at' ? result.claimService : result.claimAttempt);
</script>

<div class="overflow-x-auto rounded-card bg-surface">
	<table class="w-full border-collapse text-left text-sm">
		<caption class="sr-only">{result.mapTableCaption}</caption>
		<thead class="border-b border-line-strong">
			<tr class="st-eyebrow">
				<th scope="col" class="px-4 py-3.5 font-semibold">{result.colClaim}</th>
				<th scope="col" class="px-4 py-3.5 font-semibold">{result.colWhen}</th>
				<th scope="col" class="px-4 py-3.5 font-semibold">{result.colDistance}</th>
				<th scope="col" class="px-4 py-3.5 font-semibold">{result.colVerdict}</th>
			</tr>
		</thead>
		<tbody>
			{#each verdicts as verdict (verdict.claim_ref)}
				<tr class="border-b border-line last:border-0">
					<th scope="row" class="px-4 py-3.5 font-medium">{label(verdict.claim_ref)}</th>
					<td class="px-4 py-3.5 text-muted">{formatDateTime(verdict.claimed_at)}</td>
					<td class="px-4 py-3.5 text-muted tabular-nums">
						{#if verdict.nearest_fix_km == null}—{:else}{formatKm(verdict.nearest_fix_km)}{/if}
						{#if verdict.required_speed_kmh}
							<span class="block text-xs">{formatSpeed(verdict.required_speed_kmh)}</span>
						{/if}
					</td>
					<td class="px-4 py-3.5"><TierBadge tier={verdict.tier} size="sm" /></td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>
