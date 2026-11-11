<script lang="ts">
	/**
	 * What came off the document, for the person to correct. Bible §14.2; build prompt §4.3.
	 *
	 * Everything downstream — the engine, the verdict, the packet, the sworn affidavit —
	 * is computed from these fields, and a model read them off a photograph. So the goal is
	 * not to look confident; it is to make a wrong value quick to notice and quick to fix.
	 *
	 * - **Flagged first.** By default only the fields that need a look are shown: read with
	 *   confidence under 0.8, or noted by a validator. "Show all fields" is one tap away,
	 *   and every field is always editable.
	 * - **The page beside the field.** Selecting a field turns the viewer to its page and
	 *   boxes the words it came from.
	 * - **Keyboard first.** Enter keeps what we read, Esc puts it back, Tab moves on.
	 * - **"Confirm all" is the gate,** and it stays shut until every flag has been looked
	 *   at. `user_confirmed` is what `/api/analyze` refuses to run without (bible §10), and
	 *   it means this person read these fields — not that a model was confident.
	 */
	import { tick } from 'svelte';
	import type { DocumentExtraction, PageType } from '$lib/api/client';
	import Button from '$lib/ui/Button.svelte';
	import Callout from '$lib/ui/Callout.svelte';
	import Eyebrow from '$lib/ui/Eyebrow.svelte';
	import TextField from '$lib/ui/TextField.svelte';
	import PageViewer from './PageViewer.svelte';
	import {
		FIELDS,
		OUTCOMES,
		attemptKey,
		attemptsFrom,
		changedPages,
		describeAffidavit,
		evidenceFor,
		flaggedKeys,
		isFlagged,
		notesFor,
		pageFor,
		unresolved,
		valuesFrom,
		type AttemptValues,
		type Values
	} from './review';
	import { upload } from '$copy/en';

	let {
		extraction,
		selected = 0,
		values = $bindable(),
		attempts = $bindable([]),
		resolved = $bindable([]),
		confirmed = $bindable(false),
		retagging = false,
		onselect,
		onretag,
		onconfirm
	}: {
		extraction: DocumentExtraction | null;
		selected?: number;
		values: Values;
		attempts?: AttemptValues[];
		/** Flagged keys the person has accepted or changed. */
		resolved?: string[];
		confirmed?: boolean;
		retagging?: boolean;
		onselect?: (index: number) => void;
		onretag?: (pageTypes: PageType[]) => void;
		onconfirm?: () => void;
	} = $props();

	const review = upload.review;
	const labels = upload.fields as Record<string, string>;

	const found = $derived(extraction?.affidavits?.[selected] ?? null);
	const original = $derived(valuesFrom(found?.draft));
	const originalAttempts = $derived(attemptsFrom(found?.draft));
	const flagged = $derived(flaggedKeys(found));
	const left = $derived(unresolved(flagged, new Set(resolved)));
	const previews = $derived(extraction?.previews ?? []);

	let showAll = $state(false);
	const everything = $derived(showAll || flagged.length === 0);
	let activeKey = $state<string | null>(null);
	let page = $state(0);

	/** The viewer follows the selected field to its page. */
	$effect(() => {
		if (activeKey !== null) page = pageFor(found, activeKey);
		else if (found?.pages?.[0] !== undefined) page = found.pages[0];
	});

	const evidence = $derived(activeKey ? evidenceFor(found, activeKey) : null);

	/** A new affidavit, or new flags, start the viewer afresh. */
	$effect(() => {
		void found;
		activeKey = null;
	});

	function visible(key: string): boolean {
		return everything || flagged.includes(key);
	}

	function touch(key: string) {
		if (!resolved.includes(key)) resolved = [...resolved, key];
		confirmed = false;
	}

	async function focusNext(after: string) {
		// Wait for the gate to open: focusing a still-disabled "Confirm all" does nothing.
		await tick();
		const order = flagged;
		const next = order.slice(order.indexOf(after) + 1).find((key) => !resolved.includes(key));
		const target = next ?? order.find((key) => !resolved.includes(key));
		if (target) document.getElementById(`field-${target}`)?.focus();
		else document.getElementById('confirm-all')?.focus();
	}

	function revert(key: string) {
		const match = /^attempts\[(\d+)\]$/.exec(key);
		if (match) {
			const i = Number(match[1]);
			const was = originalAttempts[i];
			if (was) attempts[i] = { ...was };
		} else {
			values[key] = original[key] ?? '';
		}
		resolved = resolved.filter((k) => k !== key);
		confirmed = false;
	}

	/** Enter keeps the value as it stands, Esc puts back what we read. */
	function keys(key: string) {
		return (event: KeyboardEvent) => {
			if (event.key === 'Enter') {
				event.preventDefault();
				touch(key);
				void focusNext(key);
			} else if (event.key === 'Escape') {
				event.preventDefault();
				revert(key);
			}
		};
	}

	function noteFor(key: string): string | undefined {
		const observed = notesFor(found, key)[0]?.message;
		if (observed) return observed;
		if (!isFlagged(found, key)) return undefined;
		const quote = evidenceFor(found, key)?.quote;
		return quote ? `${upload.lowConfidence} ${upload.quotedAs} “${quote}”` : upload.lowConfidence;
	}

	function confirmAll() {
		if (left.length > 0) return;
		confirmed = true;
		onconfirm?.();
	}

	/** The page labels as the person is editing them, before they ask to read again. */
	let labelsDraft = $state<PageType[]>([]);
	$effect(() => {
		labelsDraft = [...(extraction?.page_types ?? [])];
	});
	const retagged = $derived(changedPages(extraction?.page_types ?? [], labelsDraft));
	const PAGE_TYPES = Object.keys(upload.pageTypes) as PageType[];

	const description = $derived(found?.draft.recipient_description?.raw_text ?? '');
</script>

<section>
	<Eyebrow>{upload.reviewTitle}</Eyebrow>
	<p class="mt-3 leading-relaxed text-muted">{upload.reviewIntro}</p>

	{#if extraction && extraction.provider === 'none'}
		<div class="mt-5"><Callout tone="neutral">{upload.noLlm}</Callout></div>
	{/if}
	{#each extraction?.notes ?? [] as note (note.message)}
		<div class="mt-5"><Callout tone="caution">{note.message}</Callout></div>
	{/each}

	{#if (extraction?.affidavits?.length ?? 0) > 1}
		<fieldset class="mt-6">
			<legend class="text-sm font-medium">{review.which(extraction?.affidavits?.length ?? 0)}</legend>
			<div class="mt-3 grid gap-2 sm:grid-cols-2">
				{#each extraction?.affidavits ?? [] as candidate, i (i)}
					{@const about = describeAffidavit(candidate)}
					<label
						class="flex min-h-12 cursor-pointer items-start gap-3 rounded-control border px-3 py-2.5 text-sm
						       {i === selected ? 'border-accent bg-accent-quiet' : 'border-line-strong'}"
					>
						<input
							type="radio"
							name="which-affidavit"
							checked={i === selected}
							onchange={() => onselect?.(i)}
							class="mt-1"
						/>
						<span>
							<span class="block font-medium">{about.name || '—'}</span>
							<span class="block text-muted">
								{review.pagesOf(about.pages)}{about.date ? ` · ${about.date}` : ''}
							</span>
						</span>
					</label>
				{/each}
			</div>
		</fieldset>
	{/if}

	<div class="mt-6 grid gap-6 {previews.length ? 'lg:grid-cols-2' : ''}">
		{#if previews.length}
			<div class="lg:sticky lg:top-4 lg:self-start">
				<PageViewer
					{previews}
					pageTypes={extraction?.page_types ?? []}
					bind:page
					bbox={evidence?.page === page ? (evidence?.bbox ?? null) : null}
					quote={evidence?.quote ?? null}
					active={activeKey !== null}
				/>

				{#if (extraction?.n_pages ?? 0) > 1 && onretag}
					<details class="mt-3 rounded-card border border-line bg-surface">
						<summary class="flex min-h-11 cursor-pointer items-center px-4 text-sm font-medium">
							{review.pagesTitle}
						</summary>
						<div class="px-4 pb-4">
							<p class="text-xs leading-relaxed text-muted">{review.pagesHint}</p>
							<ol class="mt-3 grid gap-2 sm:grid-cols-2">
								{#each labelsDraft as _, i (i)}
									<li class="flex items-center gap-2 text-sm">
										<label for="page-type-{i}" class="w-14 shrink-0 text-muted">
											{review.page(i + 1, labelsDraft.length).split(' of')[0]}
										</label>
										<select
											id="page-type-{i}"
											bind:value={labelsDraft[i]}
											class="min-h-10 w-full rounded-control border border-line-strong bg-raised px-2 text-sm"
										>
											{#each PAGE_TYPES as type (type)}
												<option value={type}>{upload.pageTypes[type]}</option>
											{/each}
										</select>
									</li>
								{/each}
							</ol>
							{#if retagged.length > 0}
								<div class="mt-3">
									<Button
										variant="secondary"
										disabled={retagging}
										onclick={() => onretag?.([...labelsDraft])}
									>
										{retagging ? review.rereading : review.reread}
									</Button>
								</div>
							{/if}
						</div>
					</details>
				{/if}
			</div>
		{/if}

		<div>
			{#if flagged.length > 0}
				<div class="flex flex-wrap items-center justify-between gap-3">
					<p class="text-sm font-medium" aria-live="polite">
						{review.flaggedCount(left.length, flagged.length)}
					</p>
					<label class="flex items-center gap-2 text-sm">
						<input type="checkbox" bind:checked={showAll} />
						{review.showAll}
					</label>
				</div>
				<p class="mt-1 text-xs text-faint">{review.keys}</p>
			{:else if found}
				<p class="text-sm text-muted">{review.noneFlagged}</p>
			{/if}

			<div class="mt-4 grid gap-5 sm:grid-cols-2">
				{#each FIELDS as field (field.key)}
					{#if visible(field.key)}
						{@const flag = isFlagged(found, field.key)}
						{@const done = resolved.includes(field.key)}
						<div
							class="{field.wide || previews.length ? 'sm:col-span-2' : ''}
							       {activeKey === field.key ? 'rounded-control ring-2 ring-accent/40 ring-offset-4 ring-offset-canvas' : ''}"
						>
							{#if field.kind === 'method'}
								<!--
									A select rather than free text: the one field with a closed set of
									answers, and every timing rule branches on it.
								-->
								<label class="block text-sm font-medium" for="field-method">{labels.method}</label>
								<select
									id="field-method"
									bind:value={values.method}
									onfocus={() => (activeKey = 'method')}
									onchange={() => touch('method')}
									onkeydown={keys('method')}
									aria-describedby={noteFor('method') ? 'field-method-note' : undefined}
									class="mt-1.5 min-h-11 w-full rounded-control border bg-raised px-3 text-sm text-ink
									       {flag && !done ? 'border-caution' : 'border-line-strong'}"
								>
									{#each Object.entries(upload.methodOptions) as [value, label] (value)}
										<option {value}>{label}</option>
									{/each}
								</select>
								{#if noteFor('method')}
									<p id="field-method-note" class="mt-1.5 text-xs leading-relaxed text-caution">
										{noteFor('method')}
									</p>
								{/if}
							{:else if field.kind === 'readonly'}
								{#if description}
									<button
										type="button"
										id="field-{field.key}"
										class="w-full text-left"
										onfocus={() => (activeKey = field.key)}
										onclick={() => {
											activeKey = field.key;
											touch(field.key);
										}}
										onkeydown={keys(field.key)}
									>
										<span class="block text-sm font-medium">{labels[field.key]}</span>
										<span
											class="mt-1.5 block rounded-control border bg-sunken px-3 py-2.5 text-sm
											       {flag && !done ? 'border-caution' : 'border-line'}">{description}</span
										>
										<span class="mt-1.5 block text-xs text-faint">{upload.descriptionReadOnly}</span>
									</button>
								{/if}
							{:else}
								<TextField
									id="field-{field.key}"
									label={labels[field.key] ?? field.key}
									bind:value={values[field.key]}
									type={field.kind === 'date' ? 'date' : field.kind === 'time' ? 'time' : 'text'}
									invalid={flag && !done}
									note={noteFor(field.key)}
									onfocus={() => (activeKey = field.key)}
									oninput={() => touch(field.key)}
									onkeydown={keys(field.key)}
								/>
							{/if}

							{#if flag}
								<div class="mt-2 flex items-center gap-3 text-xs">
									{#if done}
										<span class="font-medium text-consistent">✓ {review.accepted}</span>
										{#if (values[field.key] ?? '') !== (original[field.key] ?? '')}
											<button type="button" class="underline" onclick={() => revert(field.key)}>
												{review.revert}
											</button>
										{/if}
									{:else}
										<button
											type="button"
											class="min-h-8 rounded-control border border-line-strong px-2.5 font-medium"
											onclick={() => {
												touch(field.key);
												void focusNext(field.key);
											}}
										>
											{review.accept}
										</button>
									{/if}
								</div>
							{/if}
						</div>
					{/if}
				{/each}
			</div>

			{#if attempts.length > 0 && attempts.some((_, i) => visible(attemptKey(i)))}
				<fieldset class="mt-8">
					<legend class="text-sm font-medium">{upload.attempts}</legend>
					<div class="mt-3 space-y-4">
						{#each attempts as attempt, i (i)}
							{@const key = attemptKey(i)}
							{#if visible(key)}
								{@const flag = isFlagged(found, key)}
								{@const done = resolved.includes(key)}
								<div
									class="rounded-card border p-3 {flag && !done ? 'border-caution' : 'border-line'}"
								>
									<p class="text-xs font-medium text-muted">{upload.attempt(i + 1)}</p>
									<div class="mt-2 grid gap-3 sm:grid-cols-2">
										<TextField
											id="field-{key}"
											label={upload.attemptDate}
											type="date"
											bind:value={attempt.date}
											onfocus={() => (activeKey = key)}
											oninput={() => touch(key)}
											onkeydown={keys(key)}
										/>
										<TextField
											id="field-{key}-time"
											label={upload.attemptTime}
											type="time"
											bind:value={attempt.time}
											onfocus={() => (activeKey = key)}
											oninput={() => touch(key)}
											onkeydown={keys(key)}
										/>
										<div class="sm:col-span-2">
											<TextField
												id="field-{key}-address"
												label={upload.attemptAddress}
												bind:value={attempt.address}
												onfocus={() => (activeKey = key)}
												oninput={() => touch(key)}
												onkeydown={keys(key)}
											/>
										</div>
										<div class="sm:col-span-2">
											<label class="block text-sm font-medium" for="field-{key}-outcome">
												{upload.attemptOutcome}
											</label>
											<select
												id="field-{key}-outcome"
												bind:value={attempt.outcome}
												onfocus={() => (activeKey = key)}
												onchange={() => touch(key)}
												class="mt-1.5 min-h-11 w-full rounded-control border border-line-strong bg-raised px-3 text-sm"
											>
												{#each OUTCOMES as outcome (outcome)}
													<option value={outcome}>{upload.outcomes[outcome]}</option>
												{/each}
											</select>
										</div>
									</div>
									{#if flag}
										<p class="mt-2 text-xs text-caution">{noteFor(key)}</p>
										{#if !done}
											<button
												type="button"
												class="mt-2 min-h-8 rounded-control border border-line-strong px-2.5 text-xs font-medium"
												onclick={() => {
													touch(key);
													void focusNext(key);
												}}
											>
												{review.accept}
											</button>
										{:else}
											<p class="mt-2 text-xs font-medium text-consistent">✓ {review.accepted}</p>
										{/if}
									{/if}
								</div>
							{/if}
						{/each}
					</div>
				</fieldset>
			{/if}

			<div class="mt-8 border-t border-line pt-6">
				<Button id="confirm-all" onclick={confirmAll} disabled={left.length > 0 || confirmed}>
					{confirmed ? `✓ ${upload.confirmCheckbox}` : review.confirmAll}
				</Button>
				{#if left.length > 0}
					<p class="mt-2 text-sm text-caution">{review.confirmBlocked(left.length)}</p>
				{:else if confirmed}
					<p class="mt-2 text-sm text-muted">{review.confirmed}</p>
				{/if}
			</div>
		</div>
	</div>
</section>
