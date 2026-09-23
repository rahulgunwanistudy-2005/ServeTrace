<script lang="ts">
	import Button from '$lib/ui/Button.svelte';
	import { landing, site } from '$copy/en';
</script>

<svelte:head><title>{site.name} — {landing.headline}</title></svelte:head>

<section class="max-w-2xl">
	<h1 class="text-3xl font-semibold tracking-tight sm:text-4xl">{landing.headline}</h1>
	<p class="mt-4 text-lg text-slate-700">{landing.sub}</p>

	<div class="mt-8 flex flex-wrap gap-3">
		<Button href="/check">{landing.startCheck}</Button>
		<Button href="/demo" variant="secondary">{landing.seeDemo}</Button>
		<Button href="/advocate" variant="quiet">{landing.advocate}</Button>
	</div>

	<p class="mt-8 rounded-lg bg-slate-50 p-4 text-sm text-slate-700">{landing.privacyBadge}</p>
</section>
