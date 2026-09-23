<script lang="ts">
	import Callout from '$lib/ui/Callout.svelte';
	import { advocate } from '$copy/en';
</script>

<svelte:head><title>{advocate.title} — ServeTrace</title></svelte:head>

<div class="max-w-2xl">
	<h1 class="text-3xl font-semibold sm:text-4xl">{advocate.title}</h1>
	<p class="mt-3 text-lg text-muted">{advocate.sub}</p>
	<p class="mt-3 text-muted">{advocate.upload}</p>

	<div class="mt-8 space-y-4">
		<Callout tone="accent" title={advocate.gpsTitle}>{advocate.dcwpNote}</Callout>
		<Callout tone="neutral">{advocate.comingSoon}</Callout>
	</div>
</div>
