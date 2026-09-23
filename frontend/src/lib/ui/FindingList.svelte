<script lang="ts">
	import type { Finding } from '$lib/api/client';
	import { legalRefs, result } from '$copy/en';
	import { bySeverity, severityTone, toneEdge } from './tone';
	import SeverityTag from './SeverityTag.svelte';

	let { findings }: { findings: Finding[] } = $props();

	// The engine already sorts these strongest first. Sorting again is not distrust of it:
	// a list that arrives from anywhere else, or one filtered in a component, still has to
	// put the strongest thing a judge would want to see at the top.
	const ordered = $derived([...findings].sort(bySeverity));
</script>

<section aria-labelledby="findings-heading">
	<h2 id="findings-heading" class="st-display-sm text-xl sm:text-2xl">{result.findings}</h2>

	{#if ordered.length === 0}
		<p class="mt-3 text-muted">{result.noFindings}</p>
	{:else}
		<ul class="mt-5 space-y-3">
			{#each ordered as finding (finding.code + finding.title)}
				<li
					class="rounded-card border-l-2 bg-surface p-5 sm:p-6
					       {toneEdge[severityTone(finding.severity)]}"
				>
					<div class="flex flex-wrap items-baseline gap-x-3 gap-y-2">
						<h3 class="grow text-base font-semibold tracking-[-0.015em]">{finding.title}</h3>
						<SeverityTag severity={finding.severity} />
					</div>
					<p class="mt-2.5 leading-relaxed text-muted">{finding.detail}</p>
					{#if finding.legal_ref && finding.legal_ref in legalRefs}
						<p class="mt-4 border-t border-line pt-3 text-sm text-faint">
							<span class="font-medium text-ink">{result.basedOn}</span>
							{legalRefs[finding.legal_ref as keyof typeof legalRefs]}
						</p>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}
</section>
