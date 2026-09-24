<script lang="ts">
	/**
	 * A labelled text input.
	 *
	 * The styling is `ColumnMapper`'s field, extracted rather than invented: the wizard
	 * needs a dozen inputs and the advocate mapper already established what one looks like
	 * in this product. Two places writing the same classes by hand is how a visual system
	 * drifts.
	 */
	let {
		id,
		label,
		value = $bindable(''),
		hint,
		placeholder,
		type = 'text',
		required = false,
		multiline = false,
		invalid = false,
		note
	}: {
		id: string;
		label: string;
		value?: string;
		hint?: string;
		placeholder?: string;
		type?: 'text' | 'date';
		required?: boolean;
		multiline?: boolean;
		/** Amber, for a field the extractor was unsure about or a validator flagged. */
		invalid?: boolean;
		note?: string;
	} = $props();

	const shell =
		'mt-1.5 w-full rounded-control border bg-raised px-3 py-2.5 text-sm text-ink ' +
		'placeholder:text-faint';
</script>

<div>
	<label class="block text-sm font-medium" for={id}>
		{label}
		{#if required}<span class="ml-1 font-normal text-caution">·&nbsp;needed</span>{/if}
	</label>

	{#if multiline}
		<textarea
			{id}
			bind:value
			{placeholder}
			rows="3"
			aria-describedby={note ? `${id}-note` : undefined}
			class="{shell} {invalid ? 'border-caution' : 'border-line-strong'}"
		></textarea>
	{:else}
		<input
			{id}
			{type}
			bind:value
			{placeholder}
			aria-describedby={note ? `${id}-note` : undefined}
			class="{shell} min-h-11 {invalid ? 'border-caution' : 'border-line-strong'}"
		/>
	{/if}

	{#if note}
		<p id="{id}-note" class="mt-1.5 text-xs leading-relaxed {invalid ? 'text-caution' : 'text-faint'}">
			{note}
		</p>
	{:else if hint}
		<p class="mt-1.5 text-xs leading-relaxed text-faint">{hint}</p>
	{/if}
</div>
