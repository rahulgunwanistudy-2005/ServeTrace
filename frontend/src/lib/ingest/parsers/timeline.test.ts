import { describe, expect, it } from 'vitest';

import { DEMO_CASES, demoJson, expectedFixes, groundTruth } from '../demoFixtures';
import { dedupeFixes } from '../dedupe';
import type { LocationFix } from '../types';
import { androidRawSignalToFixes, androidSegmentToFixes, parseGoogleAndroid } from './googleAndroid';
import { iosItemToFixes, parseGoogleIos } from './googleIos';

const METRES_PER_DEGREE = 111_320;

function metresApart(a: LocationFix, b: LocationFix): number {
	const dLat = (a.loc.lat - b.loc.lat) * METRES_PER_DEGREE;
	const dLng =
		(a.loc.lng - b.loc.lng) * METRES_PER_DEGREE * Math.cos((a.loc.lat * Math.PI) / 180);
	return Math.hypot(dLat, dLng);
}

function visits(fixes: LocationFix[]): LocationFix[] {
	return fixes.filter((f) => f.kind === 'visit');
}

describe.each(DEMO_CASES)('the Android export of %s', (name) => {
	const parsed = parseGoogleAndroid(demoJson(name, 'timeline_android.json'));
	const deduped = dedupeFixes(parsed.fixes);
	const expected = expectedFixes(name);

	it('recovers exactly the fixes the generator put there', () => {
		// `fixes.json` is the generator's own record of where it placed the person. It was
		// written before any of this code existed, so agreeing with it is evidence and not
		// a restatement of the parser.
		expect(deduped).toHaveLength(expected.length);
		expect(deduped.map((f) => f.kind)).toEqual(expected.map((f) => f.kind));
	});

	it('puts every fix at the same instant and the same point as the generator', () => {
		for (const [i, fix] of deduped.entries()) {
			const want = expected[i] as LocationFix;
			expect(Date.parse(fix.t), `fix ${i} time`).toBe(Date.parse(want.t));
			expect(metresApart(fix, want), `fix ${i} position`).toBeLessThan(0.1);
		}
	});

	it('keeps the end time of every visit', () => {
		for (const visit of visits(deduped)) {
			expect(visit.t_end).toBeTruthy();
			expect(Date.parse(visit.t_end as string)).toBeGreaterThan(Date.parse(visit.t));
		}
	});

	it('takes the accuracy from the raw signals rather than losing it', () => {
		const withAccuracy = deduped.filter((f) => f.kind === 'path' && f.accuracy_m);
		expect(withAccuracy.length).toBe(deduped.filter((f) => f.kind === 'path').length);
	});

	it('skips nothing in a well-formed export', () => {
		expect(parsed.skipped).toBe(0);
	});

	it('covers the days the case says it covers', () => {
		const days = new Set(
			deduped.map((f) => new Date(f.t).toLocaleDateString('en-CA', { timeZone: 'America/New_York' }))
		);
		for (const day of groundTruth(name).dates_covered) expect(days).toContain(day);
	});
});

describe.each(DEMO_CASES)('the iOS export of %s', (name) => {
	const parsed = parseGoogleIos(demoJson(name, 'timeline_ios.json'));

	it('reads every visit', () => {
		const androidVisits = visits(parseGoogleAndroid(demoJson(name, 'timeline_android.json')).fixes);
		expect(visits(parsed.fixes)).toHaveLength(androidVisits.length);
	});

	it('reads the ends of each journey', () => {
		expect(parsed.fixes.filter((f) => f.kind === 'path').length).toBeGreaterThan(0);
	});

	it('skips nothing in a well-formed export', () => {
		expect(parsed.skipped).toBe(0);
	});

	it('marks its source, so a packet can say where a point came from', () => {
		expect(new Set(parsed.fixes.map((f) => f.source))).toEqual(new Set(['timeline_ios']));
	});
});

describe.each(DEMO_CASES)('Android and iOS renderings of %s agree', (name) => {
	const android = visits(parseGoogleAndroid(demoJson(name, 'timeline_android.json')).fixes);
	const ios = visits(parseGoogleIos(demoJson(name, 'timeline_ios.json')).fixes);

	it('on every visit, within a metre and a second', () => {
		// The same synthetic history written two ways. Visits are the part both shapes carry
		// in full: a journey is every sampled point on Android and two endpoints on iOS, so
		// there is nothing to compare there.
		expect(ios).toHaveLength(android.length);
		for (const [i, fix] of android.entries()) {
			const other = ios[i] as LocationFix;
			expect(metresApart(fix, other), `visit ${i}`).toBeLessThan(1);
			expect(Math.abs(Date.parse(fix.t) - Date.parse(other.t))).toBeLessThan(1000);
			expect(
				Math.abs(Date.parse(fix.t_end as string) - Date.parse(other.t_end as string))
			).toBeLessThan(1000);
		}
	});

	it('on the label the visit carries', () => {
		expect(ios.map((f) => f.label)).toEqual(android.map((f) => f.label));
	});
});

describe('Android records that are not the happy path', () => {
	it('reads a path point timed as minutes from the segment start', () => {
		const parsed = androidSegmentToFixes({
			startTime: '2025-06-12T08:00:00.000-04:00',
			endTime: '2025-06-12T08:30:00.000-04:00',
			timelinePath: [{ point: '40.7580992°, -73.9855564°', durationMinutesOffsetFromStartTime: 10 }]
		});
		expect(parsed.fixes[0]?.t).toBe('2025-06-12T12:10:00.000Z');
	});

	it('reads an activity segment as its two endpoints', () => {
		const parsed = androidSegmentToFixes({
			startTime: '2025-06-12T08:00:00.000-04:00',
			endTime: '2025-06-12T08:30:00.000-04:00',
			activity: { start: { latLng: '40.70°, -73.90°' }, end: { latLng: '40.75°, -73.98°' } }
		});
		expect(parsed.fixes.map((f) => f.kind)).toEqual(['path', 'path']);
	});

	it('skips a visit with an unreadable coordinate instead of dropping the file', () => {
		const parsed = androidSegmentToFixes({
			startTime: '2025-06-12T08:00:00.000-04:00',
			endTime: '2025-06-12T09:00:00.000-04:00',
			visit: { topCandidate: { placeLocation: { latLng: 'somewhere in the Bronx' } } }
		});
		expect(parsed).toEqual({ fixes: [], skipped: 1 });
	});

	it('skips a visit with no time', () => {
		const parsed = androidSegmentToFixes({
			visit: { topCandidate: { placeLocation: { latLng: '40.75°, -73.98°' } } }
		});
		expect(parsed.skipped).toBe(1);
	});

	it('refuses a timestamp with no offset rather than guessing the zone', () => {
		const parsed = androidSegmentToFixes({
			startTime: '2025-06-12T08:00:00',
			endTime: '2025-06-12T09:00:00',
			visit: { topCandidate: { placeLocation: { latLng: '40.75°, -73.98°' } } }
		});
		expect(parsed.skipped).toBe(1);
	});

	it('reads a raw signal that writes its point as named numbers', () => {
		const parsed = androidRawSignalToFixes({
			position: {
				LatLng: { latitude: 40.75, longitude: -73.98 },
				timestamp: '2025-06-12T08:00:00.000-04:00',
				accuracyMeters: 22
			}
		});
		expect(parsed.fixes[0]).toMatchObject({ loc: { lat: 40.75, lng: -73.98 }, accuracy_m: 22 });
	});

	it('ignores a segment that carries no location at all', () => {
		expect(androidSegmentToFixes({ startTime: '2025-06-12T08:00:00.000-04:00' })).toEqual({
			fixes: [],
			skipped: 0
		});
	});

	it.each([null, undefined, 42, 'text', []])('ignores %s where a segment should be', (value) => {
		expect(androidSegmentToFixes(value)).toEqual({ fixes: [], skipped: 0 });
	});

	it('returns nothing for a document of the wrong shape', () => {
		expect(parseGoogleAndroid([1, 2, 3]).fixes).toEqual([]);
	});
});

describe('iOS records that are not the happy path', () => {
	it('reads a visit written as a geo: string', () => {
		const parsed = iosItemToFixes({
			startTime: '2025-06-12T08:00:00.000-04:00',
			endTime: '2025-06-12T16:00:00.000-04:00',
			visit: { topCandidate: { placeLocation: 'geo:40.7580992,-73.9855564', semanticType: 'WORK' } }
		});
		expect(parsed.fixes[0]).toMatchObject({
			kind: 'visit',
			label: 'Timeline visit: WORK',
			loc: { lat: 40.7580992, lng: -73.9855564 }
		});
	});

	it('keeps the end of an activity even when its start is unreadable', () => {
		const parsed = iosItemToFixes({
			startTime: '2025-06-12T08:00:00.000-04:00',
			endTime: '2025-06-12T08:30:00.000-04:00',
			activity: { start: 'geo:not,a,point', end: 'geo:40.75,-73.98' }
		});
		expect(parsed.fixes).toHaveLength(1);
		expect(parsed.fixes[0]?.t).toBe('2025-06-12T08:30:00.000-04:00');
	});

	it('counts an activity with no readable point as skipped', () => {
		const parsed = iosItemToFixes({
			startTime: '2025-06-12T08:00:00.000-04:00',
			endTime: '2025-06-12T08:30:00.000-04:00',
			activity: { start: 'nonsense', end: 'nonsense' }
		});
		expect(parsed).toEqual({ fixes: [], skipped: 1 });
	});

	it('returns nothing for a document of the wrong shape', () => {
		expect(parseGoogleIos({ semanticSegments: [] }).fixes).toEqual([]);
	});
});

describe('a day the clocks change', () => {
	// 2 November 2025: 01:30 happens twice in New York. The offsets in the file are what
	// disambiguate it, which is exactly why a timestamp without one is refused.
	const fold = [
		{
			startTime: '2025-11-02T01:30:00.000-04:00',
			endTime: '2025-11-02T01:45:00.000-04:00',
			visit: { topCandidate: { placeLocation: 'geo:40.75,-73.98', semanticType: 'HOME' } }
		},
		{
			startTime: '2025-11-02T01:30:00.000-05:00',
			endTime: '2025-11-02T01:45:00.000-05:00',
			visit: { topCandidate: { placeLocation: 'geo:40.85,-73.86', semanticType: 'HOME' } }
		}
	];

	it('keeps the two readings of the same wall clock an hour apart', () => {
		const parsed = parseGoogleIos(fold);
		const [first, second] = parsed.fixes as [LocationFix, LocationFix];
		expect(Date.parse(second.t) - Date.parse(first.t)).toBe(3_600_000);
	});

	it('does not collapse them into one fix', () => {
		expect(dedupeFixes(parseGoogleIos(fold).fixes)).toHaveLength(2);
	});
});
