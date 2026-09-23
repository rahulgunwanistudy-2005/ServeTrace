<script lang="ts">
	import '../app.css';
	import { dev } from '$app/environment';
	import { page } from '$app/stores';
	import { DRAFT_BANNER, nav, site } from '$copy/en';
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();

	const links = [
		{ href: '/check', label: 'Start check' },
		{ href: '/advocate', label: nav.advocate },
		{ href: '/methodology', label: nav.methodology },
		{ href: '/privacy', label: nav.privacy }
	];
	const current = $derived($page.url.pathname);
</script>

<div class="flex min-h-dvh flex-col">
	<a
		href="#main"
		class="sr-only focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-50
		       focus:rounded-lg focus:bg-surface focus:px-4 focus:py-2 focus:shadow-card"
	>
		Skip to content
	</a>

	<header class="sticky top-0 z-30 border-b border-line bg-canvas/85 backdrop-blur">
		<nav
			aria-label="Main"
			class="mx-auto flex max-w-4xl flex-wrap items-center gap-x-5 gap-y-2 px-4 py-3"
		>
			<a href="/" class="flex items-center gap-2 font-semibold tracking-tight">
				<!-- A pin with a line through it: a claimed place, and a track that disagrees. -->
				<svg viewBox="0 0 24 24" class="size-5 text-accent" aria-hidden="true" fill="none">
					<path
						d="M12 21s7-6.2 7-11a7 7 0 1 0-14 0c0 4.8 7 11 7 11Z"
						stroke="currentColor"
						stroke-width="1.7"
					/>
					<circle cx="12" cy="10" r="2.4" fill="currentColor" />
					<path d="M3 20.5 21 3" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
				</svg>
				{site.name}
			</a>

			<div class="ml-auto flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
				{#each links as link (link.href)}
					<a
						href={link.href}
						aria-current={current === link.href ? 'page' : undefined}
						class="py-1 transition-colors hover:text-ink
						       {current === link.href ? 'font-medium text-ink' : 'text-muted'}"
					>
						{link.label}
					</a>
				{/each}
				{#if dev}
					<!-- Development only. Both routes refuse to render in a production build. -->
					<a class="py-1 text-muted" href="/dev/ingest">Ingest</a>
					<a class="py-1 text-muted" href="/dev/analyze">Analyze</a>
				{/if}
			</div>
		</nav>
	</header>

	<main id="main" class="mx-auto w-full max-w-4xl flex-1 px-4 py-8 sm:py-12">
		{@render children()}
	</main>

	<footer class="mt-8 border-t border-line bg-sunken">
		<div class="mx-auto max-w-4xl space-y-2 px-4 py-8 text-sm text-muted">
			<p class="font-medium text-ink">{site.tagline}</p>
			<p>{DRAFT_BANNER}</p>
			<p class="flex flex-wrap gap-x-4 gap-y-1 pt-2">
				<a class="underline underline-offset-4" href="/methodology">{nav.methodology}</a>
				<a class="underline underline-offset-4" href="/privacy">{nav.privacy}</a>
			</p>
		</div>
	</footer>
</div>
