<script lang="ts">
	import type { Snippet } from 'svelte';
	import { toneEdge, type Tone } from './tone';

	let {
		tone,
		padded = true,
		children
	}: { tone?: Tone; padded?: boolean; children: Snippet } = $props();
</script>

<!-- A tone puts a coloured rule down the leading edge rather than tinting the whole card:
     a page of tinted blocks stops meaning anything, and the rule still reads at AA. -->
<section
	class="rounded-card border border-line bg-surface shadow-card {padded ? 'p-5 sm:p-6' : ''}
	       {tone ? `border-l-4 ${toneEdge[tone]}` : ''}"
>
	{@render children()}
</section>
