<script lang="ts">
	/**
	 * What came off the document, for the person to correct. Bible §14.2.
	 *
	 * The whole product rests on this screen. Everything downstream — the engine, the
	 * verdict, the packet, the sworn affidavit — is computed from these fields, and a
	 * model read them off a photograph. So the goal is not to look confident; it is to
	 * make a wrong value easy to notice and easy to fix.
	 *
	 * Three things follow:
	 *
	 * - **Every field is editable, always**, not "editable if we were unsure". A person who
	 *   knows their own address should not have to argue with a confidence score.
	 * - **Anything under 0.8 is amber and shows the words it was read from**, so the person
	 *   compares our value against the page rather than against nothing.
	 * - **The tick is the gate.** `user_confirmed` is what `/api/analyze` refuses to run
	 *   without (bible §10), and it means this person read these fields — not that a model
	 *   was confident about them.
	 */
	import type { ExtractionResult } from '$lib/api/client';
	import Callout from '$lib/ui/Callout.svelte';
	import CheckBox from '$lib/ui/CheckBox.svelte';
	import Eyebrow from '$lib/ui/Eyebrow.svelte';
	import TextField from '$lib/ui/TextField.svelte';
	import { upload } from '$copy/en';

	let {
		extraction,
		values = $bindable(),
		confirmed = $bindable(false)
	}: {
		extraction: ExtractionResult | null;
		values: Record<string, string>;
		confirmed?: boolean;
	} = $props();

	/** Bible §14.2: below this a field is amber and shows its source quote. */
	const UNSURE_BELOW = 0.8;

	const TEXT_FIELDS = [
		'defendant_name',
		'served_address',
		'served_date',
		'served_time',
		'recipient_name',
		'recipient_relationship',
		'index_number',
		'court',
		'plaintiff',
		'server_name',
		'mailing_date',
		'proof_filed_date'
	] as const;

	const WIDE = new Set(['served_address', 'court']);
	const DATES = new Set(['served_date', 'mailing_date', 'proof_filed_date']);

	const labels = upload.fields as Record<string, string>;

	function unsure(field: string): boolean {
		const score = extraction?.draft.field_confidence?.[field];
		return typeof score === 'number' && score < UNSURE_BELOW;
	}

	/** A validator's observation outranks a confidence score: it is deterministic. */
	function validatorNote(field: string): string | undefined {
		return extraction?.notes?.find((n) => n.field === field)?.message;
	}

	function noteFor(field: string): string | undefined {
		const observed = validatorNote(field);
		if (observed) return observed;
		if (!unsure(field)) return undefined;
		const source = extraction?.draft.evidence_quotes?.[field];
		return source ? `${upload.lowConfidence} ${upload.quotedAs} “${source}”` : upload.lowConfidence;
	}
</script>

<section>
	<Eyebrow>{upload.reviewTitle}</Eyebrow>
	<p class="mt-3 leading-relaxed text-muted">{upload.reviewIntro}</p>

	{#if extraction && extraction.provider === 'none'}
		<div class="mt-5"><Callout tone="neutral">{upload.noLlm}</Callout></div>
	{/if}

	<div class="mt-6 grid gap-5 sm:grid-cols-2">
		<!--
			`method` is a select rather than free text: it is the one field with a closed set
			of answers, every downstream timing rule branches on it, and a typo here would
			silently skip those rules rather than fail.
		-->
		<div class="sm:col-span-2">
			<label class="block text-sm font-medium" for="field-method">{labels.method}</label>
			<select
				id="field-method"
				bind:value={values.method}
				class="mt-1.5 min-h-11 w-full rounded-control border bg-raised px-3 text-sm text-ink
				       {unsure('method') ? 'border-caution' : 'border-line-strong'}"
			>
				{#each Object.entries(upload.methodOptions) as [value, label] (value)}
					<option {value}>{label}</option>
				{/each}
			</select>
			{#if noteFor('method')}
				<p class="mt-1.5 text-xs leading-relaxed text-caution">{noteFor('method')}</p>
			{/if}
		</div>

		{#each TEXT_FIELDS as field (field)}
			<div class={WIDE.has(field) ? 'sm:col-span-2' : ''}>
				<TextField
					id="field-{field}"
					label={labels[field] ?? field}
					bind:value={values[field]}
					type={DATES.has(field) ? 'date' : 'text'}
					invalid={unsure(field) || Boolean(validatorNote(field))}
					note={noteFor(field)}
				/>
			</div>
		{/each}
	</div>

	<div class="mt-8 border-t border-line pt-6">
		<CheckBox id="confirm-details" bind:checked={confirmed} label={upload.confirmCheckbox} />
	</div>
</section>
