<script lang="ts">
	/**
	 * Pills, after the reference's "Book a Call".
	 *
	 * `primary` is ink on paper and paper on ink — one rule, both colour schemes, because
	 * `--st-accent` and `--st-on-accent` invert together. That is why there is no `dark:`
	 * class anywhere in this file.
	 *
	 * `invert` is for the dark panel, which keeps its own scheme regardless of the
	 * reader's: on it the primary pill has to be light whatever the page around it is
	 * doing.
	 */
	import type { Snippet } from 'svelte';

	let {
		href,
		variant = 'primary',
		size = 'md',
		type = 'button',
		disabled = false,
		arrow = false,
		invert = false,
		onclick,
		children
	}: {
		href?: string;
		variant?: 'primary' | 'secondary' | 'quiet';
		size?: 'md' | 'lg';
		type?: 'button' | 'submit';
		disabled?: boolean;
		/** The reference's trailing arrow. Decorative; the label carries the meaning. */
		arrow?: boolean;
		/** Sitting on `.st-panel`, which is dark in both schemes. */
		invert?: boolean;
		onclick?: () => void;
		children: Snippet;
	} = $props();

	// 44px minimum on every variant: bible §14 is mobile-first, and a target smaller than
	// a thumb is a target Maria misses on a moving bus.
	const base =
		'group inline-flex min-h-11 items-center justify-center gap-2 rounded-full font-medium ' +
		'tracking-[-0.01em] transition-colors duration-150 ' +
		'disabled:cursor-not-allowed disabled:opacity-50';
	const sizes = {
		md: 'px-5 text-[0.9375rem]',
		lg: 'min-h-12 px-6 text-base'
	} as const;

	const page = {
		primary: 'bg-accent text-on-accent hover:bg-accent-hover',
		secondary: 'border border-line-strong text-ink hover:bg-surface',
		quiet: 'text-muted underline decoration-line-strong underline-offset-4 hover:text-ink'
	} as const;

	const panel = {
		primary: 'bg-panel-ink text-panel hover:bg-panel-ink/85',
		secondary: 'border border-panel-line text-panel-ink hover:bg-panel-ink/10',
		quiet: 'text-panel-muted underline decoration-panel-line underline-offset-4 hover:text-panel-ink'
	} as const;

	const skin = $derived((invert ? panel : page)[variant]);
</script>

{#snippet inner()}
	{@render children()}
	{#if arrow}
		<svg
			viewBox="0 0 16 16"
			class="size-3.5 shrink-0 transition-transform group-hover:translate-x-0.5"
			fill="none"
			aria-hidden="true"
		>
			<path
				d="M3 8h10m0 0-4-4m4 4-4 4"
				stroke="currentColor"
				stroke-width="1.7"
				stroke-linecap="round"
				stroke-linejoin="round"
			/>
		</svg>
	{/if}
{/snippet}

{#if href}
	<a {href} class="{base} {sizes[size]} {skin}">{@render inner()}</a>
{:else}
	<button {type} {onclick} {disabled} class="{base} {sizes[size]} {skin}">
		{@render inner()}
	</button>
{/if}
