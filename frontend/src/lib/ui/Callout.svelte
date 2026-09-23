<script lang="ts">
	import type { Snippet } from 'svelte';
	import { toneClasses, type Tone } from './tone';

	let {
		tone = 'neutral',
		title,
		children
	}: { tone?: Tone; title?: string; children: Snippet } = $props();
</script>

<aside class="rounded-card border p-4 text-sm leading-relaxed {toneClasses[tone]}">
	{#if title}<p class="font-semibold">{title}</p>{/if}
	<div class={title ? 'mt-1' : ''}>{@render children()}</div>
</aside>
