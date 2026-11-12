<script lang="ts">
	import { changelogPage as copy, nav } from '$copy/en';
	import { releases } from '$lib/changelog';
	import { spans } from '$lib/changelog/parse';
	import Eyebrow from '$lib/ui/Eyebrow.svelte';
</script>

<svelte:head><title>{copy.title} — ServeTrace</title></svelte:head>

<div class="st-shell st-shell-prose">
	<Eyebrow>{nav.changelog}</Eyebrow>
	<h1 class="st-display mt-5 text-3xl sm:text-5xl">{copy.title}</h1>
	<p class="mt-5 text-lg leading-relaxed text-muted">{copy.intro}</p>

	<article class="prose-st mt-10" id="changelog">
		{#each releases as release (release.version)}
			<section id={`v${release.version}`}>
				<h2>
					<span class="tabular-nums">{release.version}</span>
					<span class="text-base font-normal text-muted">· <time datetime={release.date}>{release.date}</time></span>
				</h2>
				{#each release.sections as section (section.title)}
					<h3>{section.title}</h3>
					<ul>
						{#each section.items as item, i (i)}
							<li>
								{#each spans(item) as part, j (j)}{#if part.code}<code>{part.text}</code>{:else}{part.text}{/if}{/each}
							</li>
						{/each}
					</ul>
				{/each}
			</section>
		{/each}
	</article>
</div>
