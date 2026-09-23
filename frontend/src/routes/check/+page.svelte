<script lang="ts">
	import Callout from '$lib/ui/Callout.svelte';
	import StepHeader from '$lib/ui/StepHeader.svelte';
	import { steps, upload } from '$copy/en';
</script>

<svelte:head><title>{steps.one.title} — ServeTrace</title></svelte:head>

<div class="max-w-2xl">
	<StepHeader step={1} total={3} title={steps.one.title} hint={steps.one.hint} />

	<p class="text-muted">{upload.prompt}</p>

	<details class="mt-5 rounded-card border border-line bg-surface p-5 shadow-card">
		<summary class="cursor-pointer font-medium">{upload.whereDoIGetIt}</summary>
		<p class="mt-2 leading-relaxed text-muted">{upload.whereDoIGetItBody}</p>
	</details>

	<div class="mt-8">
		<Callout tone="accent">{upload.comingSoon}</Callout>
	</div>
</div>
