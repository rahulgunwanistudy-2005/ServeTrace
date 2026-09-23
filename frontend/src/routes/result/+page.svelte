<script lang="ts">
	import LimitationNote from '$lib/ui/LimitationNote.svelte';
	import ResultMap from '$lib/map/ResultMap.svelte';
	import { result } from '$copy/en';
</script>

<svelte:head><title>{result.findings}</title></svelte:head>

<h1 class="text-2xl font-semibold tracking-tight sm:text-3xl">{result.findings}</h1>

<div class="mt-6">
	<ResultMap />
</div>

<LimitationNote />

<p class="mt-8 text-sm text-slate-500">Verdicts and documents arrive in sessions 3 to 5.</p>
