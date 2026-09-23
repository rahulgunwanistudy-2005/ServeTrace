/**
 * Turning addresses into points, which is the one part of ingest that needs the network.
 *
 * The geocoder is an argument, never an import. That is what keeps every parser in this
 * directory pure and every test of them offline: nothing under `ingest/` can reach the
 * network on its own, and the one place that can is this file, which is handed the ability
 * by its caller.
 *
 * Each distinct address is looked up once, however many rows mention it — a month of
 * groceries from the same shop is one request — and lookups run a few at a time so a long
 * statement does not arrive as a burst the server has to refuse (bible §16).
 */

import { ingestWarnings } from '$copy/en';

import type { LatLng, LocationFix, PendingFix } from './types';

export type Geocoder = (address: string) => Promise<LatLng | null>;

export type ResolveResult = {
	fixes: LocationFix[];
	/** Addresses nothing could be found for. Named back to the user, not swallowed. */
	unresolved: string[];
	warnings: string[];
};

const CONCURRENCY = 4;

export async function resolvePendingFixes(
	pending: PendingFix[],
	geocode: Geocoder,
	concurrency: number = CONCURRENCY
): Promise<ResolveResult> {
	const addresses = [...new Set(pending.map((p) => p.address))];
	const found = new Map<string, LatLng | null>();

	let next = 0;
	const workers = Array.from({ length: Math.min(concurrency, addresses.length) }, async () => {
		for (;;) {
			const index = next;
			next += 1;
			const address = addresses[index];
			if (address === undefined) return;
			try {
				found.set(address, await geocode(address));
			} catch {
				// One address that will not resolve must not cost the user the other fifty.
				// It is reported below by being absent.
				found.set(address, null);
			}
		}
	});
	await Promise.all(workers);

	const fixes: LocationFix[] = [];
	const unresolved: string[] = [];
	for (const item of pending) {
		const point = found.get(item.address) ?? null;
		if (!point) {
			if (!unresolved.includes(item.address)) unresolved.push(item.address);
			continue;
		}
		const { address: _address, ...rest } = item;
		fixes.push({ ...rest, loc: point });
	}

	const warnings: string[] = [];
	if (unresolved.length > 0) warnings.push(ingestWarnings.addressesNotFound(unresolved.length));
	return { fixes, unresolved, warnings };
}
