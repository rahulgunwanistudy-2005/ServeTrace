<script lang="ts">
	/**
	 * The three bundled cases, one per tier the engine can reach for a main claim.
	 *
	 * Bible §16 wants a demo that never fails and never lies about what it is: the chip
	 * appears before the heading, and every card carries the tier it demonstrates, so a
	 * judge watching the video can see that the CONSISTENT case is shown with the same
	 * weight as the CONTRADICTED one rather than tucked away.
	 */
	import ActionRow from '$lib/ui/ActionRow.svelte';
	import Button from '$lib/ui/Button.svelte';
	import DemoChip from '$lib/ui/DemoChip.svelte';
	import Eyebrow from '$lib/ui/Eyebrow.svelte';
	import TierBadge from '$lib/ui/TierBadge.svelte';
	import { demo } from '$copy/en';
</script>

<svelte:head><title>Demo — ServeTrace</title></svelte:head>

<section class="st-panel st-iridescent rounded-none">
	<div class="st-shell py-14 sm:py-20">
		<DemoChip invert />
		<h1 class="st-display mt-6 max-w-3xl text-3xl text-panel-ink sm:text-5xl">{demo.title}</h1>
		<p class="mt-5 max-w-2xl text-lg leading-relaxed text-panel-muted">{demo.note}</p>
	</div>
</section>

<div class="st-shell py-14 sm:py-20">
	<Eyebrow index="01">Three cases</Eyebrow>

	<ul class="mt-6 grid gap-4 sm:grid-cols-3">
		{#each demo.cases as demoCase (demoCase.id)}
			<li class="flex flex-col rounded-card bg-surface p-6">
				<!-- Wrapped: a bare inline-flex badge would stretch to the column's width. -->
				<div><TierBadge tier={demoCase.tier} size="sm" /></div>
				<h2 class="st-display-sm mt-4 text-xl">{demoCase.name}</h2>
				<p class="mt-2.5 grow text-sm leading-relaxed text-muted">{demoCase.summary}</p>
			</li>
		{/each}
	</ul>

	<div class="mt-12 border-t border-line pt-8">
		<p class="max-w-2xl leading-relaxed text-muted">{demo.comingSoon}</p>
		<div class="mt-6 flex flex-wrap items-center gap-3">
			<Button href="/check" size="lg" arrow>Start your own check</Button>
			<div class="w-full max-w-xs"><ActionRow href="/methodology" label="How the check works" /></div>
		</div>
	</div>
</div>
