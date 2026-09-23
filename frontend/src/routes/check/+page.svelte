<script lang="ts">
	import StepHeader from '$lib/ui/StepHeader.svelte';
	import { steps, upload } from '$copy/en';
</script>

<svelte:head><title>{steps.one.title}</title></svelte:head>

<StepHeader step={1} total={3} title={steps.one.title} hint={steps.one.hint} />

<p class="text-slate-700">{upload.prompt}</p>

<details class="mt-4 rounded-lg border border-slate-200 p-4">
	<summary class="cursor-pointer font-medium">{upload.whereDoIGetIt}</summary>
	<p class="mt-2 text-slate-700">{upload.whereDoIGetItBody}</p>
</details>

<p class="mt-8 text-sm text-slate-500">Upload and extraction arrive in session 2.</p>
