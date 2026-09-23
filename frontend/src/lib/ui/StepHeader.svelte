<script lang="ts">
	/**
	 * Where you are in the three steps.
	 *
	 * The progress bar is a row of hairlines rather than a filled track: the reference
	 * counts things ("01/05") instead of filling them, and a counter is easier to read
	 * at a glance than a partly-shaded bar. The count is stated in words underneath for
	 * anyone the bar does not reach, and the bar itself is hidden from the reading order
	 * so it is not announced twice.
	 */
	let { step, total, title, hint }: { step: number; total: number; title: string; hint?: string } =
		$props();
</script>

<header class="mb-8 border-b border-line pb-7">
	<div class="flex items-baseline gap-3">
		<p class="st-eyebrow shrink-0">
			<span class="text-ink">{String(step).padStart(2, '0')}</span>
			<span class="opacity-60">/ {String(total).padStart(2, '0')}</span>
		</p>
		<div class="flex flex-1 items-center gap-1.5" aria-hidden="true">
			{#each { length: total } as _, i (i)}
				<span class="h-0.5 flex-1 rounded-full {i < step ? 'bg-accent' : 'bg-line'}"></span>
			{/each}
		</div>
	</div>

	<h1 class="st-display mt-5 text-3xl sm:text-4xl">{title}</h1>
	{#if hint}
		<p class="mt-3 max-w-xl text-base leading-relaxed text-muted">{hint}</p>
	{/if}
</header>
