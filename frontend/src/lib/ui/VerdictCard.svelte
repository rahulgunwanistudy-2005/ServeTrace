<script lang="ts">
	/**
	 * The one screen the whole product exists to produce.
	 *
	 * It is the single raised card in the system — everything else on the page is a tonal
	 * block that sits *in* the paper, so the one thing that sits *on* it is unmistakable
	 * without any colour being spent on the distinction.
	 *
	 * Bible §6 is load-bearing here: a CONSISTENT verdict gets exactly this treatment,
	 * exactly this size, and exactly this prominence. Showing it honestly is a feature,
	 * and a result card that quietly shrank when the news was good would be the product
	 * arguing with its own evidence.
	 */
	import type { CaseAnalysis } from '$lib/api/client';
	import { result, tiers, verdictLine } from '$copy/en';
	import { tierTone, toneEdge, toneInk } from './tone';
	import Eyebrow from './Eyebrow.svelte';
	import LimitationNote from './LimitationNote.svelte';
	import TierBadge from './TierBadge.svelte';

	let { analysis }: { analysis: CaseAnalysis } = $props();

	const main = $derived(analysis.verdicts.find((v) => v.claim_ref === 'served_at'));
	const tone = $derived(tierTone(analysis.overall));
</script>

<section class="overflow-hidden rounded-card bg-raised shadow-card" aria-labelledby="verdict-headline">
	<!-- The class comes out of a map rather than a template string: Tailwind scans source
	     text, so a name built at runtime is a name it never generates. -->
	<div class="border-t-4 px-5 py-7 sm:px-8 sm:py-9 {toneEdge[tone]}">
		<TierBadge tier={analysis.overall} />
		<h2 id="verdict-headline" class="st-display mt-4 text-3xl sm:text-[2.75rem]">
			{tiers[analysis.overall].headline}
		</h2>

		{#if main}
			<!-- Bible §14.5: the one sentence carrying the number, right under the headline. -->
			<p class="st-statement mt-5 max-w-2xl {toneInk[tone]}">
				{verdictLine(main.claimed_at, main.nearest_fix_km, main.required_speed_kmh)}
			</p>
		{/if}
	</div>

	<div class="border-t border-line px-5 py-6 sm:px-8">
		<Eyebrow>{result.whatThisMeans}</Eyebrow>
		<p class="mt-3 max-w-2xl leading-relaxed text-muted">{tiers[analysis.overall].meaning}</p>
		<LimitationNote />
	</div>
</section>
