import { describe, expect, it } from 'vitest';
import { windowFixes } from './window';
import type { LocationFix } from './types';

const CLAIM = '2025-06-12T19:42:00-04:00';

function fix(t: string, t_end?: string): LocationFix {
	return { t, t_end, loc: { lat: 40.75, lng: -73.98 }, kind: 'path', source: 'test' };
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
		expect(windowFixes([], [CLAIM])).toEqual({ kept: [], total: 0 });
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
