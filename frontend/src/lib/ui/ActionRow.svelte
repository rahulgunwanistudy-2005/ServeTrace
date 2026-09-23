<script lang="ts">
	/**
	 * The reference's card footer: a label on the left, a square arrow button on the
	 * right, the whole bar one target.
	 *
	 * It is a real `<a>` or `<button>` rather than a div with a click handler, so it is
	 * reachable by keyboard and announced as what it is. The arrow is decorative — the
	 * label carries the meaning.
	 */
	let {
		href,
		label,
		onclick,
		disabled = false,
		invert = false
	}: {
		href?: string;
		label: string;
		onclick?: () => void;
		disabled?: boolean;
		invert?: boolean;
	} = $props();

	const shell =
		'group flex min-h-12 w-full items-center justify-between gap-3 rounded-control ' +
		'px-4 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50';
	// `$derived`, not a plain const: a plain one would capture whichever value `invert`
	// had when the component was created and never follow it afterwards.
	const skin = $derived(
		invert
			? 'bg-panel-ink/10 text-panel-ink hover:bg-panel-ink/20'
			: 'bg-sunken text-ink hover:bg-accent-quiet'
	);
	const knob = $derived(invert ? 'bg-panel-ink text-panel' : 'bg-accent text-on-accent');
</script>

{#snippet inner()}
	<span>{label}</span>
	<span
		aria-hidden="true"
		class="grid size-7 shrink-0 place-items-center rounded-md transition-transform
		       group-hover:translate-x-0.5 {knob}"
	>
		<svg viewBox="0 0 16 16" class="size-3.5" fill="none" aria-hidden="true">
			<path
				d="M3 8h10m0 0-4-4m4 4-4 4"
				stroke="currentColor"
				stroke-width="1.6"
				stroke-linecap="round"
				stroke-linejoin="round"
			/>
		</svg>
	</span>
{/snippet}

{#if href}
	<a {href} class="{shell} {skin}">{@render inner()}</a>
{:else}
	<button type="button" {onclick} {disabled} class="{shell} {skin}">{@render inner()}</button>
{/if}
