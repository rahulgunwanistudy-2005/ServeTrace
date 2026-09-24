<script lang="ts">
	/**
	 * What the person will swear to, collected before the draft affidavit is written.
	 *
	 * Bible §15 is the reason this exists rather than a download button. Every boolean
	 * here gates a numbered paragraph in a document signed in front of a notary, and each
	 * one states something only this person knows — whether papers reached them, whether
	 * an address is theirs, whether notice arrived in time to defend. `documents/affidavit`
	 * leaves an unticked paragraph out entirely rather than hedging it, because a sworn
	 * statement hedged into vagueness is worse for them than a shorter one.
	 *
	 * So the form asks plainly and takes silence for no.
	 */
	import { untrack } from 'svelte';

	import type { AffiantStatement } from '$lib/api/client';
	import Button from './Button.svelte';
	import Callout from './Callout.svelte';
	import CheckBox from './CheckBox.svelte';
	import Card from './Card.svelte';
	import Eyebrow from './Eyebrow.svelte';
	import TextField from './TextField.svelte';
	import { result } from '$copy/en';

	let {
		defaultName = '',
		busy = false,
		onsubmit,
		oncancel
	}: {
		defaultName?: string;
		busy?: boolean;
		onsubmit: (statement: AffiantStatement) => void;
		oncancel: () => void;
	} = $props();

	// Seeded once, on purpose, and `untrack` says so rather than leaving a warning to be
	// read as an oversight: this is the person's name to correct, not a value the parent
	// keeps control of. Reacting to a later change would overwrite what they had typed.
	let name = $state(untrack(() => defaultName));
	let address = $state('');
	let notServed = $state(false);
	let notMyAddress = $state(false);
	let noNotice = $state(false);
	let defence = $state('');
	let touched = $state(false);

	const nameMissing = $derived(name.trim().length === 0);

	function submit(event: SubmitEvent) {
		event.preventDefault();
		touched = true;
		if (nameMissing) return;
		onsubmit({
			name: name.trim(),
			residence_address: address.trim() || null,
			states_not_served: notServed,
			states_not_my_address: notMyAddress,
			states_no_notice_in_time: noNotice,
			defense_summary: defence.trim() || null
		});
	}
</script>

<Card>
	<form onsubmit={submit} novalidate>
		<Eyebrow>{result.affiantTitle}</Eyebrow>
		<p class="mt-3 leading-relaxed text-muted">{result.affiantIntro}</p>

		<div class="mt-6 space-y-5">
			<TextField
				id="affiant-name"
				label={result.affiantName}
				bind:value={name}
				required
				invalid={touched && nameMissing}
				note={touched && nameMissing ? result.affiantNameNeeded : undefined}
			/>

			<TextField
				id="affiant-address"
				label={result.affiantAddress}
				bind:value={address}
				hint={result.affiantAddressHint}
			/>

			<fieldset class="space-y-4 border-t border-line pt-5">
				<legend class="sr-only">{result.affiantTitle}</legend>
				<CheckBox id="affiant-not-served" bind:checked={notServed} label={result.affiantNotServed} />
				<CheckBox
					id="affiant-not-my-address"
					bind:checked={notMyAddress}
					label={result.affiantNotMyAddress}
				/>
				<CheckBox
					id="affiant-no-notice"
					bind:checked={noNotice}
					label={result.affiantNoNotice}
					hint={result.affiantNoNoticeHint}
				/>
			</fieldset>

			{#if noNotice}
				<TextField
					id="affiant-defence"
					label={result.affiantDefense}
					bind:value={defence}
					hint={result.affiantDefenseHint}
					multiline
				/>
			{/if}
		</div>

		<div class="mt-6">
			<Callout tone="neutral">
				Everything we generate is a draft and is not legal advice. Review it with the NYC Civil
				Court Help Center or a legal aid organization before you file it.
			</Callout>
		</div>

		<div class="mt-6 flex flex-wrap gap-3">
			<Button type="submit" disabled={busy}>
				{busy ? 'Preparing…' : result.affiantSubmit}
			</Button>
			<Button variant="quiet" onclick={oncancel} disabled={busy}>{result.affiantCancel}</Button>
		</div>
	</form>
</Card>
