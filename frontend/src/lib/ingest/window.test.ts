import { describe, expect, it } from 'vitest';
import { windowFixes } from './window';
import type { LocationFix } from './types';

const CLAIM = '2025-06-12T19:42:00-04:00';

function fix(t: string, t_end?: string): LocationFix {
	return { t, t_end, loc: { lat: 40.75, lng: -73.98 }, kind: t_end ? 'visit' : 'path', source: 'test' };
}

describe('windowFixes', () => {
	it('keeps a fix inside the window', () => {
		const result = windowFixes([fix('2025-06-12T18:00:00-04:00')], [CLAIM]);
		expect(result.kept).toHaveLength(1);
		expect(result.total).toBe(1);
	});

	it('drops a fix outside the window', () => {
		expect(windowFixes([fix('2025-06-12T09:00:00-04:00')], [CLAIM]).kept).toHaveLength(0);
	});

	it('reports the total so the user is told how much is held back', () => {
		const fixes = [fix('2025-06-12T19:40:00-04:00'), fix('2025-06-10T09:00:00-04:00')];
		const result = windowFixes(fixes, [CLAIM]);
		expect(result.kept).toHaveLength(1);
		expect(result.total).toBe(2);
	});

	it('keeps a long visit that spans the claim even though it starts far outside', () => {
		// The whole point of an eight-hour work visit is that it covers the claimed time.
		// Filtering on start time alone would throw away the strongest evidence there is.
		const visit = fix('2025-06-12T14:00:00-04:00', '2025-06-12T22:00:00-04:00');
		expect(windowFixes([visit], [CLAIM]).kept).toHaveLength(1);
	});

	it('drops a visit that ends well before the window opens', () => {
		const visit = fix('2025-06-11T08:00:00-04:00', '2025-06-11T16:00:00-04:00');
		expect(windowFixes([visit], [CLAIM]).kept).toHaveLength(0);
	});

	it('keeps a fix inside the window of any one claim', () => {
		const claims = [CLAIM, '2025-06-05T10:00:00-04:00'];
		const result = windowFixes([fix('2025-06-05T11:00:00-04:00')], claims);
		expect(result.kept).toHaveLength(1);
	});

	it('includes the exact edge of the window', () => {
		const edge = fix('2025-06-12T16:42:00-04:00');
		expect(windowFixes([edge], [CLAIM]).kept).toHaveLength(1);
	});

	it('returns nothing when there are no claims', () => {
		expect(windowFixes([fix(CLAIM)], []).kept).toHaveLength(0);
	});

	it('handles an empty fix list', () => {
		expect(windowFixes([], [CLAIM])).toEqual({ kept: [], total: 0, dropped: 0 });
	});

	it('compares instants, not wall-clock strings, across offsets', () => {
		// Same instant, written in UTC. Treating the offset as decoration would move this
		// fix four hours and silently drop it.
		const sameInstant = fix('2025-06-12T23:42:00Z');
		expect(windowFixes([sameInstant], [CLAIM]).kept).toHaveLength(1);
	});

	it('respects a narrower window when one is given', () => {
		const fixes = [fix('2025-06-12T17:30:00-04:00')];
		expect(windowFixes(fixes, [CLAIM], 1).kept).toHaveLength(0);
		expect(windowFixes(fixes, [CLAIM], 3).kept).toHaveLength(1);
	});
});

describe('windowFixes dedupes and caps', () => {
	it('collapses duplicates that both fall in the window', () => {
		const duplicate = fix('2025-06-12T19:40:00-04:00');
		const result = windowFixes([duplicate, { ...duplicate }], [CLAIM]);
		expect(result.kept).toHaveLength(1);
		// The total is what the file held, not what survived: the user is told both.
		expect(result.total).toBe(2);
	});

	it('keeps everything when the list is under the cap', () => {
		const fixes = Array.from({ length: 10 }, (_, i) =>
			fix(new Date(Date.parse(CLAIM) + i * 60_000).toISOString())
		);
		expect(windowFixes(fixes, [CLAIM]).kept).toHaveLength(10);
		expect(windowFixes(fixes, [CLAIM]).dropped).toBe(0);
	});

	it('keeps the fixes nearest the claim when there are more than the cap', () => {
		// Every minute for three hours either side: far more than a small cap allows.
		const fixes = Array.from({ length: 360 }, (_, i) =>
			fix(new Date(Date.parse(CLAIM) + (i - 180) * 60_000).toISOString())
		);

		const result = windowFixes(fixes, [CLAIM], 3, 11);

		expect(result.kept).toHaveLength(11);
		expect(result.dropped).toBe(349);
		const offsets = result.kept.map((f) => (Date.parse(f.t) - Date.parse(CLAIM)) / 60_000);
		expect(Math.max(...offsets.map(Math.abs))).toBeLessThanOrEqual(5);
	});

	it('never drops an interval that covers the claim to make room', () => {
		// The visit spanning the claimed time is the strongest evidence in the file. If the
		// cap could evict it, the cap would decide the case.
		const covering = fix('2025-06-12T14:00:00-04:00', '2025-06-12T22:00:00-04:00');
		const noise = Array.from({ length: 50 }, (_, i) =>
			fix(new Date(Date.parse(CLAIM) + (i + 1) * 60_000).toISOString())
		);

		const result = windowFixes([...noise, covering], [CLAIM], 3, 5);

		expect(result.kept).toContainEqual(covering);
	});

	it('ignores a fix whose timestamp cannot be read at all', () => {
		expect(windowFixes([fix('the evening of the twelfth')], [CLAIM]).kept).toEqual([]);
	});
});
