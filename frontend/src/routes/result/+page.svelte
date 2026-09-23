<script lang="ts">
	import Callout from '$lib/ui/Callout.svelte';
	import LimitationNote from '$lib/ui/LimitationNote.svelte';
	import { result } from '$copy/en';
</script>

<svelte:head><title>{result.findings} — ServeTrace</title></svelte:head>

<div class="max-w-2xl">
	<h1 class="text-3xl font-semibold sm:text-4xl">{result.findings}</h1>
	<p class="mt-3 text-muted">{result.comingSoon}</p>
	<div class="mt-6"><Callout tone="accent">{result.comingSoonDetail}</Callout></div>
	<LimitationNote />
</div>
