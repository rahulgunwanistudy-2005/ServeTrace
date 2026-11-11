/**
 * The advocate batch, on the device: a folder of affidavits read one by one, each
 * confirmed by a person, then sent together for the agency report. Build prompt §6.2.
 *
 * Kept free of components so the parts that decide things — what needs a look, how many
 * reads run at once, when to try again — are tested without a DOM.
 *
 * The browser drives the reading rather than the server, for the same reason the defendant
 * flow does: nothing is stored server-side (bible §16), so a server-side job queue would
 * have nowhere to keep its jobs. The cost is that the tab has to stay open; the queue says so.
 */

import { ApiError, type AffidavitDraft, type DocumentExtraction } from '$lib/api/client';
import { attemptsFrom, flaggedKeys, valuesFrom, type AttemptValues, type Values } from '$lib/check/review';

/** Build prompt §6.2: how much one sitting may hold. */
export const MAX_FILES = 200;
export const MAX_PAGES = 2000;
/** Reads in flight at once: enough to keep a reader busy, few enough not to trip its limit. */
export const CONCURRENCY = 3;
/** When the server gives no `retry_after`, wait this long before the one retry. */
export const DEFAULT_BACKOFF_S = 2;

export type ItemStatus = 'queued' | 'reading' | 'ok' | 'review' | 'failed' | 'confirmed';

/** Why a row failed, as a code the copy turns into words. */
export type FailCode = 'read' | 'no_affidavit' | 'reader' | 'page_cap' | 'build';

/**
 * One row of the queue. A file starts as one row; once read, it becomes one row per
 * affidavit found in it, because a court file can hold several.
 */
export type QueueItem = {
	id: string;
	/** The file's name, shown on this device only and never sent with the analysis. */
	name: string;
	file: File | null;
	status: ItemStatus;
	extraction: DocumentExtraction | null;
	/** Which affidavit in the extraction this row is. */
	index: number;
	values: Values;
	attempts: AttemptValues[];
	resolved: string[];
	fail: FailCode | null;
	/** A server message worth showing as it is (a typed refusal), else null. */
	message: string | null;
};

let counter = 0;
const nextId = () => `item-${++counter}`;

export function queued(file: File): QueueItem {
	return {
		id: nextId(),
		name: file.name,
		file,
		status: 'queued',
		extraction: null,
		index: 0,
		values: valuesFrom(null),
		attempts: [],
		resolved: [],
		fail: null,
		message: null
	};
}

/**
 * A row for an affidavit the reader could not read, so the person can type it in. Whatever
 * the deterministic validators did get (the method, from the wording) is kept, and the
 * page images stay beside the form.
 */
export function manual(item: QueueItem): QueueItem {
	const draft = item.extraction?.affidavits?.[item.index]?.draft ?? null;
	return {
		...item,
		status: 'review',
		fail: null,
		message: null,
		values: valuesFrom(draft),
		attempts: attemptsFrom(draft),
		resolved: []
	};
}

/**
 * What the engine cannot work without. A row missing any of these needs a person, however
 * confident the reader was about everything else.
 */
const REQUIRED = ['served_date', 'served_time', 'served_address'] as const;

export function missingRequired(values: Values): string[] {
	const missing: string[] = REQUIRED.filter((key) => !(values[key] ?? '').trim());
	if (!(values.server_name ?? '').trim() && !(values.server_license ?? '').trim()) {
		missing.push('server_name');
	}
	return missing;
}

/** The reader itself was down for this file (vision.py's "reader" note). */
export function readerFailed(extraction: DocumentExtraction): boolean {
	return (extraction.notes ?? []).some((note) => note.field === 'reader' && note.level === 'error');
}

/**
 * A read file, as queue rows: one per affidavit found.
 *
 * "ok" means nothing needs a look — no flagged field, nothing required missing — and the
 * row can be confirmed with the rest in one press. Anything else is "review".
 */
export function fromExtraction(item: QueueItem, extraction: DocumentExtraction): QueueItem[] {
	const found = extraction.affidavits ?? [];
	if (readerFailed(extraction)) {
		return [{ ...item, status: 'failed', fail: 'reader', extraction }];
	}
	if (found.length === 0) {
		return [{ ...item, status: 'failed', fail: 'no_affidavit', extraction }];
	}
	return found.map((affidavit, index) => {
		const values = valuesFrom(affidavit.draft);
		const clean = flaggedKeys(affidavit).length === 0 && missingRequired(values).length === 0;
		return {
			...item,
			id: index === 0 ? item.id : nextId(),
			status: clean ? 'ok' : 'review',
			extraction,
			index,
			values,
			attempts: attemptsFrom(affidavit.draft),
			resolved: [],
			fail: null,
			message: null
		};
	});
}

export function draftOf(item: QueueItem): AffidavitDraft | null {
	return item.extraction?.affidavits?.[item.index]?.draft ?? null;
}

/** How many fields on this row the reader flagged. */
export function flagCount(item: QueueItem): number {
	const found = item.extraction?.affidavits?.[item.index] ?? null;
	return flaggedKeys(found).length;
}

/**
 * The defendant's initials, never the name: the queue is a working list on a shared
 * screen in a legal-aid office, and a column of full names is more than the task needs.
 */
export function initials(name: string | null | undefined): string {
	const parts = (name ?? '').trim().split(/\s+/).filter(Boolean);
	if (parts.length === 0) return '—';
	return parts.map((part) => `${part[0]!.toUpperCase()}.`).join(' ');
}

/** Worth one more try: rate-limited, the server or reader briefly down, or the network. */
export function retryable(error: unknown): boolean {
	if (!(error instanceof ApiError)) return false;
	return error.status === 429 || error.status >= 500 || error.code === 'network';
}

export type Sleep = (ms: number) => Promise<void>;
const realSleep: Sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Run once; on a retryable failure wait — what the server asked for, else a default — and
 * run once more. Never a loop: a reader that is down stays down for the rest of a batch,
 * and hammering it would only spend the person's rate budget.
 */
export async function withRetry<T>(
	run: () => Promise<T>,
	sleep: Sleep = realSleep,
	backoffS = DEFAULT_BACKOFF_S
): Promise<T> {
	try {
		return await run();
	} catch (error) {
		if (!retryable(error)) throw error;
		const wait = error instanceof ApiError && error.retryAfter !== null ? error.retryAfter : backoffS;
		await sleep(Math.min(wait, 60) * 1000);
		return await run();
	}
}

/**
 * Run `work` over `items` with at most `limit` in flight, in order of starting. Resolves
 * when everything has settled; `work` is expected to record its own failures.
 */
export async function pool<T>(
	items: readonly T[],
	limit: number,
	work: (item: T) => Promise<void>
): Promise<void> {
	let next = 0;
	const lanes = Array.from({ length: Math.min(limit, items.length) }, async () => {
		while (next < items.length) {
			const item = items[next++]!;
			await work(item);
		}
	});
	await Promise.all(lanes);
}

/** Caps, as the person sees them before anything is read. */
export function admit(
	current: number,
	files: readonly File[]
): { accepted: File[]; refused: number } {
	const room = Math.max(0, MAX_FILES - current);
	return { accepted: files.slice(0, room), refused: Math.max(0, files.length - room) };
}

/** Counts for the queue's header line. */
export function tally(items: readonly QueueItem[]): Record<ItemStatus, number> {
	const counts: Record<ItemStatus, number> = {
		queued: 0,
		reading: 0,
		ok: 0,
		review: 0,
		failed: 0,
		confirmed: 0
	};
	for (const item of items) counts[item.status] += 1;
	return counts;
}

/** The rows the report is built from, in queue order. */
export function confirmedRows(items: readonly QueueItem[]): QueueItem[] {
	return items.filter((item) => item.status === 'confirmed');
}
