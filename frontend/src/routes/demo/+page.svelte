<script lang="ts">
	import DemoChip from '$lib/ui/DemoChip.svelte';
	import { demo } from '$copy/en';
</script>

<svelte:head><title>Demo</title></svelte:head>

<DemoChip />
<h1 class="mt-4 text-2xl font-semibold tracking-tight sm:text-3xl">Demo cases</h1>
<p class="mt-3 text-slate-700">{demo.note}</p>

<ul class="mt-6 space-y-2 text-slate-700">
	<li>Maria — her data conflicts with the affidavit.</li>
	<li>James — his data is consistent with the affidavit.</li>
	<li>Lin — affix and mail, with a thin pattern of prior attempts.</li>
</ul>

<p class="mt-8 text-sm text-slate-500">The bundled demo walkthrough arrives in session 5.</p>
