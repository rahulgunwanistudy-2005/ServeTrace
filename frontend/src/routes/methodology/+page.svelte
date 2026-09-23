<script lang="ts">
	import { deadlines, nav } from '$copy/en';
</script>

<svelte:head><title>{nav.methodology}</title></svelte:head>

<h1 class="text-2xl font-semibold tracking-tight sm:text-3xl">{nav.methodology}</h1>

<p class="mt-4 text-slate-700">
	How the check works, the thresholds it uses, how it scores against synthetic cases, and
	where it cannot help. Filled in once the engine and the eval exist.
</p>

<h2 class="mt-8 text-lg font-semibold">The law this encodes</h2>
<p class="mt-2 text-slate-700">{deadlines.cplr5015}</p>
<p class="mt-2 text-slate-700">{deadlines.cplr317}</p>
<p class="mt-2 text-slate-700">{deadlines.traverse}</p>

<p class="mt-8 text-sm text-slate-500">Thresholds, eval numbers and sources arrive in session 6.</p>
