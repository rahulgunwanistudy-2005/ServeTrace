<script lang="ts">
	/**
	 * A card is a quieter rectangle of the same paper, not a white slab floating on grey.
	 *
	 * That inversion — surface *below* canvas rather than above it — is the reference's
	 * central move, and it is why there is no border and no shadow here by default. A
	 * page of bordered, shadowed boxes reads as a form; a page of tonal blocks reads as a
	 * document, which is what this is.
	 *
	 * A tone still puts a coloured rule down the leading edge rather than tinting the
	 * whole card: a page of tinted blocks stops meaning anything, and the rule still
	 * reads at AA.
	 */
	import type { Snippet } from 'svelte';
	import { toneEdge, type Tone } from './tone';

	let {
		tone,
		padded = true,
		raised = false,
		children
	}: {
		tone?: Tone;
		padded?: boolean;
		/** For the few things that genuinely sit on top of the page rather than in it. */
		raised?: boolean;
		children: Snippet;
	} = $props();
</script>

<section
	class="rounded-card {raised ? 'bg-raised shadow-card' : 'bg-surface'}
	       {padded ? 'p-5 sm:p-6' : ''}
	       {tone ? `border-l-2 ${toneEdge[tone]}` : ''}"
>
	{@render children()}
</section>
