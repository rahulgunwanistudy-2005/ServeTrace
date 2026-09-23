/**
 * Reading values out of `unknown` without trusting any of it.
 *
 * Every parser in this directory is handed data from a file the user found on their phone.
 * It may be from a Google export written this year or three years ago, hand-edited, or not
 * a location history at all. So nothing here throws on a surprise: a field that is missing
 * or the wrong type reads as null and the caller decides whether that entry is still
 * usable. One unreadable row must never cost the user the other fifty thousand.
 */

import { parseLatLng, toEpochMs } from '../tz';
import type { LatLng, LocationFix } from '../types';

export type ParsedItems = {
	fixes: LocationFix[];
	/** Entries that looked like records but could not be read. Reported, never hidden. */
	skipped: number;
};

export const EMPTY_ITEMS: ParsedItems = { fixes: [], skipped: 0 };

export function asObject(value: unknown): Record<string, unknown> | null {
	return typeof value === 'object' && value !== null && !Array.isArray(value)
		? (value as Record<string, unknown>)
		: null;
}

export function asArray(value: unknown): unknown[] | null {
	return Array.isArray(value) ? value : null;
}

export function asString(value: unknown): string | null {
	return typeof value === 'string' ? value : null;
}

export function asNumber(value: unknown): number | null {
	if (typeof value === 'number' && Number.isFinite(value)) return value;
	if (typeof value === 'string' && value.trim() !== '') {
		const n = Number(value);
		return Number.isFinite(n) ? n : null;
	}
	return null;
}

/** Follow a path of keys, stopping at the first thing that is not an object. */
export function dig(value: unknown, ...path: string[]): unknown {
	let current: unknown = value;
	for (const key of path) {
		const object = asObject(current);
		if (!object) return null;
		current = object[key];
	}
	return current ?? null;
}

/**
 * A point, from any of the shapes the exports use.
 *
 * Android writes `"40.75°, -73.98°"`, iOS writes `"geo:40.75,-73.98"`, and raw signals
 * sometimes write an object with named fields. They all mean the same thing.
 */
export function readPoint(value: unknown): LatLng | null {
	const text = asString(value);
	if (text !== null) return parseLatLng(text);

	const object = asObject(value);
	if (!object) return null;

	const nested = object['latLng'] ?? object['LatLng'] ?? object['placeLocation'];
	if (nested !== undefined && nested !== null) return readPoint(nested);

	const lat = asNumber(object['latitude'] ?? object['lat']);
	const lng = asNumber(object['longitude'] ?? object['lng'] ?? object['lon']);
	if (lat === null || lng === null) return null;
	if (lat < -90 || lat > 90 || lng < -180 || lng > 180) return null;
	return { lat, lng };
}

/** An ISO instant with an offset, normalised. Anything else reads as null (see `tz.ts`). */
export function readInstant(value: unknown): string | null {
	const text = asString(value);
	if (text === null) return null;
	return toEpochMs(text) === null ? null : text;
}
