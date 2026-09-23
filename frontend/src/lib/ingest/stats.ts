/**
 * What the user is told about their own file.
 *
 * The numbers here describe the *whole* export even though only a few hours of it are
 * kept, and they are accumulated one fix at a time so that describing a 150 MB file costs
 * no more memory than describing a small one.
 *
 * The question this exists to answer early is "does your export even cover that evening?".
 * Finding that out after three steps of a wizard is a bad experience; finding it out on the
 * screen where the file is dropped is a useful one.
 */

import { fixKey } from './dedupe';
import { nyDayKey, nyDaysSpanned } from './tz';
import { EMPTY_STATS, type IngestStats, type LocationFix } from './types';

/**
 * How many distinct points may be tracked before the count stops being exact.
 *
 * An Android export records each journey point twice — once in the path, once as a raw
 * signal — so counting records would tell someone their quiet Tuesday holds twice the
 * points it does. Deduplicating needs a key per point, and a key per point is memory, so
 * it is bounded: past this many the count carries on without deduplicating and says so.
 * Half a million distinct points is several years of ordinary history.
 */
export const MAX_DISTINCT_TRACKED = 500_000;

export class StatsAccumulator {
	private total = 0;
	private skipped = 0;
	private firstMs: number | null = null;
	private lastMs: number | null = null;
	private approximate = false;
	private readonly days = new Set<string>();
	private readonly seen = new Set<string>();

	add(fix: LocationFix): void {
		const start = Date.parse(fix.t);
		if (Number.isNaN(start)) {
			this.skipped += 1;
			return;
		}
		if (this.seen.size < MAX_DISTINCT_TRACKED) {
			const key = fixKey(fix);
			if (this.seen.has(key)) return;
			this.seen.add(key);
		} else {
			this.approximate = true;
		}
		const end = fix.t_end ? Date.parse(fix.t_end) : start;
		this.total += 1;
		if (this.firstMs === null || start < this.firstMs) this.firstMs = start;
		const latest = Number.isNaN(end) ? start : end;
		if (this.lastMs === null || latest > this.lastMs) this.lastMs = latest;
		for (const day of nyDaysSpanned(start, latest)) this.days.add(day);
	}

	addSkipped(n: number): void {
		this.skipped += n;
	}

	/** `claims` are the affidavit's claimed instants; `kept` is what survived windowing. */
	finish(claims: string[], kept: number, bytesRead: number): IngestStats {
		const claimedDays = [...new Set(claims.map((claim) => nyDayKey(claim)))].sort();
		return {
			...EMPTY_STATS,
			total: this.total,
			totalIsApproximate: this.approximate,
			kept,
			bytesRead,
			skipped: this.skipped,
			firstAt: this.firstMs === null ? null : new Date(this.firstMs).toISOString(),
			lastAt: this.lastMs === null ? null : new Date(this.lastMs).toISOString(),
			daysCovered: [...this.days].sort(),
			claimedDaysMissing: claimedDays.filter((day) => !this.days.has(day))
		};
	}
}

/** Build stats for a list of fixes already in memory (manual entries, a CSV, a test). */
export function statsFor(
	fixes: LocationFix[],
	claims: string[] = [],
	kept = fixes.length,
	bytesRead = 0
): IngestStats {
	const accumulator = new StatsAccumulator();
	for (const fix of fixes) accumulator.add(fix);
	return accumulator.finish(claims, kept, bytesRead);
}
