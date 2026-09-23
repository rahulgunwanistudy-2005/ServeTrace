<script lang="ts">
	let { step, total, title, hint }: { step: number; total: number; title: string; hint?: string } =
		$props();
</script>

<header class="mb-6">
	<p class="text-sm font-medium text-slate-500">Step {step} of {total}</p>
	<h1 class="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
	{#if hint}
		<p class="mt-2 text-base text-slate-600">{hint}</p>
	{/if}
</header>
