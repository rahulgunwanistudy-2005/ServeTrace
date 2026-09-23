/** Time-zone helpers. All display is New York local; all transport is ISO with offset.
 *
 * There is no date library here on purpose (bible §8 pins the stack). Everything below is
 * `Date.parse` for instants and `Intl.DateTimeFormat` for New York local wall-clock time,
 * which is the one thing in the browser that knows when the offset changed.
 */

export const TZ = 'America/New_York';

const displayFormatter = new Intl.DateTimeFormat('en-US', {
	timeZone: TZ,
	dateStyle: 'medium',
	timeStyle: 'short'
});

const timeFormatter = new Intl.DateTimeFormat('en-US', {
	timeZone: TZ,
	hour: 'numeric',
	minute: '2-digit'
});

const dayFormatter = new Intl.DateTimeFormat('en-US', {
	timeZone: TZ,
	year: 'numeric',
	month: '2-digit',
	day: '2-digit'
});

const longDayFormatter = new Intl.DateTimeFormat('en-US', {
	timeZone: TZ,
	weekday: 'short',
	month: 'long',
	day: 'numeric',
	year: 'numeric'
});

export function formatNY(value: Date | string | number): string {
	return displayFormatter.format(toDate(value));
}

export function formatNYTime(value: Date | string | number): string {
	return timeFormatter.format(toDate(value));
}

export function formatNYDay(value: Date | string | number): string {
	return longDayFormatter.format(toDate(value));
}

function toDate(value: Date | string | number): Date {
	return value instanceof Date ? value : new Date(value);
}

/**
 * Parse an ISO instant to epoch milliseconds, or null.
 *
 * Google writes every timestamp with an offset, which makes this unambiguous — but a
 * hand-edited file or a different export may not, and `Date.parse` would then read it as
 * *local* time on whatever machine the browser is running on. A user in Los Angeles
 * checking a New York affidavit would have their day shifted three hours. So an offset is
 * required, and a timestamp without one is treated as unreadable rather than guessed at.
 */
export function toEpochMs(iso: string): number | null {
	if (!HAS_OFFSET.test(iso)) return null;
	const ms = Date.parse(iso);
	return Number.isNaN(ms) ? null : ms;
}

const HAS_OFFSET = /(?:Z|[+-]\d{2}:?\d{2})$/i;

/**
 * The New York calendar date of an instant, as `YYYY-MM-DD`.
 *
 * "Does my export cover 12 June?" is a question about the date printed on the affidavit,
 * so it has to be answered in the affidavit's time zone and not in UTC: 8pm on 12 June in
 * New York is already 13 June in UTC, and half the evening would answer the wrong day.
 */
export function nyDayKey(value: Date | string | number): string {
	const parts = dayFormatter.formatToParts(toDate(value));
	const get = (type: string) => parts.find((p) => p.type === type)?.value ?? '';
	return `${get('year')}-${get('month')}-${get('day')}`;
}

const DAY_MS = 86_400_000;
const MAX_DAYS_SPANNED = 400;

/**
 * Every New York date an interval touches, inclusive.
 *
 * A visit that starts before midnight and ends after it covers both days, and a work shift
 * recorded as one visit is exactly that. Counting only the start day would report an
 * export as not covering the day it plainly covers.
 */
export function nyDaysSpanned(startMs: number, endMs: number): string[] {
	const days: string[] = [];
	const first = nyDayKey(startMs);
	days.push(first);
	if (endMs <= startMs) return days;

	// Step by a day at a time from the start; DST makes some of those steps 23 or 25 hours
	// long, so the day key is recomputed each step rather than counted arithmetically.
	let cursor = startMs;
	const last = nyDayKey(endMs);
	for (let i = 0; i < MAX_DAYS_SPANNED; i += 1) {
		if (days[days.length - 1] === last) break;
		cursor += DAY_MS;
		const key = nyDayKey(cursor);
		if (key !== days[days.length - 1]) days.push(key);
	}
	return days;
}

const wallFormatter = new Intl.DateTimeFormat('en-US', {
	timeZone: TZ,
	hour12: false,
	year: 'numeric',
	month: '2-digit',
	day: '2-digit',
	hour: '2-digit',
	minute: '2-digit',
	second: '2-digit'
});

/** The New York wall clock at an instant, expressed as if it were a UTC timestamp. */
function wallAsUtcMs(instantMs: number): number {
	const parts = wallFormatter.formatToParts(new Date(instantMs));
	const get = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? '0');
	// Intl renders midnight as hour 24 in the hour12:false locale; both mean the same day.
	const hour = get('hour') % 24;
	return Date.UTC(get('year'), get('month') - 1, get('day'), hour, get('minute'), get('second'));
}

/** New York's UTC offset at an instant, in milliseconds (negative: behind UTC). */
function offsetAtMs(instantMs: number): number {
	return wallAsUtcMs(instantMs) - instantMs;
}

export type NyLocalInstant = {
	iso: string;
	/** The wall clock happened twice that day (the autumn fold). The earlier one is used. */
	ambiguous: boolean;
	/** The wall clock never happened (the spring gap). It is moved forward past the gap. */
	nonexistent: boolean;
};

const TWELVE_H = 43_200_000;

/**
 * Turn a New York wall-clock date and time — `2025-06-12`, `19:42` — into an instant.
 *
 * A typed-in entry and a bank statement row have no offset in them, and the offset that
 * applied depends on the date. Rather than guess, both candidate offsets are tried and
 * each is checked by rendering it back: on the autumn fold both survive and the earlier is
 * taken; in the spring gap neither does and the time is moved past the gap. Both cases are
 * reported so the UI can say so instead of silently moving the user's evening by an hour.
 */
export function nyLocalToInstant(date: string, time: string): NyLocalInstant | null {
	const day = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date.trim());
	const clock = /^(\d{1,2}):(\d{2})(?::(\d{2}))?$/.exec(time.trim());
	if (!day || !clock) return null;

	const [year, month, dayOfMonth] = [Number(day[1]), Number(day[2]), Number(day[3])];
	const [hour, minute, second] = [Number(clock[1]), Number(clock[2]), Number(clock[3] ?? 0)];
	if (month < 1 || month > 12 || dayOfMonth < 1 || dayOfMonth > 31) return null;
	if (hour > 23 || minute > 59 || second > 59) return null;

	const wall = Date.UTC(year, month - 1, dayOfMonth, hour, minute, second);
	// A calendar date that does not exist (31 February) rolls over in Date.UTC; catching it
	// here keeps a typo from becoming a confident wrong answer.
	const rolled = new Date(wall);
	if (rolled.getUTCMonth() !== month - 1 || rolled.getUTCDate() !== dayOfMonth) return null;

	// Probe the zone either side of the wall time; on a transition day the two disagree,
	// and that disagreement is exactly what makes a wall clock ambiguous or impossible.
	const offsets = [offsetAtMs(wall - TWELVE_H), offsetAtMs(wall + TWELVE_H)];
	const candidates = [...new Set(offsets.map((offset) => wall - offset))].sort((a, b) => a - b);
	const valid = candidates.filter((candidate) => wallAsUtcMs(candidate) === wall);

	// Ambiguous: the earlier of the two readings. Impossible: forward past the gap, which is
	// what every time library does with 02:30 on the spring-forward day and what a person
	// writing "half past two" on that morning would have meant.
	const chosen = valid[0] ?? candidates[candidates.length - 1];
	if (chosen === undefined) return null;
	return {
		iso: new Date(chosen).toISOString(),
		ambiguous: valid.length > 1,
		nonexistent: valid.length === 0
	};
}

/**
 * Parse a Google Timeline coordinate string.
 *
 * Android writes `"40.7580123°, -73.9855123°"`; iOS writes `"geo:40.7580123,-73.9855123"`.
 * Returns null rather than throwing, because a single malformed row in a 200 MB export
 * must not abort the whole import.
 */
export function parseLatLng(raw: string): { lat: number; lng: number } | null {
	const cleaned = raw.trim().replace(/^geo:/i, '').replace(/°/g, '');
	const parts = cleaned.split(',');
	if (parts.length !== 2) return null;
	const lat = Number(parts[0]?.trim());
	const lng = Number(parts[1]?.trim());
	if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
	if (lat < -90 || lat > 90 || lng < -180 || lng > 180) return null;
	return { lat, lng };
}
