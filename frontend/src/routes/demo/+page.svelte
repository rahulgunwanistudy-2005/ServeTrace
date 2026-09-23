<script lang="ts">
	import Button from '$lib/ui/Button.svelte';
	import DemoChip from '$lib/ui/DemoChip.svelte';
	import TierBadge from '$lib/ui/TierBadge.svelte';
	import { demo } from '$copy/en';
</script>

<svelte:head><title>Demo — ServeTrace</title></svelte:head>

<DemoChip />
<h1 class="mt-4 text-3xl font-semibold sm:text-4xl">{demo.title}</h1>
<p class="mt-3 max-w-2xl text-lg text-muted">{demo.note}</p>

<ul class="mt-8 grid gap-4 sm:grid-cols-3">
	{#each demo.cases as demoCase (demoCase.id)}
		<li class="flex flex-col rounded-card border border-line bg-surface p-5 shadow-card">
			<TierBadge tier={demoCase.tier} size="sm" />
			<h2 class="mt-3 font-semibold">{demoCase.name}</h2>
			<p class="mt-1.5 grow text-sm leading-relaxed text-muted">{demoCase.summary}</p>
		</li>
	{/each}
</ul>

<p class="mt-8 text-sm text-muted">{demo.comingSoon}</p>
<div class="mt-4"><Button href="/check">Start your own check</Button></div>
