/**
 * Card or bank statement CSV. Bible §13.
 *
 * Only the address column is ever read. The amount column is not parsed, not carried and
 * not sent anywhere — not because it would be rejected further down, but because a value
 * that is never read cannot leak. What a person spent is nobody's business here; where the
 * shop was is the only thing that bears on the affidavit.
 *
 * A row becomes a fix only when it has a date, a time and an address. A purchase with no
 * time places someone on a day, not at an hour, and the claimed service is an hour — so
 * those rows are counted and reported rather than quietly given a time they never had.
 */

import Papa from 'papaparse';

import { ingestWarnings } from '$copy/en';

import { nyLocalToInstant } from '../tz';
import type { PendingFix } from '../types';

export type ColumnMap = {
	date: string;
	time?: string;
	merchant?: string;
	address?: string;
};

export type CsvParseResult = {
	pending: PendingFix[];
	/** Rows that could not be placed: no address, no time, or an unreadable date. */
	skipped: number;
	warnings: string[];
};

/** Bible §13: a card transaction is a coarse location, and is scored as one. */
export const TRANSACTION_ACCURACY_M = 500;

/** The column names in the file, for the mapping UI to offer. */
export function readCsvHeaders(text: string): string[] {
	const result = Papa.parse<Record<string, string>>(text, {
		header: true,
		skipEmptyLines: 'greedy',
		preview: 1
	});
	return result.meta.fields ?? [];
}

export function parseCardCsv(text: string, columns: ColumnMap): CsvParseResult {
	const parsed = Papa.parse<Record<string, string>>(text, {
		header: true,
		skipEmptyLines: 'greedy'
	});

	const warnings: string[] = [];
	if (!columns.address) {
		return {
			pending: [],
			skipped: parsed.data.length,
			warnings: [ingestWarnings.csvNeedsAddress]
		};
	}

	const pending: PendingFix[] = [];
	let skipped = 0;
	let ambiguous = 0;

	for (const row of parsed.data) {
		const date = (row[columns.date] ?? '').trim();
		const time = columns.time ? (row[columns.time] ?? '').trim() : '';
		const address = (row[columns.address] ?? '').trim();

		if (!date || !time || !address) {
			skipped += 1;
			continue;
		}

		const instant = nyLocalToInstant(date, normaliseTime(time));
		if (!instant) {
			skipped += 1;
			continue;
		}
		if (instant.ambiguous || instant.nonexistent) ambiguous += 1;

		pending.push({
			t: instant.iso,
			t_end: null,
			address,
			accuracy_m: TRANSACTION_ACCURACY_M,
			kind: 'transaction',
			source: 'card_csv',
			label: columns.merchant ? ((row[columns.merchant] ?? '').trim() || null) : null
		});
	}

	if (skipped > 0) warnings.push(ingestWarnings.csvRowsSkipped(skipped));
	if (ambiguous > 0) warnings.push(ingestWarnings.clocksChanged(ambiguous));
	if (parsed.errors.length > 0) warnings.push(ingestWarnings.csvMisshapenLines);

	return { pending, skipped, warnings };
}

/** `7:05 PM`, `19:05`, `19:05:33` all mean a time of day; only one of them parses as one. */
function normaliseTime(raw: string): string {
	const meridiem = /^(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AaPp])\.?[Mm]\.?$/.exec(raw.trim());
	if (!meridiem) return raw;

	const hour12 = Number(meridiem[1]) % 12;
	const hour = meridiem[4]?.toLowerCase() === 'p' ? hour12 + 12 : hour12;
	return `${String(hour).padStart(2, '0')}:${meridiem[2]}:${meridiem[3] ?? '00'}`;
}
