/**
 * Windowing. Bible §13: only fixes within ±3h of a claimed time ever leave the device.
 *
 * This is the privacy boundary of the whole product, so it lives in one small function
 * with its own tests, and the UI reports the numbers it returns.
 */

import type { LocationFix } from './types';

export const SEARCH_WINDOW_H = 3;

const HOUR_MS = 3_600_000;

export type WindowResult = {
	kept: LocationFix[];
	total: number;
};

export function windowFixes(
	fixes: LocationFix[],
	claimTimes: (Date | string)[],
	windowHours: number = SEARCH_WINDOW_H
): WindowResult {
	const claims = claimTimes.map((t) => (typeof t === 'string' ? new Date(t) : t).getTime());
	const span = windowHours * HOUR_MS;

	const kept = fixes.filter((fix) => {
		const start = new Date(fix.t).getTime();
		const end = fix.t_end ? new Date(fix.t_end).getTime() : start;
		// An interval counts when it overlaps the window, not only when it starts inside it:
		// an eight-hour visit covering the claim would otherwise be dropped.
		return claims.some((claim) => start <= claim + span && end >= claim - span);
	});

	return { kept, total: fixes.length };
}
