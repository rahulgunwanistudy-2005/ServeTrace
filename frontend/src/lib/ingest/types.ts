/**
 * Browser-side mirrors of the backend contracts in `domain/models.py`, plus the protocol
 * the ingest worker speaks.
 *
 * These are hand-written only until `npm run gen:types` has run against a backend that
 * exposes them; from then on the generated `schema.d.ts` is the source of truth.
 */

export type LatLng = { lat: number; lng: number };

export type FixKind = 'visit' | 'path' | 'transaction' | 'manual';

export type LocationFix = {
	t: string;
	t_end?: string | null;
	loc: LatLng;
	accuracy_m?: number | null;
	kind: FixKind;
	source: string;
	label?: string | null;
};

/**
 * A fix that knows *where* only as an address. A statement row and a typed-in entry both
 * arrive this way, and stay this way until `resolve.ts` is given a geocoder.
 *
 * Keeping the unresolved form in the type system is what lets every parser be a pure
 * function: nothing in this directory can reach the network by accident.
 */
export type PendingFix = Omit<LocationFix, 'loc'> & { address: string };

export type IngestFormat = 'google_android' | 'google_ios';

/** Every way ingest can fail, so the UI switches on a code and never on message text. */
export type IngestErrorCode =
	| 'unsupported_format'
	| 'file_too_large'
	| 'empty_file'
	| 'malformed_json'
	| 'no_fixes'
	| 'cancelled';

export class IngestError extends Error {
	readonly code: IngestErrorCode;

	constructor(code: IngestErrorCode, message: string) {
		super(message);
		this.name = 'IngestError';
		this.code = code;
	}
}

/**
 * What the user is told about their own file — computed over the *whole* export, even
 * though only the windowed fixes are kept.
 *
 * `daysCovered` is a sorted list of New York local dates (`YYYY-MM-DD`), because "does
 * this export cover 12 June?" is a question about the calendar the affidavit was written
 * in, not about UTC.
 */
export type IngestStats = {
	/** Distinct location points in the whole file, duplicates merged. */
	total: number;
	/** True when the file held more points than could be counted exactly (`stats.ts`). */
	totalIsApproximate: boolean;
	kept: number;
	firstAt: string | null;
	lastAt: string | null;
	daysCovered: string[];
	claimedDaysMissing: string[];
	bytesRead: number;
	skipped: number;
};

export type ParseResult = {
	fixes: LocationFix[];
	stats: IngestStats;
	warnings: string[];
};

/** The worker's inbound message. `claims` are the affidavit's claimed instants (ISO). */
export type IngestRequest = {
	type: 'parse';
	file: File;
	format?: IngestFormat;
	claims?: string[];
	windowHours?: number;
};

export type IngestResponse =
	| { type: 'progress'; bytesRead: number; totalBytes: number; fixes: number }
	| { type: 'done'; fixes: LocationFix[]; stats: IngestStats; warnings: string[] }
	| { type: 'error'; code: IngestErrorCode; message: string };

export const EMPTY_STATS: IngestStats = {
	total: 0,
	totalIsApproximate: false,
	kept: 0,
	firstAt: null,
	lastAt: null,
	daysCovered: [],
	claimedDaysMissing: [],
	bytesRead: 0,
	skipped: 0
};
