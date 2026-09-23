<script lang="ts">
	import Button from '$lib/ui/Button.svelte';
	import Callout from '$lib/ui/Callout.svelte';
	import { landing, site } from '$copy/en';
</script>

<svelte:head><title>{site.name} — {landing.headline}</title></svelte:head>

<section class="max-w-2xl">
	<p class="text-sm font-semibold tracking-wide text-accent uppercase">{site.name}</p>
	<h1 class="mt-3 text-3xl leading-tight font-semibold sm:text-5xl">{landing.headline}</h1>
	<p class="mt-4 text-lg leading-relaxed text-muted sm:text-xl">{landing.sub}</p>

	<div class="mt-8 flex flex-wrap gap-3">
		<Button href="/check" size="lg">{landing.startCheck}</Button>
		<Button href="/demo" variant="secondary" size="lg">{landing.seeDemo}</Button>
		<Button href="/advocate" variant="quiet">{landing.advocate}</Button>
	</div>

	<p class="mt-6 text-sm text-muted">
		<span aria-hidden="true">🔒</span>
		{landing.privacyBadge}
	</p>
</section>

<ol class="mt-14 grid gap-4 sm:grid-cols-3">
	{#each landing.steps as step, i (step.title)}
		<li class="rounded-card border border-line bg-surface p-5 shadow-card">
			<span
				class="flex size-8 items-center justify-center rounded-full bg-accent-quiet
				       text-sm font-semibold text-accent"
			>
				{i + 1}
			</span>
			<h2 class="mt-3 font-semibold">{step.title}</h2>
			<p class="mt-1.5 text-sm leading-relaxed text-muted">{step.body}</p>
		</li>
	{/each}
</ol>

<section class="mt-14 max-w-3xl">
	<h2 class="text-xl font-semibold sm:text-2xl">{landing.angleTitle}</h2>
	<p class="mt-3 leading-relaxed text-muted">{landing.angleBody}</p>
</section>

<section class="mt-12 max-w-3xl">
	<Callout tone="neutral" title={landing.trustTitle}>
		<ul class="mt-2 space-y-1.5">
			{#each landing.trustPoints as point (point)}
				<li class="flex gap-2">
					<span aria-hidden="true" class="mt-2 size-1 shrink-0 rounded-full bg-current"></span>
					<span>{point}</span>
				</li>
			{/each}
		</ul>
	</Callout>
</section>
