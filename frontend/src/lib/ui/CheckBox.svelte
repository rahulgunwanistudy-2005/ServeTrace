<script lang="ts">
	/**
	 * A tick, with the sentence it gates beside it.
	 *
	 * Deliberately large: bible §14 asks for large tap targets, and every tick in this
	 * product gates something consequential — whether analysis may run at all, or whether
	 * a paragraph appears in a document somebody signs under oath.
	 */
	import type { Snippet } from 'svelte';

	let {
		id,
		checked = $bindable(false),
		label,
		hint,
		children
	}: {
		id: string;
		checked?: boolean;
		label?: string;
		hint?: string;
		children?: Snippet;
	} = $props();
</script>

<div class="flex gap-3">
	<input
		{id}
		type="checkbox"
		bind:checked
		class="mt-0.5 size-5 shrink-0 accent-ink"
		aria-describedby={hint ? `${id}-hint` : undefined}
	/>
	<div class="min-w-0">
		<label class="block text-sm leading-relaxed" for={id}>
			{#if children}{@render children()}{:else}{label}{/if}
		</label>
		{#if hint}
			<p id="{id}-hint" class="mt-1 text-xs leading-relaxed text-faint">{hint}</p>
		{/if}
	</div>
</div>
