<script lang="ts">
	/**
	 * A page section, set the way the reference sets one: a hairline across the full
	 * measure, the eyebrow held in a narrow left column, and the content in a wide column
	 * beside it.
	 *
	 * The two columns collapse to one below `md`. That is not a concession — on a phone
	 * the eyebrow simply sits above its heading, which is the same reading order the
	 * markup already has, so nothing has to be reordered or duplicated.
	 */
	import type { Snippet } from 'svelte';
	import Eyebrow from './Eyebrow.svelte';

	let {
		eyebrow,
		index,
		rule = true,
		children
	}: { eyebrow?: string; index?: string; rule?: boolean; children: Snippet } = $props();
</script>

<section class={rule ? 'border-t border-line pt-8 sm:pt-10' : ''}>
	<div class="grid gap-x-8 gap-y-5 md:grid-cols-[12rem_minmax(0,1fr)]">
		<div>
			{#if eyebrow}<Eyebrow {index}>{eyebrow}</Eyebrow>{/if}
		</div>
		<div class="min-w-0">{@render children()}</div>
	</div>
</section>
