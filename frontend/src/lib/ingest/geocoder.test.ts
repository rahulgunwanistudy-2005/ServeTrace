import { describe, expect, it, vi } from 'vitest';

import { api } from '$lib/api/client';
import { apiGeocoder, MIN_CONFIDENCE } from './geocoder';

const BRONX = { lat: 40.8532963, lng: -73.8675013 };

function answer(confidence: number) {
	return {
		result: { location: BRONX, label: '2100 White Plains Road', confidence, source: 'cache' as const }
	};
}

describe('apiGeocoder', () => {
	it('returns the point for a confident answer', async () => {
		vi.spyOn(api, 'geocode').mockResolvedValue(answer(0.9));
		expect(await apiGeocoder('2100 White Plains Road')).toEqual(BRONX);
	});

	it('sends the address and nothing else', async () => {
		// Bible §13. The whole request is the address: no merchant, no amount, no case.
		const spy = vi.spyOn(api, 'geocode').mockResolvedValue(answer(0.9));
		await apiGeocoder('2100 White Plains Road');
		expect(spy).toHaveBeenCalledWith('2100 White Plains Road');
		expect(spy).toHaveBeenCalledTimes(1);
	});

	it('refuses a low-confidence answer rather than dropping a pin on a guess', async () => {
		vi.spyOn(api, 'geocode').mockResolvedValue(answer(MIN_CONFIDENCE - 0.01));
		expect(await apiGeocoder('somewhere vague')).toBeNull();
	});

	it('returns null when nothing was found', async () => {
		vi.spyOn(api, 'geocode').mockResolvedValue({ result: null });
		expect(await apiGeocoder('Philadelphia')).toBeNull();
	});
});
