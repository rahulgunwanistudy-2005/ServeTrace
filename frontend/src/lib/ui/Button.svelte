<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		href,
		variant = 'primary',
		size = 'md',
		type = 'button',
		disabled = false,
		onclick,
		children
	}: {
		href?: string;
		variant?: 'primary' | 'secondary' | 'quiet';
		size?: 'md' | 'lg';
		type?: 'button' | 'submit';
		disabled?: boolean;
		onclick?: () => void;
		children: Snippet;
	} = $props();

	// 44px minimum on every variant: bible §14 is mobile-first, and a target smaller than
	// a thumb is a target Maria misses on a moving bus.
	const base =
		'inline-flex min-h-11 items-center justify-center gap-2 rounded-lg font-medium ' +
		'transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50';
	const sizes = { md: 'px-5 text-[0.9375rem]', lg: 'min-h-12 px-6 text-base' } as const;
	const styles = {
		primary: 'bg-accent text-canvas hover:bg-accent-hover shadow-sm',
		secondary: 'border border-line-strong bg-surface text-ink hover:bg-sunken',
		quiet: 'text-muted hover:text-ink underline underline-offset-4 decoration-line-strong'
	} as const;
</script>

{#if href}
	<a {href} class="{base} {sizes[size]} {styles[variant]}">{@render children()}</a>
{:else}
	<button {type} {onclick} {disabled} class="{base} {sizes[size]} {styles[variant]}">
		{@render children()}
	</button>
{/if}
