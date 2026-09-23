/**
 * Windowing. Bible §13: only fixes within ±3h of a claimed time ever leave the device.
 *
 * This is the privacy boundary of the whole product, so it lives in one small function
 * with its own tests, and the UI reports the numbers it returns.
 */

import { dedupeFixes, sortFixes } from './dedupe';
import type { LocationFix } from './types';

export const SEARCH_WINDOW_H = 3;

/** Bible §16: the analyze request carries at most this many fixes. */
export const MAX_FIXES = 5_000;

const HOUR_MS = 3_600_000;

export type WindowResult = {
	kept: LocationFix[];
	/** How many fixes the file held, before windowing. The user is told both numbers. */
	total: number;
	/** How many were dropped purely to stay under the cap, so that is never silent. */
	dropped: number;
};

function instant(value: string): number {
	return Date.parse(value);
}

/**
 * How far a fix is from the nearest claim, in milliseconds. Zero when it covers one.
 *
 * An interval that spans a claimed time is the strongest evidence in the file, so it must
 * never be the thing dropped at the cap: this returns 0 for it, which sorts it first.
 */
function distanceToClaims(fix: LocationFix, claims: number[]): number {
	const start = instant(fix.t);
	const end = fix.t_end ? instant(fix.t_end) : start;
	let best = Number.POSITIVE_INFINITY;
	for (const claim of claims) {
		const gap = claim < start ? start - claim : claim > end ? claim - end : 0;
		if (gap < best) best = gap;
	}
	return best;
}

export function windowFixes(
	fixes: LocationFix[],
	claimTimes: (Date | string)[],
	windowHours: number = SEARCH_WINDOW_H,
	maxFixes: number = MAX_FIXES
): WindowResult {
	const claims = claimTimes.map((t) => (typeof t === 'string' ? new Date(t) : t).getTime());
	const span = windowHours * HOUR_MS;

	const inWindow = fixes.filter((fix) => {
		const start = instant(fix.t);
		const end = fix.t_end ? instant(fix.t_end) : start;
		if (Number.isNaN(start) || Number.isNaN(end)) return false;
		// An interval counts when it overlaps the window, not only when it starts inside it:
		// an eight-hour visit covering the claim would otherwise be dropped.
		return claims.some((claim) => start <= claim + span && end >= claim - span);
	});

	const deduped = dedupeFixes(inWindow);
	if (deduped.length <= maxFixes) {
		return { kept: deduped, total: fixes.length, dropped: 0 };
	}

	// Over the cap: keep the fixes nearest the claimed times. Sorting by distance to the
	// claim rather than truncating the list means what survives is the evidence about the
	// moment in dispute, and never an arbitrary first five thousand.
	const ranked = [...deduped].sort(
		(a, b) => distanceToClaims(a, claims) - distanceToClaims(b, claims) || instant(a.t) - instant(b.t)
	);
	return {
		kept: sortFixes(ranked.slice(0, maxFixes)),
		total: fixes.length,
		dropped: deduped.length - maxFixes
	};
}
