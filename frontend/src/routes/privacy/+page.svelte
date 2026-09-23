<script lang="ts">
	import Callout from '$lib/ui/Callout.svelte';
	import { nav, privacy as copy } from '$copy/en';
</script>

<svelte:head><title>{nav.privacy} — ServeTrace</title></svelte:head>

<article class="prose-st max-w-3xl">
	<h1 class="text-3xl font-semibold sm:text-4xl">{nav.privacy}</h1>
	<p class="text-lg">{copy.intro}</p>

	<Callout tone="consistent" title={copy.shortVersionTitle}>{copy.shortVersion}</Callout>

	<h2>{copy.whatStaysTitle}</h2>
	<ul>
		{#each copy.whatStays as point (point)}<li>{point}</li>{/each}
	</ul>

	<h2>{copy.whatLeavesTitle}</h2>
	<ul>
		{#each copy.whatLeaves as point (point)}<li>{point}</li>{/each}
	</ul>

	<h2>{copy.serverTitle}</h2>
	<ul>
		{#each copy.server as point (point)}<li>{point}</li>{/each}
	</ul>

	<!-- Session 3 found this and wrote it down rather than leaving it for someone else. -->
	<h2>{copy.mapTitle}</h2>
	<p>{copy.mapBody}</p>

	<h2>{copy.notDoneTitle}</h2>
	<ul>
		{#each copy.notDone as point (point)}<li>{point}</li>{/each}
	</ul>
</article>
