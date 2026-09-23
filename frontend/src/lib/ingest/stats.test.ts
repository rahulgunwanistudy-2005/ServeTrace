import { describe, expect, it } from 'vitest';

import { StatsAccumulator, statsFor } from './stats';
import type { LocationFix } from './types';

function fix(t: string, t_end?: string, lat = 40.75): LocationFix {
	return {
		t,
		t_end,
		loc: { lat, lng: -73.98 },
		kind: t_end ? 'visit' : 'path',
		source: 'timeline_android'
	};
}

describe('statsFor', () => {
	it('reports the first and last instant in the file', () => {
		const stats = statsFor([fix('2025-06-12T19:00:00-04:00'), fix('2025-06-12T08:00:00-04:00')]);
		expect(stats.firstAt).toBe('2025-06-12T12:00:00.000Z');
		expect(stats.lastAt).toBe('2025-06-12T23:00:00.000Z');
	});

	it('takes the end of a visit as the last instant', () => {
		const stats = statsFor([fix('2025-06-12T09:00:00-04:00', '2025-06-12T21:00:00-04:00')]);
		expect(stats.lastAt).toBe('2025-06-13T01:00:00.000Z');
	});

	it('lists the New York days covered, not the UTC ones', () => {
		// 8pm on the 12th in New York is the 13th in UTC. Answering in UTC would tell someone
		// their export does not cover the evening the affidavit is about.
		expect(statsFor([fix('2025-06-12T20:00:00-04:00')]).daysCovered).toEqual(['2025-06-12']);
	});

	it('counts a visit that crosses midnight against both days', () => {
		const overnight = fix('2025-06-12T22:00:00-04:00', '2025-06-13T07:00:00-04:00');
		expect(statsFor([overnight]).daysCovered).toEqual(['2025-06-12', '2025-06-13']);
	});

	it('names the claimed days the export does not cover', () => {
		const stats = statsFor([fix('2025-06-12T20:00:00-04:00')], ['2025-06-14T19:42:00-04:00']);
		expect(stats.claimedDaysMissing).toEqual(['2025-06-14']);
	});

	it('says nothing is missing when the day is there', () => {
		const stats = statsFor([fix('2025-06-12T20:00:00-04:00')], ['2025-06-12T19:42:00-04:00']);
		expect(stats.claimedDaysMissing).toEqual([]);
	});

	it('counts the same point recorded twice as one point', () => {
		// The Android export lists every journey point in the path and again as a raw signal.
		expect(statsFor([fix('2025-06-12T08:00:00-04:00'), fix('2025-06-12T08:00:00-04:00')]).total).toBe(1);
	});

	it('counts two different points at the same instant separately', () => {
		const stats = statsFor([
			fix('2025-06-12T08:00:00-04:00', undefined, 40.75),
			fix('2025-06-12T08:00:00-04:00', undefined, 40.85)
		]);
		expect(stats.total).toBe(2);
	});

	it('handles a file with nothing in it', () => {
		expect(statsFor([])).toMatchObject({ total: 0, firstAt: null, lastAt: null, daysCovered: [] });
	});
});

describe('StatsAccumulator', () => {
	it('counts entries it could not read separately from the ones it could', () => {
		const stats = new StatsAccumulator();
		stats.add(fix('2025-06-12T08:00:00-04:00'));
		stats.addSkipped(3);

		expect(stats.finish([], 1, 0)).toMatchObject({ total: 1, skipped: 3, kept: 1 });
	});

	it('counts a fix with an unreadable time as skipped rather than as a point', () => {
		const stats = new StatsAccumulator();
		stats.add(fix('some time on Thursday'));
		expect(stats.finish([], 0, 0)).toMatchObject({ total: 0, skipped: 1 });
	});

	it('reports an exact count as exact', () => {
		const stats = new StatsAccumulator();
		stats.add(fix('2025-06-12T08:00:00-04:00'));
		expect(stats.finish([], 1, 0).totalIsApproximate).toBe(false);
	});
});
