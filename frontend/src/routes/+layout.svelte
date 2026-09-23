<script lang="ts">
	import '../app.css';
	import { dev } from '$app/environment';
	import { page } from '$app/stores';
	import { DRAFT_BANNER, nav, site } from '$copy/en';
	import Button from '$lib/ui/Button.svelte';
	import Eyebrow from '$lib/ui/Eyebrow.svelte';
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();

	/**
	 * The nav is grouped rather than listed, the way the reference's is: what you came to
	 * do, and what you might want to check about it. "Start check" is the pill on the
	 * right and so is not repeated in the list.
	 */
	const links = [
		{ href: '/demo', label: 'Demo' },
		{ href: '/advocate', label: nav.advocate },
		{ href: '/methodology', label: nav.methodology },
		{ href: '/privacy', label: nav.privacy }
	];
	const current = $derived($page.url.pathname);
	/** The landing page carries its own full-bleed hero, so it opens flush to the header. */
	const flush = $derived(current === '/');
</script>

<div class="flex min-h-dvh flex-col">
	<a
		href="#main"
		class="sr-only focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-50
		       focus:rounded-control focus:bg-raised focus:px-4 focus:py-2 focus:shadow-card"
	>
		Skip to content
	</a>

	<header class="sticky top-0 z-30 border-b border-line bg-canvas/80 backdrop-blur-md">
		<nav aria-label="Main" class="st-shell flex items-center gap-x-6 gap-y-2 py-3.5">
			<a href="/" class="flex shrink-0 items-center gap-2 text-[0.9375rem] font-semibold tracking-[-0.02em]">
				<!-- A pin with a line through it: a claimed place, and a track that disagrees. -->
				<svg viewBox="0 0 24 24" class="size-[1.125rem] text-ink" aria-hidden="true" fill="none">
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

			<!-- Horizontally scrollable rather than wrapped: a header that grows to three
			     lines on a narrow phone pushes the page's own heading below the fold. -->
			<div
				class="-mx-1 flex flex-1 items-center gap-x-5 overflow-x-auto px-1 text-sm
				       [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
			>
				{#each links as link (link.href)}
					<a
						href={link.href}
						aria-current={current === link.href ? 'page' : undefined}
						class="shrink-0 py-1 whitespace-nowrap transition-colors hover:text-ink
						       {current === link.href ? 'font-medium text-ink' : 'text-muted'}"
					>
						{link.label}
					</a>
				{/each}
				{#if dev}
					<!-- Development only. Both routes refuse to render in a production build. -->
					<a class="shrink-0 py-1 text-faint" href="/dev/ingest">Ingest</a>
					<a class="shrink-0 py-1 text-faint" href="/dev/analyze">Analyze</a>
				{/if}
			</div>

			<div class="hidden shrink-0 sm:block">
				<Button href="/check" arrow>Start check</Button>
			</div>
		</nav>
	</header>

	<main id="main" class="flex-1 {flush ? '' : 'py-10 sm:py-14'}">
		{@render children()}
	</main>

	<!--
		The footer is the reference's closing panel: dark in both colour schemes, the
		wordmark set enormous along the bottom, and the tagline as the one large statement.

		Where the reference puts an email address, this puts the draft banner. Bible §18
		forbids the product contacting anyone on the user's behalf, so an inviting
		`mailto:` would promise something that does not exist. The thing a person most
		needs to carry away from this page is that nothing here is legal advice.
	-->
	<footer class="st-panel st-iridescent mt-20 rounded-none">
		<div class="st-shell py-14 sm:py-16">
			<p class="st-display max-w-3xl text-2xl text-panel-ink sm:text-4xl">
				{site.tagline}
			</p>

			<div class="mt-12 grid gap-8 border-t border-panel-line pt-8 sm:grid-cols-3">
				<div>
					<Eyebrow>Start</Eyebrow>
					<ul class="mt-3 space-y-2 text-sm">
						<li><a class="text-panel-ink hover:underline underline-offset-4" href="/check">Check an affidavit</a></li>
						<li><a class="text-panel-ink hover:underline underline-offset-4" href="/demo">See a demo</a></li>
						<li><a class="text-panel-ink hover:underline underline-offset-4" href="/advocate">{nav.advocate}</a></li>
					</ul>
				</div>
				<div>
					<Eyebrow>Check our work</Eyebrow>
					<ul class="mt-3 space-y-2 text-sm">
						<li><a class="text-panel-ink hover:underline underline-offset-4" href="/methodology">{nav.methodology}</a></li>
						<li><a class="text-panel-ink hover:underline underline-offset-4" href="/privacy">{nav.privacy}</a></li>
					</ul>
				</div>
				<div>
					<Eyebrow>Where this applies</Eyebrow>
					<p class="mt-3 text-sm leading-relaxed text-panel-muted">
						New York City Civil Court, consumer credit cases. Service on a person under
						CPLR 308.
					</p>
				</div>
			</div>

			<p class="mt-10 max-w-2xl text-sm leading-relaxed text-panel-muted">{DRAFT_BANNER}</p>

			<!-- The oversized wordmark, cropped by the panel exactly as the reference crops
			     its own. Decorative: the name is already in the header and the page title. -->
			<p
				aria-hidden="true"
				class="st-display mt-12 -mb-4 text-[15vw] leading-[0.8] text-panel-ink/10 select-none sm:-mb-6"
			>
				{site.name}
			</p>
		</div>
	</footer>
</div>
