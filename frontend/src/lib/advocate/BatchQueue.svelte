<script lang="ts">
	/**
	 * The batch, one row per affidavit: what was read, and what still needs a person.
	 *
	 * The status is a word as well as a colour (bible §14), and the defendant is shown as
	 * initials only: this is a working list on an office screen, and the task is checking
	 * a server's filings, not reading a column of names. The file name stays on this
	 * device; it is never part of what is sent for the analysis.
	 */
	import type { Snippet } from 'svelte';
	import { advocate } from '$copy/en';
	import { draftOf, flagCount, initials, type ItemStatus, type QueueItem } from './batch';

	let {
		items,
		open,
		onopen,
		onretry,
		onmanual,
		detail
	}: {
		items: QueueItem[];
		/** The row whose review is open, if any. */
		open: string | null;
		onopen: (id: string) => void;
		onretry: (id: string) => void;
		onmanual: (id: string) => void;
		/** The open row's review, drawn directly beneath it rather than under the whole list. */
		detail?: Snippet<[QueueItem]>;
	} = $props();

	const words = advocate.batch;

	const TONE: Record<ItemStatus, string> = {
		queued: 'border-line-strong text-muted',
		reading: 'border-line-strong text-muted',
		ok: 'border-consistent/40 bg-consistent-quiet text-consistent',
		review: 'border-caution/40 bg-caution-quiet text-caution',
		failed: 'border-contradicted/40 bg-contradicted-quiet text-contradicted',
		confirmed: 'border-accent bg-accent text-on-accent'
	};

	function agencyOf(item: QueueItem): string {
		return item.values.agency_name || draftOf(item)?.agency_license || '—';
	}
</script>

<div class="relative overflow-x-auto rounded-card bg-surface">
	<table class="w-full border-collapse text-sm">
		<caption class="sr-only">{words.queueTitle}. {words.queueHint}</caption>
		<thead>
			<tr class="st-eyebrow border-b border-line-strong text-left">
				<th scope="col" class="px-3 py-3 font-semibold">{words.columns.status}</th>
				<th scope="col" class="px-3 py-3 font-semibold">{words.columns.file}</th>
				<th scope="col" class="px-3 py-3 font-semibold">{words.columns.defendant}</th>
				<th scope="col" class="px-3 py-3 font-semibold">{words.columns.served}</th>
				<th scope="col" class="px-3 py-3 font-semibold">{words.columns.server}</th>
				<th scope="col" class="px-3 py-3 font-semibold">{words.columns.agency}</th>
				<th scope="col" class="px-3 py-3 font-semibold">{words.columns.method}</th>
				<th scope="col" class="px-3 py-3 text-right font-semibold">{words.columns.flags}</th>
				<th scope="col" class="px-3 py-3"><span class="sr-only">Action</span></th>
			</tr>
		</thead>
		<tbody>
			{#each items as item (item.id)}
				{@const flags = flagCount(item)}
				<tr
					class="border-b border-line last:border-0 {open === item.id ? 'bg-accent-quiet' : ''}"
					data-status={item.status}
				>
					<td class="px-3 py-2.5">
						<span
							class="inline-block whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-semibold
							       {TONE[item.status]}"
						>
							{words.status[item.status]}
						</span>
					</td>
					<td class="max-w-40 truncate px-3 py-2.5 text-muted" title={item.name}>
						{item.name}{item.extraction && (item.extraction.affidavits?.length ?? 0) > 1
							? ` · ${item.index + 1}`
							: ''}
					</td>
					{#if item.status === 'failed'}
						<td colspan="6" class="px-3 py-2.5 text-contradicted">
							{item.message ?? (item.fail ? words.fail[item.fail] : '')}
						</td>
					{:else if item.status === 'queued' || item.status === 'reading'}
						<td colspan="6" class="px-3 py-2.5 text-faint">—</td>
					{:else}
						<td class="px-3 py-2.5 font-medium tabular-nums">
							{initials(item.values.defendant_name)}
						</td>
						<td class="whitespace-nowrap px-3 py-2.5 tabular-nums text-muted">
							{item.values.served_date || '—'}
						</td>
						<td class="px-3 py-2.5">{item.values.server_name || item.values.server_license || '—'}</td>
						<td class="max-w-48 truncate px-3 py-2.5 text-muted" title={agencyOf(item)}>
							{agencyOf(item)}
						</td>
						<td class="whitespace-nowrap px-3 py-2.5 text-muted">
							{words.methodShort[item.values.method ?? 'unknown'] ?? '—'}
						</td>
						<td class="px-3 py-2.5 text-right tabular-nums {flags ? 'font-semibold text-caution' : 'text-faint'}">
							{flags}
						</td>
					{/if}
					<td class="whitespace-nowrap px-3 py-1.5 text-right">
						{#if item.status === 'failed'}
							<button
								type="button"
								class="min-h-9 rounded-control px-2 font-medium underline underline-offset-4"
								onclick={() => onretry(item.id)}
								disabled={!item.file}
							>
								{words.retry}
							</button>
							<button
								type="button"
								class="min-h-9 rounded-control px-2 font-medium underline underline-offset-4"
								onclick={() => onmanual(item.id)}
							>
								{words.typeIn}
							</button>
						{:else if item.status === 'ok' || item.status === 'review' || item.status === 'confirmed'}
							<button
								type="button"
								class="min-h-9 rounded-control px-2 font-medium underline underline-offset-4"
								aria-expanded={open === item.id}
								onclick={() => onopen(item.id)}
							>
								{open === item.id ? words.close : words.review}
							</button>
						{/if}
					</td>
				</tr>
				{#if open === item.id && detail}
					<tr class="border-b border-line">
						<td colspan="9" class="bg-canvas p-3 sm:p-5">{@render detail(item)}</td>
					</tr>
				{/if}
			{/each}
		</tbody>
	</table>
</div>
