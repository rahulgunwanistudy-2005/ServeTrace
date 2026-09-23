<script lang="ts">
	let { step, total, title, hint }: { step: number; total: number; title: string; hint?: string } =
		$props();
</script>

<header class="mb-7">
	<div class="flex items-center gap-2" aria-hidden="true">
		{#each { length: total } as _, i (i)}
			<span
				class="h-1.5 flex-1 rounded-full {i < step ? 'bg-accent' : 'bg-line'}"
			></span>
		{/each}
	</div>
	<p class="mt-3 text-sm font-medium text-muted">Step {step} of {total}</p>
	<h1 class="mt-1 text-2xl font-semibold sm:text-3xl">{title}</h1>
	{#if hint}
		<p class="mt-2 text-base text-muted">{hint}</p>
	{/if}
</header>
