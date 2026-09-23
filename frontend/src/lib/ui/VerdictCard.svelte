<script lang="ts">
	import type { CaseAnalysis } from '$lib/api/client';
	import { result, tiers, verdictLine } from '$copy/en';
	import { tierTone, toneEdge, toneInk } from './tone';
	import LimitationNote from './LimitationNote.svelte';
	import TierBadge from './TierBadge.svelte';

	let { analysis }: { analysis: CaseAnalysis } = $props();

	const main = $derived(analysis.verdicts.find((v) => v.claim_ref === 'served_at'));
	const tone = $derived(tierTone(analysis.overall));
</script>

<section
	class="rounded-card border border-line bg-surface shadow-card overflow-hidden"
	aria-labelledby="verdict-headline"
>
	<!-- The class comes out of a map rather than a template string: Tailwind scans source
	     text, so a name built at runtime is a name it never generates. -->
	<div class="border-b-4 px-5 py-6 sm:px-7 sm:py-7 {toneEdge[tone]}">
		<TierBadge tier={analysis.overall} />
		<h2 id="verdict-headline" class="mt-3 text-2xl leading-tight font-semibold sm:text-3xl">
			{tiers[analysis.overall].headline}
		</h2>

		{#if main}
			<!-- Bible §14.5: the one sentence carrying the number, right under the headline. -->
			<p class="mt-3 text-lg leading-relaxed {toneInk[tone]}">
				{verdictLine(main.claimed_at, main.nearest_fix_km, main.required_speed_kmh)}
			</p>
		{/if}
	</div>

	<div class="px-5 py-5 sm:px-7">
		<h3 class="text-sm font-semibold tracking-wide uppercase text-muted">
			{result.whatThisMeans}
		</h3>
		<p class="mt-2 leading-relaxed text-muted">{tiers[analysis.overall].meaning}</p>
		<LimitationNote />
	</div>
</section>
