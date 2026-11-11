<script lang="ts">
	/**
	 * For attorneys and legal aid: what the batch mode does, what happens to the papers,
	 * and a way to get in touch. Build prompt §8.3.
	 *
	 * The contact form is the only place in the product where what someone types is kept,
	 * so it says exactly that, asks for consent in words, and links to how to undo it.
	 * The honeypot is a real field moved off screen and out of the tab order: a person
	 * never fills it, a form-filling bot usually does, and the server drops those quietly.
	 */
	import { api, ApiError, type Health, type LeadIn } from '$lib/api/client';
	import { attorneys as copy, nav, upload } from '$copy/en';
	import Button from '$lib/ui/Button.svelte';
	import Callout from '$lib/ui/Callout.svelte';
	import Card from '$lib/ui/Card.svelte';
	import CheckBox from '$lib/ui/CheckBox.svelte';
	import Eyebrow from '$lib/ui/Eyebrow.svelte';
	import IridescentField from '$lib/ui/IridescentField.svelte';
	import TextField from '$lib/ui/TextField.svelte';

	type Role = LeadIn['role'];

	let name = $state('');
	let email = $state('');
	let organization = $state('');
	let role = $state<Role>('legal_aid');
	let message = $state('');
	let consent = $state(false);
	let website = $state('');
	let sending = $state(false);
	let sent = $state(false);
	let failure = $state<string | null>(null);

	let health = $state<Health | null>(null);
	$effect(() => {
		void api
			.health()
			.then((h) => (health = h))
			.catch(() => (health = null));
	});
	const PROVIDERS: Record<string, string> = { gemini: 'Google Gemini', anthropic: 'Anthropic' };
	const realAllowed = $derived(health?.llm_real_data_allowed === true && health.llm_provider !== 'none');

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		failure = null;
		if (!consent) {
			failure = copy.consentNeeded;
			return;
		}
		sending = true;
		try {
			await api.lead({
				name: name.trim(),
				email: email.trim(),
				organization: organization.trim() || null,
				role,
				message: message.trim() || null,
				consent: true,
				website
			});
			sent = true;
		} catch (error) {
			failure = error instanceof ApiError ? error.message : 'Something went wrong.';
		} finally {
			sending = false;
		}
	}
</script>

<svelte:head><title>{nav.attorneys} — ServeTrace</title></svelte:head>

<section class="st-panel st-iridescent rounded-none">
	<IridescentField />
	<div class="st-shell py-12 sm:py-16">
		<Eyebrow>{nav.attorneys}</Eyebrow>
		<h1 class="st-display mt-4 max-w-3xl text-3xl text-panel-ink sm:text-5xl">{copy.title}</h1>
		<p class="mt-5 max-w-2xl text-lg leading-relaxed text-panel-muted">{copy.sub}</p>
		<div class="mt-8 flex flex-wrap items-center gap-3">
			<Button href="/advocate?mode=affidavits" invert arrow>{copy.tryIt}</Button>
			<p class="text-sm text-panel-muted">{copy.tryItNote}</p>
		</div>
	</div>
</section>

<div class="st-shell space-y-14 py-12 sm:py-16">
	<ol class="grid gap-4 md:grid-cols-3">
		{#each copy.blocks as block, i (block.title)}
			<li>
				<Card>
					<p class="st-eyebrow tabular-nums">0{i + 1}</p>
					<h2 class="st-display-sm mt-3 text-lg">{block.title}</h2>
					<p class="mt-2 text-sm leading-relaxed text-muted">{block.body}</p>
				</Card>
			</li>
		{/each}
	</ol>

	<section class="max-w-3xl space-y-4">
		<h2 class="st-display-sm text-xl sm:text-2xl">{copy.dataTitle}</h2>
		{#if realAllowed && health}
			<Callout tone="neutral">
				{upload.realDataAllowed(PROVIDERS[health.llm_provider] ?? health.llm_provider)}
			</Callout>
		{:else}
			<Callout tone="caution">{upload.realDataBlocked}</Callout>
		{/if}
		<p class="leading-relaxed text-muted">{copy.notStored}</p>
		<p class="leading-relaxed text-muted">{copy.noReader}</p>
	</section>

	<section class="max-w-2xl" aria-labelledby="contact-title">
		<h2 id="contact-title" class="st-display-sm text-xl sm:text-2xl">{copy.formTitle}</h2>
		<p class="mt-2 leading-relaxed text-muted">{copy.formIntro}</p>

		{#if sent}
			<div class="mt-6" role="status">
				<Callout tone="consistent" title={copy.sentTitle}>{copy.sent}</Callout>
			</div>
		{:else}
			<form class="mt-6 space-y-5" onsubmit={submit} novalidate={false}>
				{#if failure}
					<div role="alert"><Callout tone="contradicted">{failure}</Callout></div>
				{/if}
				<TextField id="lead-name" label={copy.fields.name} bind:value={name} required />
				<TextField id="lead-email" type="email" label={copy.fields.email} bind:value={email} required />
				<TextField id="lead-organization" label={copy.fields.organization} bind:value={organization} />
				<label class="block">
					<span class="text-sm font-medium">{copy.fields.role}</span>
					<select
						id="lead-role"
						bind:value={role}
						class="mt-1.5 min-h-11 w-full rounded-control border border-line-strong bg-raised px-3 text-sm text-ink"
					>
						{#each Object.entries(copy.roles) as [value, label] (value)}
							<option {value}>{label}</option>
						{/each}
					</select>
				</label>
				<TextField id="lead-message" label={copy.fields.message} bind:value={message} multiline />

				<!-- The honeypot. Off screen, out of the tab order, hidden from assistive tech. -->
				<div class="absolute -left-[10000px] h-px w-px overflow-hidden" aria-hidden="true">
					<label>
						{copy.honeypot}
						<input type="text" name="website" tabindex="-1" autocomplete="off" bind:value={website} />
					</label>
				</div>

				<CheckBox id="lead-consent" bind:checked={consent} label={copy.consent} />

				<div class="flex flex-wrap items-center gap-4">
					<Button type="submit" disabled={sending || !consent}>
						{sending ? copy.sending : copy.send}
					</Button>
					<a href="/privacy" class="text-sm underline underline-offset-4">{copy.privacyLink}</a>
				</div>
			</form>
		{/if}
	</section>
</div>
