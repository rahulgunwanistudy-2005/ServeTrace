/**
 * Guessing which column is which, so the advocate confirms rather than configures.
 *
 * Column mapping is the step that loses people. Twelve dropdowns on a blank form is a
 * form; twelve dropdowns already filled in is a review, and a review takes ten seconds.
 * So this guesses from the header names, shows what it guessed, and lets every one of
 * them be changed.
 *
 * It is deliberately a pure function of the header list. The engine never sees it — the
 * server validates the mapping it is handed either way — which means being wrong here
 * costs a correction and never a wrong answer.
 */

import type { AdvocateColumnMapping } from '$lib/api/client';

export type MappableField = keyof AdvocateColumnMapping;

/** Every field the mapping can name, in the order the form shows them. */
export const FIELDS: readonly MappableField[] = [
	'server_id',
	'at',
	'date',
	'time',
	'lat',
	'lng',
	'address',
	'case_ref',
	'outcome',
	'recipient_desc'
] as const;

export const REQUIRED_FIELDS: readonly MappableField[] = ['server_id'] as const;

/**
 * What each field's column is called out there.
 *
 * Ordered most specific first, because matching is first-hit: `service_date` must reach
 * `date` before a looser `at` rule claims it. The names come from what these exports
 * actually look like — a licence number column, a "server" column, a "process server"
 * column — rather than from what a schema designer would have chosen.
 */
const SYNONYMS: Record<MappableField, readonly string[]> = {
	server_id: [
		'server_id',
		'serverid',
		'process server',
		'processserver',
		'server license',
		'license',
		'licence',
		'server name',
		'server',
		'agent'
	],
	at: [
		'service_datetime',
		'servicedatetime',
		'datetime',
		'date time',
		'timestamp',
		'served at',
		'service date time',
		'date_served',
		'served'
	],
	date: ['service_date', 'servicedate', 'date of service', 'date'],
	time: ['service_time', 'servicetime', 'time of service', 'time'],
	lat: ['latitude', 'lat', 'gps_lat', 'y'],
	lng: ['longitude', 'lng', 'lon', 'long', 'gps_lng', 'x'],
	address: ['service address', 'address', 'location', 'street', 'premises'],
	case_ref: ['case_number', 'case number', 'case', 'index number', 'index', 'docket', 'matter'],
	outcome: ['outcome', 'result', 'status', 'disposition', 'service type'],
	recipient_desc: [
		'person_served_description',
		'person served description',
		'recipient description',
		'description',
		'person served',
		'recipient'
	]
};

/** Case, spacing and punctuation must not stop `Service Date/Time` matching `datetime`. */
function normalize(header: string): string {
	return header
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, ' ')
		.trim();
}

function scoreHeader(header: string, synonyms: readonly string[]): number {
	const normalized = normalize(header);
	for (let i = 0; i < synonyms.length; i += 1) {
		const synonym = normalize(synonyms[i]!);
		// An exact name beats a containment, and an earlier synonym beats a later one, so
		// `service_date` reaches `date` before `served` can claim it for `at`.
		if (normalized === synonym) return 1000 - i;
		if (normalized.includes(synonym)) return 500 - i;
	}
	return 0;
}

/**
 * The best guess at which header is which field.
 *
 * Each header is used at most once: a file with a single `date` column must not have it
 * claimed by both `at` and `date`, because the mapping means something different then.
 * Fields are filled in `FIELDS` order and the strongest match for each wins.
 */
export function guessColumns(headers: readonly string[]): AdvocateColumnMapping {
	const taken = new Set<string>();
	const guess: Record<string, string | undefined> = {};

	for (const field of FIELDS) {
		let best: { header: string; score: number } | null = null;
		for (const header of headers) {
			if (taken.has(header)) continue;
			const score = scoreHeader(header, SYNONYMS[field]);
			if (score > 0 && (best === null || score > best.score)) best = { header, score };
		}
		if (best) {
			guess[field] = best.header;
			taken.add(best.header);
		}
	}

	// A file with one combined date-and-time column has no separate date or time to give,
	// and offering both to the server would be ambiguous about which it should believe.
	if (guess.at) {
		delete guess.date;
		delete guess.time;
	}

	return { server_id: guess.server_id ?? '', ...guess } as AdvocateColumnMapping;
}

/** The same two rules the server enforces, so the button can be disabled before the trip. */
export function hasTime(mapping: AdvocateColumnMapping): boolean {
	return Boolean(mapping.at) || Boolean(mapping.date && mapping.time);
}

export function hasPlace(mapping: AdvocateColumnMapping): boolean {
	return Boolean(mapping.lat && mapping.lng) || Boolean(mapping.address);
}

export function isComplete(mapping: AdvocateColumnMapping): boolean {
	return Boolean(mapping.server_id) && hasTime(mapping) && hasPlace(mapping);
}

/**
 * What is still missing, as field names the copy module can label.
 *
 * Returned rather than rendered so the sentence stays in `copy/en.ts`, and so a test can
 * assert the rule without reading any English.
 */
export function missingFields(mapping: AdvocateColumnMapping): MappableField[] {
	const missing: MappableField[] = [];
	if (!mapping.server_id) missing.push('server_id');
	if (!hasTime(mapping)) missing.push('at');
	if (!hasPlace(mapping)) missing.push('address');
	return missing;
}
