<script lang="ts">
	/**
	 * The global error boundary (bible-adjacent: S8's hardening item).
	 *
	 * SvelteKit renders this for any uncaught error in a page and for any route the
	 * client router cannot match. Without it the person gets SvelteKit's own white page
	 * reading "Internal Error", which on a product about a frozen bank account is the
	 * worst possible moment to look broken and anonymous.
	 *
	 * It composes the S6 primitives and adds no colour, no type scale and no component.
	 * It is also deliberately inert: no fetch, no store read, no map. A boundary that can
	 * itself throw is not a boundary.
	 */
	import { page } from '$app/stores';
	import { errorPage } from '$copy/en';
	import Button from '$lib/ui/Button.svelte';
	import Eyebrow from '$lib/ui/Eyebrow.svelte';

	const status = $derived($page.status);
	const notFound = $derived(status === 404);
	const title = $derived(notFound ? errorPage.title[404] : errorPage.title.default);
	const body = $derived(notFound ? errorPage.body[404] : errorPage.body.default);

	/**
	 * SvelteKit puts a `message` on every error, and for an unexpected one that message is
	 * whatever threw. It is shown as a reference rather than as prose because it is not
	 * written for a reader, and it is worth showing at all because it is the only thing a
	 * person can tell us when they say the screen went wrong.
	 */
	const reference = $derived($page.error?.message ?? '');

	function reload() {
		location.reload();
	}
</script>

<svelte:head><title>{title} — ServeTrace</title></svelte:head>

<div class="st-shell">
	<div class="max-w-xl">
		<Eyebrow>{errorPage.eyebrow}</Eyebrow>
		<h1 class="st-display mt-4 text-3xl sm:text-4xl">{title}</h1>
		<p class="mt-5 leading-relaxed text-muted">{body}</p>

		<div class="mt-8 flex flex-wrap items-center gap-3">
			{#if !notFound}
				<Button onclick={reload}>{errorPage.retry}</Button>
			{/if}
			<Button href="/" variant={notFound ? 'primary' : 'secondary'} arrow>
				{errorPage.home}
			</Button>
		</div>

		{#if reference}
			<p class="mt-10 border-t border-line pt-4 text-xs text-muted">
				{errorPage.referenceLabel}: <span class="font-mono">{status} {reference}</span>
			</p>
		{/if}
	</div>
</div>
