<script lang="ts">
	import { advocate } from '$copy/en';
	import AdvocateMap from '$lib/map/AdvocateMap.svelte';
</script>

<svelte:head><title>{advocate.title}</title></svelte:head>

<h1 class="text-2xl font-semibold tracking-tight sm:text-3xl">{advocate.title}</h1>
<p class="mt-3 text-slate-700">{advocate.sub}</p>
<p class="mt-2 text-slate-700">{advocate.upload}</p>

<div class="mt-6"><AdvocateMap /></div>

<p class="mt-6 rounded-lg bg-slate-50 p-4 text-sm text-slate-700">{advocate.dcwpNote}</p>
<p class="mt-8 text-sm text-slate-500">Batch analysis arrives in session 4.</p>
