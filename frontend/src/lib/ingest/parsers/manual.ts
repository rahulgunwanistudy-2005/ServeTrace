/**
 * Manual entries: "I was at work from 8:00 to 20:00 at <address>". Bible §13.
 *
 * This is the path for someone whose phone had Timeline switched off, and it must be as
 * usable as the others: a person who was at their sister's until nine has evidence, and it
 * being typed rather than exported does not make it worthless. It is labelled for what it
 * is, so nobody reading the packet can mistake a typed entry for a recorded one.
 */

import { ingestWarnings } from '$copy/en';

import { nyLocalToInstant } from '../tz';
import type { PendingFix } from '../types';

export type ManualEntry = {
	/** `YYYY-MM-DD`, New York local. */
	date: string;
	/** `HH:MM`, New York local. */
	from: string;
	to: string;
	address: string;
	label?: string;
};

export type ManualParseResult = {
	pending: PendingFix[];
	skipped: number;
	warnings: string[];
};

const DAY_MS = 86_400_000;

export function parseManual(entries: ManualEntry[]): ManualParseResult {
	const pending: PendingFix[] = [];
	const warnings: string[] = [];
	let skipped = 0;
	let ambiguous = 0;

	for (const entry of entries) {
		const address = entry.address.trim();
		const start = nyLocalToInstant(entry.date, entry.from);
		const end = nyLocalToInstant(entry.date, entry.to);
		if (!address || !start || !end) {
			skipped += 1;
			continue;
		}
		if (start.ambiguous || end.ambiguous || start.nonexistent || end.nonexistent) {
			ambiguous += 1;
		}

		// "From 20:00 to 02:00" is one evening, not a negative six hours.
		const startMs = Date.parse(start.iso);
		const endMs = Date.parse(end.iso);
		const finish = endMs < startMs ? endMs + DAY_MS : endMs;

		pending.push({
			t: start.iso,
			t_end: new Date(finish).toISOString(),
			address,
			accuracy_m: null,
			kind: 'manual',
			source: 'manual',
			label: entry.label?.trim() || 'Typed in by you'
		});
	}

	if (skipped > 0) warnings.push(ingestWarnings.manualIncomplete(skipped));
	if (ambiguous > 0) warnings.push(ingestWarnings.clocksChanged(ambiguous));

	return { pending, skipped, warnings };
}
