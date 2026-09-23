<script lang="ts">
	import type { Deadlines } from '$lib/api/client';
	import { deadlines as copy } from '$copy/en';
	import { formatDate } from './tone';
	import Eyebrow from './Eyebrow.svelte';

	let { deadlines }: { deadlines: Deadlines } = $props();

	const dates = $derived(
		[
			{ label: copy.fromLearning, value: deadlines.cplr_317_deadline },
			{ label: copy.fromEntry, value: deadlines.cplr_317_outer_limit }
		].filter((d) => d.value)
	);
</script>

<section class="rounded-card bg-surface p-5 sm:p-6">
	<Eyebrow>{copy.title}</Eyebrow>

	{#if dates.length > 0}
		<dl class="mt-4 grid gap-4 sm:grid-cols-2">
			{#each dates as entry (entry.label)}
				<div class="border-t border-line-strong pt-3">
					<dt class="text-xs font-medium text-faint">{entry.label}</dt>
					<dd class="st-display-sm mt-1.5 text-xl tabular-nums sm:text-2xl">
						{formatDate(entry.value!)}
					</dd>
				</div>
			{/each}
		</dl>
	{/if}

	<!-- The note is generated server-side from bible §5 L5 and L6, so it is shown as it
	     came and never paraphrased here. -->
	<p class="mt-5 text-sm leading-relaxed text-muted">{deadlines.note}</p>
</section>
