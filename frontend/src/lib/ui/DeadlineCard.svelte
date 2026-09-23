<script lang="ts">
	import type { Deadlines } from '$lib/api/client';
	import { deadlines as copy } from '$copy/en';
	import { formatDate } from './tone';

	let { deadlines }: { deadlines: Deadlines } = $props();

	const dates = $derived(
		[
			{ label: copy.fromLearning, value: deadlines.cplr_317_deadline },
			{ label: copy.fromEntry, value: deadlines.cplr_317_outer_limit }
		].filter((d) => d.value)
	);
</script>

<section class="rounded-card border border-line bg-surface p-5 shadow-card sm:p-6">
	<h2 class="text-xl font-semibold">{copy.title}</h2>

	{#if dates.length > 0}
		<dl class="mt-4 grid gap-3 sm:grid-cols-2">
			{#each dates as entry (entry.label)}
				<div class="rounded-lg border border-line bg-sunken p-4">
					<dt class="text-xs font-semibold tracking-wide text-muted uppercase">{entry.label}</dt>
					<dd class="mt-1 text-lg font-semibold tabular-nums">{formatDate(entry.value!)}</dd>
				</div>
			{/each}
		</dl>
	{/if}

	<!-- The note is generated server-side from bible §5 L5 and L6, so it is shown as it
	     came and never paraphrased here. -->
	<p class="mt-4 text-sm leading-relaxed text-muted">{deadlines.note}</p>
</section>
