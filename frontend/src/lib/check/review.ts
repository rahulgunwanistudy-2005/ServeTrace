/**
 * The logic of the flagged-first review screen, kept out of the components so it can be
 * tested without a DOM. Build prompt §4.3; bible §14.2.
 *
 * The screen exists so a person can check what a model read off their papers quickly and
 * without missing anything. Everything here serves one of those two words:
 *
 * - **Quickly:** only the fields that need a human look are shown by default, in the
 *   order they appear on the form, and each one points at the words on the page.
 * - **Without missing anything:** "Confirm all" stays closed until every flagged field has
 *   been looked at — accepted as read, or changed.
 */

import type {
	AffidavitDraft,
	DocumentExtraction,
	ExtractedAffidavit,
	FieldEvidence,
	PageType,
	ValidationNote
} from '$lib/api/client';
import { nyClockKey, nyDayKey } from '$lib/ingest/tz';

/** Bible §14.2: below this a field is flagged and shows the words it was read from. */
export const UNSURE_BELOW = 0.8;

export type FieldKind = 'text' | 'date' | 'time' | 'method' | 'outcome' | 'readonly';

export type FieldSpec = { key: string; kind: FieldKind; wide?: boolean };

/**
 * Every field the person can check, in the order an affidavit of service prints them:
 * caption first, then the server, then the service itself, then the mailing.
 */
export const FIELDS: readonly FieldSpec[] = [
	{ key: 'index_number', kind: 'text' },
	{ key: 'court', kind: 'text', wide: true },
	{ key: 'plaintiff', kind: 'text' },
	{ key: 'defendant_name', kind: 'text' },
	{ key: 'server_name', kind: 'text' },
	{ key: 'server_license', kind: 'text' },
	{ key: 'agency_name', kind: 'text', wide: true },
	{ key: 'method', kind: 'method', wide: true },
	{ key: 'served_date', kind: 'date' },
	{ key: 'served_time', kind: 'time' },
	{ key: 'served_address', kind: 'text', wide: true },
	{ key: 'recipient_name', kind: 'text' },
	{ key: 'recipient_relationship', kind: 'text' },
	{ key: 'recipient_description', kind: 'readonly', wide: true },
	{ key: 'mailing_date', kind: 'date' },
	{ key: 'mailing_address', kind: 'text', wide: true },
	{ key: 'proof_filed_date', kind: 'date' }
];

export type Values = Record<string, string>;

/** One prior attempt, as the person edits it. */
export type AttemptValues = { date: string; time: string; address: string; outcome: string };

export const OUTCOMES = ['not_home', 'refused', 'served', 'affixed', 'other'] as const;

function text(value: unknown): string {
	return typeof value === 'string' ? value : '';
}

/** The fields as strings, which is what an input holds and what a partial read produces. */
export function valuesFrom(draft: AffidavitDraft | null | undefined): Values {
	const read = (draft ?? {}) as Record<string, unknown>;
	const values: Values = {};
	for (const field of FIELDS) {
		if (field.kind === 'readonly') continue;
		values[field.key] = text(read[field.key]);
	}
	values.method ||= 'unknown';
	// The validators fill `served_at` from the date and time they could parse. When only
	// the instant survived, show it back in New York wall-clock, never the browser's.
	if (draft?.served_at) {
		const at = new Date(draft.served_at);
		values.served_date ||= nyDayKey(at);
		values.served_time ||= nyClockKey(at);
	}
	return values;
}

export function attemptsFrom(draft: AffidavitDraft | null | undefined): AttemptValues[] {
	return (draft?.attempts ?? []).map((attempt) => {
		const at = attempt.at ? new Date(attempt.at) : null;
		return {
			date: text(attempt.at_date) || (at ? nyDayKey(at) : ''),
			time: text(attempt.at_time) || (at ? nyClockKey(at) : ''),
			address: text(attempt.address),
			outcome: (OUTCOMES as readonly string[]).includes(text(attempt.outcome))
				? text(attempt.outcome)
				: 'other'
		};
	});
}

export function attemptKey(index: number): string {
	return `attempts[${index}]`;
}

/** The validator's notes about one field. Deterministic, so they outrank a score. */
export function notesFor(found: ExtractedAffidavit | null, key: string): ValidationNote[] {
	return (found?.notes ?? []).filter((note) => note.field === key);
}

/** Flagged: the reader was unsure (< 0.8), or a validator had something to say. */
export function isFlagged(found: ExtractedAffidavit | null, key: string): boolean {
	if (!found) return false;
	const score = found.draft.field_confidence?.[key];
	if (typeof score === 'number' && score < UNSURE_BELOW) return true;
	return notesFor(found, key).length > 0;
}

/** Every field and attempt that needs a look, in reading order. */
export function flaggedKeys(found: ExtractedAffidavit | null): string[] {
	if (!found) return [];
	const keys = FIELDS.map((f) => f.key).filter((key) => isFlagged(found, key));
	(found.draft.attempts ?? []).forEach((_, i) => {
		if (isFlagged(found, attemptKey(i))) keys.push(attemptKey(i));
	});
	return keys;
}

/** What still blocks "Confirm all": flagged keys nobody has accepted or changed yet. */
export function unresolved(flagged: readonly string[], resolved: ReadonlySet<string>): string[] {
	return flagged.filter((key) => !resolved.has(key));
}

/** Where the words for a field are, if the reader said. */
export function evidenceFor(
	found: ExtractedAffidavit | null,
	key: string
): FieldEvidence | null {
	if (!found) return null;
	const known = found.draft.evidence?.[key];
	if (known) return known;
	const quote = found.draft.evidence_quotes?.[key];
	return quote ? { quote, page: null, bbox: null } : null;
}

/** The page to show for a field: its evidence page, else the first page of its affidavit. */
export function pageFor(found: ExtractedAffidavit | null, key: string): number {
	const page = evidenceFor(found, key)?.page;
	if (typeof page === 'number') return page;
	return found?.pages?.[0] ?? 0;
}

/**
 * A box in PDF points as percentages of the page, so it scales with whatever size the
 * preview is drawn at. A little padding, because a box drawn tight to the glyphs hides
 * the very words it is pointing at.
 */
export function boxStyle(
	bbox: readonly number[],
	page: { width: number; height: number },
	pad = 3
): { left: number; top: number; width: number; height: number } | null {
	const [x0, top, x1, bottom] = bbox;
	if (
		x0 === undefined ||
		top === undefined ||
		x1 === undefined ||
		bottom === undefined ||
		page.width <= 0 ||
		page.height <= 0
	) {
		return null;
	}
	const clamp = (n: number) => Math.min(100, Math.max(0, n));
	const left = clamp(((x0 - pad) / page.width) * 100);
	const right = clamp(((x1 + pad) / page.width) * 100);
	const upper = clamp(((top - pad) / page.height) * 100);
	const lower = clamp(((bottom + pad) / page.height) * 100);
	return { left, top: upper, width: right - left, height: lower - upper };
}

/** A short line naming one affidavit, for choosing between several in one file. */
export function describeAffidavit(found: ExtractedAffidavit): {
	pages: string;
	name: string;
	date: string;
} {
	const pages = found.pages ?? [];
	const first = pages[0];
	const last = pages[pages.length - 1];
	return {
		pages:
			first === undefined
				? ''
				: first === last
					? `${first + 1}`
					: `${first + 1}–${(last ?? first) + 1}`,
		name: text(found.draft.defendant_name),
		date: text(found.draft.served_date)
	};
}

/**
 * The pages whose label the person changed. Re-reading goes to the server with the whole
 * new labelling and these pages only, so an affidavit nobody touched is not read again.
 */
export function changedPages(before: readonly PageType[], after: readonly PageType[]): number[] {
	const changed: number[] = [];
	after.forEach((type, i) => {
		if (before[i] !== type) changed.push(i);
	});
	return changed;
}

/**
 * The pages to read again: the ones re-labelled, plus every page of an affidavit that
 * touched them. Un-tagging the second page of a two-page affidavit must re-read the first
 * page on its own, or the affidavit would vanish rather than shrink.
 */
export function retagPages(current: DocumentExtraction, changed: readonly number[]): number[] {
	const pages = new Set(changed);
	for (const found of current.affidavits ?? []) {
		if ((found.pages ?? []).some((page) => changed.includes(page))) {
			for (const page of found.pages ?? []) pages.add(page);
		}
	}
	return [...pages].sort((a, b) => a - b);
}

/**
 * Fold a re-read range back into the extraction: affidavits touching the changed pages
 * are replaced by what the server read now; the rest are kept exactly as they were.
 */
export function mergeRetag(
	current: DocumentExtraction,
	reread: DocumentExtraction,
	pages: readonly number[]
): DocumentExtraction {
	const touched = new Set(pages);
	const untouched = (current.affidavits ?? []).filter(
		(found) =>
			!(found.pages ?? []).some((page) => touched.has(page)) &&
			// An affidavit the new labels split or extended is replaced, not duplicated.
			!(reread.affidavits ?? []).some((fresh) =>
				(fresh.pages ?? []).some((page) => (found.pages ?? []).includes(page))
			) &&
			(found.pages ?? []).every((page) => reread.page_types[page] === 'affidavit_of_service')
	);
	const affidavits = [...untouched, ...(reread.affidavits ?? [])].sort(
		(a, b) => (a.pages?.[0] ?? 0) - (b.pages?.[0] ?? 0)
	);
	const judgmentTouched = pages.some(
		(page) => current.page_types[page] === 'judgment' || reread.page_types[page] === 'judgment'
	);
	return {
		...current,
		page_types: reread.page_types,
		affidavits,
		judgment_entry_date: judgmentTouched
			? reread.judgment_entry_date
			: current.judgment_entry_date,
		judgment_evidence: judgmentTouched ? reread.judgment_evidence : current.judgment_evidence,
		notes: reread.notes,
		used_vision: current.used_vision || reread.used_vision
	};
}

/**
 * Seconds from the review appearing to "Confirm all". Development builds only: the
 * target is under two minutes per affidavit, and this is how that gets measured.
 */
export function startReviewTimer(
	now: () => number = () => performance.now(),
	log: (message: string) => void = (message) => console.info(message)
): { stop: (label: string) => number } {
	const started = now();
	let stopped = false;
	return {
		stop(label: string) {
			const seconds = Math.round((now() - started) / 100) / 10;
			if (!stopped) log(`[review-timer] ${label}: ${seconds}s to confirm`);
			stopped = true;
			return seconds;
		}
	};
}
