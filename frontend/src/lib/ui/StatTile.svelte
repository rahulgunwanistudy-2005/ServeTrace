<script lang="ts">
	/**
	 * One number, large, with what it is underneath and where it came from below that.
	 *
	 * The source line is not optional and is not a footnote. Bible §2 stakes the whole
	 * impact argument on published figures, and a statistic on a landing page without its
	 * source is exactly the kind of claim this product exists to be sceptical of.
	 */
	let {
		value,
		label,
		source,
		invert = false
	}: { value: string; label: string; source?: string; invert?: boolean } = $props();
</script>

<div
	class="flex flex-col rounded-card p-5 sm:p-6
	       {invert ? 'st-panel st-iridescent' : 'bg-surface'}"
>
	<p class="st-display text-4xl tabular-nums sm:text-5xl">{value}</p>
	<p class="mt-3 grow text-sm leading-relaxed {invert ? 'text-panel-muted' : 'text-muted'}">
		{label}
	</p>
	{#if source}
		<p class="mt-4 text-xs {invert ? 'text-panel-muted opacity-80' : 'text-faint'}">{source}</p>
	{/if}
</div>
