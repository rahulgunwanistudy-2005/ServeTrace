<script lang="ts">
	import '../app.css';
	import { nav, site } from '$copy/en';
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();
</script>

<div class="flex min-h-dvh flex-col">
	<header class="border-b border-slate-200">
		<nav class="mx-auto flex max-w-3xl items-center justify-between gap-4 px-4 py-3">
			<a href="/" class="font-semibold tracking-tight">{site.name}</a>
			<div class="flex gap-4 text-sm">
				<a class="underline underline-offset-4" href="/methodology">{nav.methodology}</a>
				<a class="underline underline-offset-4" href="/privacy">{nav.privacy}</a>
			</div>
		</nav>
	</header>

	<main class="mx-auto w-full max-w-3xl flex-1 px-4 py-8">{@render children()}</main>

	<footer class="border-t border-slate-200 px-4 py-6">
		<p class="mx-auto max-w-3xl text-sm text-slate-600">{site.tagline}</p>
	</footer>
</div>
