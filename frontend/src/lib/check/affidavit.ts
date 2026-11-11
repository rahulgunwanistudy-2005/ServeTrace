/**
 * The reviewed fields, as strings, turned into the `Affidavit` the engine takes.
 *
 * Shared by the defendant check (one affidavit) and the advocate batch (hundreds), so the
 * two can never disagree about what a confirmed affidavit is. It does the two things a
 * person typing into a form cannot: read the time as New York wall-clock (never the
 * browser's), and put a point on the map for each address.
 *
 * The geocoder is passed in. That keeps this testable without a network, and lets a batch
 * skip the lookup when the reader already placed an address the person did not change —
 * sixty affidavits should not mean sixty more requests for points we already have.
 */

import { ApiError, type Affidavit, type AffidavitDraft, type LatLng } from '$lib/api/client';
import { upload } from '$copy/en';
import { nyLocalToInstant } from '$lib/ingest/tz';
import type { AttemptValues, Values } from './review';

/** Resolves an address to a point, or null when it cannot be placed. */
export type Geocoder = (address: string) => Promise<LatLng | null>;

type Outcome = Affidavit['attempts'] extends (infer A)[] | undefined
	? A extends { outcome: infer O }
		? O
		: never
	: never;

const same = (a: string | null | undefined, b: string | null | undefined) =>
	(a ?? '').trim().toLowerCase() === (b ?? '').trim().toLowerCase();

/**
 * A point for an address, reusing the reader's when the address is the one it read.
 * Exported for the tests: this is the whole of the "no sixty geocodes" promise.
 */
export async function placeOf(
	address: string,
	read: { address?: string | null; location?: LatLng | null } | null,
	geocode: Geocoder
): Promise<LatLng | null> {
	if (read?.location && same(read.address, address)) return read.location;
	return geocode(address);
}

export async function buildAffidavit(input: {
	values: Values;
	attempts: AttemptValues[];
	draft: AffidavitDraft | null | undefined;
	sourceSha256: string | null | undefined;
	geocode: Geocoder;
}): Promise<Affidavit> {
	const { values, attempts, draft, geocode } = input;
	const v = (key: string): string => values[key] ?? '';

	const local = nyLocalToInstant(v('served_date'), v('served_time'));
	if (!local) throw new ApiError('bad_input', 400, upload.timeNeeded);
	const address = v('served_address').trim();
	const point = await placeOf(
		address,
		{ address: draft?.served_address, location: draft?.served_location },
		geocode
	);
	if (!point) throw new ApiError('bad_input', 400, upload.addressNotFound);

	// Earlier tries matter to the diligence rules (bible §11.3, R-D1/R-D2), so they go
	// through with the same New York wall-clock handling as the service itself. An
	// address we cannot place leaves that try without a point, not out of the case.
	const tries: Affidavit['attempts'] = [];
	for (const [index, attempt] of attempts.entries()) {
		const at = nyLocalToInstant(attempt.date, attempt.time);
		if (!at) throw new ApiError('bad_input', 400, upload.attemptIncomplete);
		const where = attempt.address.trim() || address;
		const read = draft?.attempts?.[index];
		const placed = await placeOf(
			where,
			read ? { address: read.address ?? address, location: read.location } : null,
			geocode
		).catch(() => null);
		tries.push({ at: at.iso, address: where, location: placed, outcome: attempt.outcome as Outcome });
	}

	return {
		index_number: v('index_number') || null,
		court: v('court') || null,
		plaintiff: v('plaintiff') || null,
		defendant_name: v('defendant_name'),
		server_name: v('server_name') || null,
		server_license: v('server_license') || null,
		agency_license: draft?.agency_license ?? null,
		agency_name: v('agency_name') || null,
		method: v('method') as Affidavit['method'],
		served_at: local.iso,
		served_address: address,
		served_location: point,
		recipient_name: v('recipient_name') || null,
		recipient_relationship: v('recipient_relationship') || null,
		recipient_description: draft?.recipient_description ?? null,
		attempts: tries,
		mailing_date: v('mailing_date') || null,
		mailing_address: v('mailing_address') || null,
		proof_filed_date: v('proof_filed_date') || null,
		source_sha256: input.sourceSha256 ?? '0'.repeat(64),
		field_confidence: draft?.field_confidence ?? {},
		evidence: draft?.evidence ?? {},
		user_confirmed: true
	};
}
