/**
 * Collapsing the same point recorded twice.
 *
 * Android exports every journey point twice: once in `timelinePath` and again in
 * `rawSignals`. Only the raw signal carries an accuracy figure. Dropping either copy
 * outright is wrong in one direction or the other — keep the path point and the accuracy
 * is lost, keep the raw signal and the ordering of the path is disturbed — so duplicates
 * are merged rather than picked between.
 *
 * Where both copies state an accuracy and they differ, the *larger* one wins. The engine
 * widens its match radius by the accuracy (bible §11.1), so the larger figure is the one
 * that makes a contradiction harder to reach, and ServeTrace resolves this kind of tie
 * against itself every time.
 */

import type { LocationFix } from './types';

const COORD_DP = 7;

/** What makes two records the same point. Shared with `stats.ts`, so the count the user
 * is shown and the list that is sent can never disagree about it. */
export function fixKey(fix: LocationFix): string {
	return [
		fix.kind,
		fix.t,
		fix.t_end ?? '',
		fix.loc.lat.toFixed(COORD_DP),
		fix.loc.lng.toFixed(COORD_DP)
	].join('|');
}

function merge(kept: LocationFix, duplicate: LocationFix): LocationFix {
	const accuracies = [kept.accuracy_m, duplicate.accuracy_m].filter(
		(a): a is number => typeof a === 'number'
	);
	return {
		...kept,
		accuracy_m: accuracies.length > 0 ? Math.max(...accuracies) : null,
		label: kept.label ?? duplicate.label ?? null
	};
}

/** Order that does not depend on the order the file happened to list things in. */
export function sortFixes(fixes: LocationFix[]): LocationFix[] {
	return [...fixes].sort(
		(a, b) =>
			Date.parse(a.t) - Date.parse(b.t) ||
			a.kind.localeCompare(b.kind) ||
			a.loc.lat - b.loc.lat ||
			a.loc.lng - b.loc.lng
	);
}

export function dedupeFixes(fixes: LocationFix[]): LocationFix[] {
	const byKey = new Map<string, LocationFix>();
	for (const fix of fixes) {
		const k = fixKey(fix);
		const existing = byKey.get(k);
		byKey.set(k, existing ? merge(existing, fix) : fix);
	}
	return sortFixes([...byKey.values()]);
}
