<script lang="ts">
	/**
	 * Confirming which column is which.
	 *
	 * The fields are already filled in by `guessColumns`, so this is a review rather than
	 * a form. It is split into what the analysis cannot run without and what makes it
	 * better, because an advocate who has to supply ten columns before seeing anything
	 * will close the tab.
	 */
	import type { AdvocateColumnMapping } from '$lib/api/client';
	import { advocate } from '$copy/en';
	import { FIELDS, isComplete, missingFields, type MappableField } from './mapping';

	let {
		headers,
		mapping = $bindable()
	}: { headers: string[]; mapping: AdvocateColumnMapping } = $props();

	/** Place before time, because a place is the one thing a file may express two ways. */
	const REQUIRED: MappableField[] = ['server_id', 'at', 'date', 'time', 'lat', 'lng', 'address'];
	const OPTIONAL: MappableField[] = FIELDS.filter((field) => !REQUIRED.includes(field));

	const missing = $derived(missingFields(mapping));
	const complete = $derived(isComplete(mapping));

	function set(field: MappableField, value: string) {
		// An unset field is absent rather than empty: the server reads `at: ""` and
		// `at: undefined` differently, and only one of them means "not in this file".
		const next = { ...mapping };
		if (value) next[field] = value;
		else delete next[field];
		mapping = next as AdvocateColumnMapping;
	}
</script>

{#snippet field(name: MappableField)}
	{@const hint = advocate.fieldHints[name as keyof typeof advocate.fieldHints]}
	<div>
		<label class="block text-sm font-medium" for="map-{name}">
			{advocate.fields[name]}
			{#if missing.includes(name)}
				<span class="ml-1 font-normal text-caution">·&nbsp;needed</span>
			{/if}
		</label>
		<select
			id="map-{name}"
			value={mapping[name] ?? ''}
			onchange={(event) => set(name, event.currentTarget.value)}
			class="mt-1.5 min-h-11 w-full rounded-control border border-line-strong bg-raised px-3
			       text-sm text-ink"
		>
			<option value="">{advocate.notMapped}</option>
			{#each headers as header (header)}
				<option value={header}>{header}</option>
			{/each}
		</select>
		{#if hint}<p class="mt-1.5 text-xs leading-relaxed text-faint">{hint}</p>{/if}
	</div>
{/snippet}

<div class="space-y-6">
	<div>
		<h3 class="st-eyebrow">{advocate.mapRequired}</h3>
		<div class="mt-3 grid gap-4 sm:grid-cols-2">
			{#each REQUIRED as name (name)}{@render field(name)}{/each}
		</div>
	</div>

	<div>
		<h3 class="st-eyebrow">{advocate.mapOptional}</h3>
		<div class="mt-3 grid gap-4 sm:grid-cols-2">
			{#each OPTIONAL as name (name)}{@render field(name)}{/each}
		</div>
	</div>

	<!-- The button's own disabled state is the primary signal; this says why, for anyone
	     who cannot see that it is greyed out. -->
	<p class="text-sm text-muted" role="status">
		{#if complete}
			Ready to analyse {headers.length} columns.
		{:else}
			Still needed: {missing.map((name) => advocate.fields[name]).join(', ')}.
		{/if}
	</p>
</div>
