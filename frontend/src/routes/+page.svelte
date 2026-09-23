<script lang="ts">
	/**
	 * The landing page, and the only place in the product that is allowed to be cinematic.
	 *
	 * The split is deliberate. Marketing surfaces — this page, the demo, the advocate
	 * intro — get the dark panel and the iridescent field, because someone arriving here
	 * has to be convinced in about four seconds that this is a real instrument and not a
	 * form. The working surfaces (the wizard, the result, methodology, privacy) stay on
	 * calm paper, because by then the person is anxious, reading closely, and would be
	 * ill-served by drama.
	 */
	import Button from '$lib/ui/Button.svelte';
	import Eyebrow from '$lib/ui/Eyebrow.svelte';
	import Section from '$lib/ui/Section.svelte';
	import StatTile from '$lib/ui/StatTile.svelte';
	import { landing, site } from '$copy/en';
</script>

<svelte:head><title>{site.name} — {landing.headline}</title></svelte:head>

<!-- ## Hero -->
<section class="st-panel st-iridescent rounded-none">
	<div class="st-shell flex min-h-[32rem] flex-col justify-end py-16 sm:min-h-[38rem] sm:py-24">
		<Eyebrow>New York City · Civil Court</Eyebrow>

		<h1 class="st-display mt-6 max-w-4xl text-[clamp(2.25rem,7vw,4.5rem)] text-panel-ink">
			{landing.headline}
		</h1>

		<p class="mt-6 max-w-xl text-lg leading-relaxed text-panel-muted sm:text-xl">
			{landing.sub}
		</p>

		<div class="mt-10 flex flex-wrap items-center gap-3">
			<Button href="/check" size="lg" invert arrow>{landing.startCheck}</Button>
			<Button href="/demo" size="lg" variant="secondary" invert>{landing.seeDemo}</Button>
			<Button href="/advocate" variant="quiet" invert>{landing.advocate}</Button>
		</div>

		<p class="mt-8 flex items-center gap-2 text-sm text-panel-muted">
			<svg viewBox="0 0 24 24" class="size-4 shrink-0" fill="none" aria-hidden="true">
				<path
					d="M12 3 4.5 6v6c0 4.2 3.2 8.1 7.5 9 4.3-.9 7.5-4.8 7.5-9V6L12 3Z"
					stroke="currentColor"
					stroke-width="1.6"
					stroke-linejoin="round"
				/>
				<path d="m9 12 2 2 4-4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
			</svg>
			{landing.privacyBadge}
		</p>
	</div>
</section>

<!-- ## The strip the reference fills with client logos -->
<section class="border-b border-line bg-surface">
	<div class="st-shell flex flex-wrap items-center gap-x-8 gap-y-3 py-6">
		<p class="st-eyebrow shrink-0">{landing.groundedTitle}</p>
		<ul class="flex flex-wrap items-center gap-x-6 gap-y-2">
			{#each landing.grounded as provision (provision)}
				<li class="text-sm font-medium tracking-[-0.01em] text-muted">{provision}</li>
			{/each}
		</ul>
	</div>
</section>

<div class="st-shell space-y-16 py-16 sm:space-y-24 sm:py-24">
	<!-- ## Three steps -->
	<Section eyebrow="How it works" index="01" rule={false}>
		<ol class="grid gap-px overflow-hidden rounded-card bg-line sm:grid-cols-3">
			{#each landing.steps as step, i (step.title)}
				<li class="flex flex-col bg-canvas p-6 sm:p-7">
					<span class="st-eyebrow tabular-nums">{String(i + 1).padStart(2, '0')}</span>
					<h2 class="st-display-sm mt-4 text-xl">{step.title}</h2>
					<p class="mt-2.5 text-sm leading-relaxed text-muted">{step.body}</p>
				</li>
			{/each}
		</ol>
	</Section>

	<!-- ## The technical angle, as the reference's statement paragraph -->
	<Section eyebrow="The idea" index="02">
		<h2 class="st-display text-2xl sm:text-4xl">{landing.angleTitle}</h2>
		<!--
			The reference's signature paragraph: the thesis in ink, the elaboration falling
			away to grey. One per page — a second would make the first mean nothing.

			`{@html}` is not used here and must not be. The emphasis is applied by splitting
			the string at its own first sentence, so the copy module stays plain text that
			`en.test.ts` can sweep for the rules in bible §6.
		-->
		<p class="st-statement mt-6 max-w-3xl">
			<strong>{landing.angleBody.split('. ')[0]}.</strong>
			{landing.angleBody.split('. ').slice(1).join('. ')}
		</p>
	</Section>

	<!-- ## Why it matters -->
	<Section eyebrow="The scale" index="03">
		<h2 class="st-display text-2xl sm:text-4xl">{landing.statsTitle}</h2>
		<p class="mt-5 max-w-2xl leading-relaxed text-muted">{landing.statsBody}</p>

		<ul class="mt-8 grid gap-4 sm:grid-cols-3">
			{#each landing.stats as stat, i (stat.value)}
				<li class="contents">
					<StatTile value={stat.value} label={stat.label} source={stat.source} invert={i === 1} />
				</li>
			{/each}
		</ul>
	</Section>

	<!-- ## What this is not -->
	<Section eyebrow="Straight answers" index="04">
		<h2 class="st-display text-2xl sm:text-4xl">{landing.trustTitle}</h2>
		<ul class="mt-8 divide-y divide-line border-y border-line">
			{#each landing.trustPoints as point, i (point)}
				<li class="flex gap-5 py-5">
					<span aria-hidden="true" class="st-eyebrow shrink-0 pt-1 tabular-nums">
						{String(i + 1).padStart(2, '0')}
					</span>
					<p class="leading-relaxed text-muted">{point}</p>
				</li>
			{/each}
		</ul>
	</Section>

	<!-- ## Closing call to action -->
	<section class="st-panel st-iridescent">
		<div class="flex flex-col gap-8 p-8 sm:flex-row sm:items-end sm:justify-between sm:p-12">
			<div>
				<Eyebrow>{landing.demoTitle}</Eyebrow>
				<p class="st-display mt-4 max-w-lg text-2xl text-panel-ink sm:text-3xl">
					{landing.demoBody}
				</p>
			</div>
			<div class="flex shrink-0 flex-wrap gap-3">
				<Button href="/demo" size="lg" invert arrow>{landing.seeDemo}</Button>
				<Button href="/check" size="lg" variant="secondary" invert>{landing.startCheck}</Button>
			</div>
		</div>
	</section>
</div>
