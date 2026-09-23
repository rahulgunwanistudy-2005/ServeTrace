import { describe, expect, it, vi } from 'vitest';

import { resolvePendingFixes } from './resolve';
import type { PendingFix } from './types';

const BRONX = { lat: 40.8532963, lng: -73.8675013 };

function pending(address: string, t = '2025-06-12T19:42:00.000Z'): PendingFix {
	return { t, t_end: null, address, accuracy_m: 500, kind: 'transaction', source: 'card_csv' };
}

describe('resolvePendingFixes', () => {
	it('turns an address into a point', async () => {
		const result = await resolvePendingFixes([pending('2100 White Plains Road')], async () => BRONX);
		expect(result.fixes[0]).toMatchObject({ loc: BRONX, kind: 'transaction' });
	});

	it('does not carry the address into the fix that gets sent', async () => {
		const result = await resolvePendingFixes([pending('2100 White Plains Road')], async () => BRONX);
		expect(result.fixes[0]).not.toHaveProperty('address');
	});

	it('looks up each distinct address once, however many rows mention it', async () => {
		// A month of groceries from the same shop is one request, not thirty.
		const geocode = vi.fn(async () => BRONX);
		await resolvePendingFixes(
			[pending('Same shop'), pending('Same shop'), pending('Same shop')],
			geocode
		);
		expect(geocode).toHaveBeenCalledTimes(1);
	});

	it('names the addresses it could not find instead of dropping them silently', async () => {
		const result = await resolvePendingFixes([pending('Somewhere in Philadelphia')], async () => null);

		expect(result.fixes).toEqual([]);
		expect(result.unresolved).toEqual(['Somewhere in Philadelphia']);
		expect(result.warnings[0]).toMatch(/New York City/);
	});

	it('keeps the rows it could place when one address fails', async () => {
		const result = await resolvePendingFixes(
			[pending('Findable'), pending('Not findable')],
			async (address) => (address === 'Findable' ? BRONX : null)
		);
		expect(result.fixes).toHaveLength(1);
		expect(result.unresolved).toEqual(['Not findable']);
	});

	it('survives a lookup that throws', async () => {
		// One address that makes the server unhappy must not cost the user the other fifty.
		const result = await resolvePendingFixes([pending('Boom'), pending('Fine')], async (address) => {
			if (address === 'Boom') throw new Error('502');
			return BRONX;
		});
		expect(result.fixes).toHaveLength(1);
		expect(result.unresolved).toEqual(['Boom']);
	});

	it('runs a few lookups at a time, not all of them at once', async () => {
		let running = 0;
		let peak = 0;
		const geocode = async () => {
			running += 1;
			peak = Math.max(peak, running);
			await new Promise((resolve) => setTimeout(resolve, 1));
			running -= 1;
			return BRONX;
		};

		const many = Array.from({ length: 20 }, (_, i) => pending(`Address ${i}`));
		await resolvePendingFixes(many, geocode, 4);

		expect(peak).toBeLessThanOrEqual(4);
	});

	it('resolves every row, not only the first few', async () => {
		const many = Array.from({ length: 20 }, (_, i) => pending(`Address ${i}`));
		const result = await resolvePendingFixes(many, async () => BRONX, 4);
		expect(result.fixes).toHaveLength(20);
	});

	it('handles being given nothing', async () => {
		const geocode = vi.fn(async () => BRONX);
		const result = await resolvePendingFixes([], geocode);
		expect(result.fixes).toEqual([]);
		expect(geocode).not.toHaveBeenCalled();
	});
});
