/**
 * Google Timeline, Android export: `{ "semanticSegments": [...], "rawSignals": [...] }`.
 * Bible §13.
 *
 * Three kinds of record matter:
 *   - `visit`   — a stay, with a start and an end. The strongest evidence there is, because
 *                 it asserts a stretch of time rather than an instant.
 *   - `timelinePath` — the sampled points of a journey.
 *   - `activity`     — the same journey summarised as a start and an end point, which is
 *                 what some versions write instead of the path.
 * `rawSignals[].position` repeats the path points and is the only place accuracy appears,
 * so it is read and then merged (see `dedupe.ts`) rather than either ignored or doubled.
 */

import type { LocationFix } from '../types';
import {
	asArray,
	asNumber,
	asObject,
	asString,
	dig,
	EMPTY_ITEMS,
	readInstant,
	readPoint,
	type ParsedItems
} from './shared';

export const SOURCE = 'timeline_android';

/** One element of `semanticSegments`. */
export function androidSegmentToFixes(item: unknown): ParsedItems {
	const segment = asObject(item);
	if (!segment) return EMPTY_ITEMS;

	const start = readInstant(segment['startTime']);
	const end = readInstant(segment['endTime']);

	const visit = asObject(segment['visit']);
	if (visit) return visitFix(visit, start, end);

	const path = asArray(segment['timelinePath']);
	if (path) return pathFixes(path, start);

	const activity = asObject(segment['activity']);
	if (activity) return activityFixes(activity, start, end);

	// A segment that is neither a stay nor a journey carries no location: not a failure,
	// just nothing to take from it.
	return EMPTY_ITEMS;
}

function visitFix(visit: Record<string, unknown>, start: string | null, end: string | null) {
	const candidate = asObject(visit['topCandidate']);
	const point = readPoint(dig(candidate, 'placeLocation'));
	if (!point || !start) return { fixes: [], skipped: 1 };

	const semanticType = asString(dig(candidate, 'semanticType'));
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

function pathFixes(path: unknown[], segmentStart: string | null): ParsedItems {
	const fixes: LocationFix[] = [];
	let skipped = 0;

	for (const entry of path) {
		const row = asObject(entry);
		const point = readPoint(row?.['point'] ?? row?.['latLng']);
		const at = readInstant(row?.['time']) ?? offsetTime(segmentStart, row?.['durationMinutesOffsetFromStartTime']);
		if (!point || !at) {
			skipped += 1;
			continue;
		}
		fixes.push({ t: at, loc: point, kind: 'path', source: SOURCE, label: null });
	}
	return { fixes, skipped };
}

/**
 * Some exports timestamp a path point as minutes from the segment's start rather than as
 * an instant. Both are the same claim about when; only one is readable on its own.
 */
function offsetTime(segmentStart: string | null, offset: unknown): string | null {
	if (!segmentStart) return null;
	const minutes = asNumber(offset);
	if (minutes === null) return null;
	return new Date(Date.parse(segmentStart) + minutes * 60_000).toISOString();
}

function activityFixes(
	activity: Record<string, unknown>,
	start: string | null,
	end: string | null
): ParsedItems {
	const from = readPoint(activity['start']);
	const to = readPoint(activity['end']);
	const fixes: LocationFix[] = [];

	if (from && start) fixes.push({ t: start, loc: from, kind: 'path', source: SOURCE, label: null });
	if (to && end) fixes.push({ t: end, loc: to, kind: 'path', source: SOURCE, label: null });

	return { fixes, skipped: fixes.length === 0 ? 1 : 0 };
}

/** One element of `rawSignals`. The only place an accuracy figure appears. */
export function androidRawSignalToFixes(item: unknown): ParsedItems {
	const position = asObject(dig(item, 'position'));
	if (!position) return EMPTY_ITEMS;

	const point = readPoint(position['LatLng'] ?? position['latLng']);
	const at = readInstant(position['timestamp']);
	if (!point || !at) return { fixes: [], skipped: 1 };

	return {
		fixes: [
			{
				t: at,
				loc: point,
				accuracy_m: asNumber(position['accuracyMeters']),
				kind: 'path',
				source: SOURCE,
				label: null
			}
		],
		skipped: 0
	};
}

/** The whole document at once. The worker streams instead; tests use this. */
export function parseGoogleAndroid(json: unknown): ParsedItems {
	const root = asObject(json);
	if (!root) return EMPTY_ITEMS;

	const fixes: LocationFix[] = [];
	let skipped = 0;

	for (const item of asArray(root['semanticSegments']) ?? []) {
		const parsed = androidSegmentToFixes(item);
		fixes.push(...parsed.fixes);
		skipped += parsed.skipped;
	}
	for (const item of asArray(root['rawSignals']) ?? []) {
		const parsed = androidRawSignalToFixes(item);
		fixes.push(...parsed.fixes);
		skipped += parsed.skipped;
	}
	return { fixes, skipped };
}
