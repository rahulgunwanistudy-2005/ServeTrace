import { describe, expect, it } from 'vitest';

import { dedupeFixes, sortFixes } from './dedupe';
import type { LocationFix } from './types';

function fix(partial: Partial<LocationFix> = {}): LocationFix {
	return {
		t: '2025-06-12T19:42:00-04:00',
		loc: { lat: 40.75, lng: -73.98 },
		kind: 'path',
		source: 'timeline_android',
		...partial
	};
}

describe('dedupeFixes', () => {
	it('collapses the same point recorded twice', () => {
		expect(dedupeFixes([fix(), fix()])).toHaveLength(1);
	});

	it('keeps the accuracy from whichever copy has one', () => {
		// The Android path point has no accuracy; the raw signal repeating it does.
		const merged = dedupeFixes([fix(), fix({ accuracy_m: 38 })]);
		expect(merged[0]?.accuracy_m).toBe(38);
	});

	it('keeps the larger accuracy when the copies disagree', () => {
		// A larger figure widens the engine's match radius, which makes a contradiction
		// harder to reach. Ties are resolved against our own case, every time.
		expect(dedupeFixes([fix({ accuracy_m: 12 }), fix({ accuracy_m: 55 })])[0]?.accuracy_m).toBe(55);
	});

	it('keeps a label from whichever copy has one', () => {
		const merged = dedupeFixes([fix(), fix({ label: 'Timeline visit: HOME' })]);
		expect(merged[0]?.label).toBe('Timeline visit: HOME');
	});

	it('does not merge two fixes at the same time in different places', () => {
		expect(dedupeFixes([fix(), fix({ loc: { lat: 40.85, lng: -73.86 } })])).toHaveLength(2);
	});

	it('does not merge a visit with a path point at the same moment', () => {
		expect(dedupeFixes([fix(), fix({ kind: 'visit', t_end: '2025-06-12T20:00:00-04:00' })])).toHaveLength(2);
	});

	it('does not merge two visits that start together but end apart', () => {
		const a = fix({ kind: 'visit', t_end: '2025-06-12T20:00:00-04:00' });
		const b = fix({ kind: 'visit', t_end: '2025-06-12T21:00:00-04:00' });
		expect(dedupeFixes([a, b])).toHaveLength(2);
	});

	it('returns them in time order whatever order they arrived in', () => {
		const later = fix({ t: '2025-06-12T20:00:00-04:00' });
		const earlier = fix({ t: '2025-06-12T18:00:00-04:00' });
		expect(dedupeFixes([later, earlier]).map((f) => f.t)).toEqual([earlier.t, later.t]);
	});

	it('handles an empty list', () => {
		expect(dedupeFixes([])).toEqual([]);
	});
});

describe('sortFixes', () => {
	it('does not modify the list it is given', () => {
		const fixes = [fix({ t: '2025-06-12T20:00:00-04:00' }), fix()];
		const before = [...fixes];
		sortFixes(fixes);
		expect(fixes).toEqual(before);
	});

	it('orders equal times by kind, so the order never depends on the file', () => {
		const visit = fix({ kind: 'visit' });
		const path = fix({ kind: 'path' });
		expect(sortFixes([visit, path]).map((f) => f.kind)).toEqual(['path', 'visit']);
	});
});
