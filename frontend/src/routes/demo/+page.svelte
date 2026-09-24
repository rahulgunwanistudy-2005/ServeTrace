<script lang="ts">
	/**
	 * The three bundled cases, one per tier the engine can reach for a main claim.
	 *
	 * Bible §16 wants a demo that never fails and never lies about what it is: the chip
	 * appears before the heading, and every card carries the tier it demonstrates, so a
	 * judge watching the video can see that the CONSISTENT case is shown with the same
	 * weight as the CONTRADICTED one rather than tucked away.
	 */
	import { goto } from '$app/navigation';
	import { caseStore } from '$lib/case/store.svelte';
	import { loadDemoCase, type DemoCaseId } from '$lib/demo/cases';
	import ActionRow from '$lib/ui/ActionRow.svelte';
	import Button from '$lib/ui/Button.svelte';
	import Callout from '$lib/ui/Callout.svelte';
	import Eyebrow from '$lib/ui/Eyebrow.svelte';
	import IridescentField from '$lib/ui/IridescentField.svelte';
	import TierBadge from '$lib/ui/TierBadge.svelte';
	import { demo } from '$copy/en';

	let opening = $state<DemoCaseId | null>(null);
	let failure = $state<string | null>(null);

	/**
	 * Load a committed case into the store and hand it to `/result`, which runs the engine.
	 *
	 * Nothing here is pre-recorded: the fixture supplies the inputs a person would have
	 * spent ten minutes providing, and every number on the next screen is computed by the
	 * same `POST /api/analyze` a real check uses. That is what makes this a demo of the
	 * product rather than a screenshot of one.
	 */
	async function open(id: DemoCaseId) {
		opening = id;
		failure = null;
		try {
			const loaded = await loadDemoCase(id);
			caseStore.reset();
			caseStore.affidavit = loaded.affidavit;
			caseStore.confirmed = true;
			caseStore.fixes = loaded.fixes;
			caseStore.household = loaded.household;
			caseStore.knowledgeDate = loaded.knowledgeDate;
			caseStore.judgmentDate = loaded.judgmentDate;
			caseStore.isDemo = true;
			await goto('/result');
		} catch {
			failure = demo.failed;
			opening = null;
		}
	}
</script>

<svelte:head><title>Demo — ServeTrace</title></svelte:head>

<section class="st-panel st-iridescent rounded-none">
	<IridescentField />
	<div class="st-shell py-14 sm:py-20">
		<!--
			No `DemoNote` here. This page's own `demo.note` below says everything that note
			says and says it better, and bible §16 asks each demo screen to disclose, not to
			disclose twice. `DemoNote` is for the screens that have no sentence of their own.
		-->
		<h1 class="st-display max-w-3xl text-3xl text-panel-ink sm:text-5xl">{demo.title}</h1>
		<p class="mt-5 max-w-2xl text-lg leading-relaxed text-panel-muted">{demo.note}</p>
	</div>
</section>

<div class="st-shell py-14 sm:py-20">
	<Eyebrow index="01">Three cases</Eyebrow>

	{#if failure}
		<div class="mt-6"><Callout tone="contradicted" title="That did not work">{failure}</Callout></div>
	{/if}

	<ul class="mt-6 grid gap-4 sm:grid-cols-3">
		{#each demo.cases as demoCase (demoCase.id)}
			<li class="flex flex-col rounded-card bg-surface p-6">
				<!-- Wrapped: a bare inline-flex badge would stretch to the column's width. -->
				<div><TierBadge tier={demoCase.tier} size="sm" /></div>
				<h2 class="st-display-sm mt-4 text-xl">{demoCase.name}</h2>
				<p class="mt-2.5 grow text-sm leading-relaxed text-muted">{demoCase.summary}</p>
				<div class="mt-5">
					<ActionRow
						label={opening === demoCase.id ? demo.opening : demo.open}
						disabled={opening !== null}
						onclick={() => open(demoCase.id as DemoCaseId)}
					/>
				</div>
			</li>
		{/each}
	</ul>

	<p class="mt-6 max-w-2xl text-sm leading-relaxed text-muted">{demo.runNote}</p>

	<div class="mt-12 border-t border-line pt-8">
		<div class="flex flex-wrap items-center gap-3">
			<Button href="/check" size="lg" arrow>Start your own check</Button>
			<div class="w-full max-w-xs"><ActionRow href="/methodology" label="How the check works" /></div>
		</div>
	</div>
</div>
