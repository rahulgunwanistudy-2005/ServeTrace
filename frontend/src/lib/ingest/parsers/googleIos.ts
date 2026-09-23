/**
 * Google Timeline, iOS export: a top-level array using `geo:` strings. Bible §13.
 *
 * The same day rendered on iOS carries less than it does on Android: a journey is one
 * `activity` with a start point and an end point, where Android lists every sampled point
 * along it. Visits are the same information in both, which is why the parity test between
 * the two shapes is a test about visits.
 */

import type { LocationFix } from '../types';
import {
	asArray,
	asObject,
	asString,
	dig,
	EMPTY_ITEMS,
	readInstant,
	readPoint,
	type ParsedItems
} from './shared';

export const SOURCE = 'timeline_ios';

/** One element of the top-level array. */
export function iosItemToFixes(item: unknown): ParsedItems {
	const entry = asObject(item);
	if (!entry) return EMPTY_ITEMS;

	const start = readInstant(entry['startTime']);
	const end = readInstant(entry['endTime']);

	const visit = asObject(entry['visit']);
	if (visit) {
		const candidate = asObject(visit['topCandidate']);
		const point = readPoint(candidate?.['placeLocation']);
		if (!point || !start) return { fixes: [], skipped: 1 };
		const semanticType = asString(candidate?.['semanticType']);
		return {
			fixes: [
				{
					t: start,
					t_end: end ?? start,
					loc: point,
					kind: 'visit',
					source: SOURCE,
					label: semanticType ? `Timeline visit: ${semanticType}` : null
				} satisfies LocationFix
			],
			skipped: 0
		};
	}

	const activity = asObject(entry['activity']);
	if (activity) {
		const from = readPoint(activity['start']);
		const to = readPoint(activity['end']);
		const fixes: LocationFix[] = [];
		if (from && start) {
			fixes.push({ t: start, loc: from, kind: 'path', source: SOURCE, label: null });
		}
		if (to && end) {
			fixes.push({ t: end, loc: to, kind: 'path', source: SOURCE, label: null });
		}
		return { fixes, skipped: fixes.length === 0 ? 1 : 0 };
	}

	// Newer iOS exports sometimes carry a sampled path as well. Free to read if it is there.
	const path = asArray(entry['timelinePath']);
	if (path) {
		const fixes: LocationFix[] = [];
		let skipped = 0;
		for (const step of path) {
			const point = readPoint(dig(step, 'point'));
			const at = readInstant(dig(step, 'time'));
			if (!point || !at) {
				skipped += 1;
				continue;
			}
			fixes.push({ t: at, loc: point, kind: 'path', source: SOURCE, label: null });
		}
		return { fixes, skipped };
	}

	return EMPTY_ITEMS;
}

/** The whole document at once. The worker streams instead; tests use this. */
export function parseGoogleIos(json: unknown): ParsedItems {
	const items = asArray(json);
	if (!items) return EMPTY_ITEMS;

	const fixes: LocationFix[] = [];
	let skipped = 0;
	for (const item of items) {
		const parsed = iosItemToFixes(item);
		fixes.push(...parsed.fixes);
		skipped += parsed.skipped;
	}
	return { fixes, skipped };
}
