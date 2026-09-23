<script lang="ts">
	/**
	 * The small uppercase label that names a section.
	 *
	 * It is a `<p>` and never a heading. It reads like one, but a screen reader walking
	 * the heading outline should find "How this works", not "SECTION 02 · HOW THIS WORKS"
	 * — the ordinal is wayfinding for the eye and noise for the ear, so it is hidden from
	 * the accessibility tree and the label itself is left plain.
	 */
	import type { Snippet } from 'svelte';

	let { index, children }: { index?: string; children: Snippet } = $props();
</script>

<p class="st-eyebrow flex items-center gap-2">
	{#if index}
		<span aria-hidden="true" class="tabular-nums opacity-70">{index}</span>
		<span aria-hidden="true" class="h-px w-4 bg-current opacity-40"></span>
	{/if}
	{@render children()}
</p>
