/**
 * The one place ingest is allowed to touch the network, and the only thing it sends is an
 * address.
 *
 * `resolve.ts` takes a geocoder as an argument so that everything under `ingest/` stays
 * pure and offline by construction. This is the implementation the app passes in: a thin
 * adapter over `/api/geocode`, which itself forwards nothing but the address string
 * (bible §13). The merchant, the amount and the rest of the statement stay in the browser.
 */

import { api } from '$lib/api/client';

import type { Geocoder } from './resolve';

/**
 * Below this the geocoder is guessing at the street, and a wrong pin is worse than none.
 * Mirrors `MIN_CONFIDENCE` in `backend/app/geo/geocode.py`.
 */
export const MIN_CONFIDENCE = 0.5;

export const apiGeocoder: Geocoder = async (address) => {
	const { result } = await api.geocode(address);
	if (!result || result.confidence < MIN_CONFIDENCE) return null;
	return { lat: result.location.lat, lng: result.location.lng };
};
