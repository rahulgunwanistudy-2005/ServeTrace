<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		href,
		variant = 'primary',
		type = 'button',
		onclick,
		children
	}: {
		href?: string;
		variant?: 'primary' | 'secondary' | 'quiet';
		type?: 'button' | 'submit';
		onclick?: () => void;
		children: Snippet;
	} = $props();

	const base =
		'inline-flex min-h-11 items-center justify-center rounded-lg px-5 text-base font-medium transition';
	const styles = {
		primary: 'bg-slate-900 text-white hover:bg-slate-700',
		secondary: 'border border-slate-300 bg-white text-slate-900 hover:bg-slate-50',
		quiet: 'text-slate-700 underline underline-offset-4 hover:text-slate-900'
	} as const;
</script>

{#if href}
	<a {href} class="{base} {styles[variant]}">{@render children()}</a>
{:else}
	<button {type} {onclick} class="{base} {styles[variant]}">{@render children()}</button>
{/if}
