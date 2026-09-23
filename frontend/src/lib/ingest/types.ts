/**
 * Browser-side mirrors of the backend contracts in `domain/models.py`.
 *
 * These are hand-written only until `npm run gen:types` has run against a backend that
 * exposes them; from then on the generated `schema.d.ts` is the source of truth.
 */

export type LatLng = { lat: number; lng: number };

export type FixKind = 'visit' | 'path' | 'transaction' | 'manual';

export type LocationFix = {
	t: string;
	t_end?: string | null;
	loc: LatLng;
	accuracy_m?: number | null;
	kind: FixKind;
	source: string;
	label?: string | null;
};

export type ParseResult = {
	fixes: LocationFix[];
	warnings: string[];
};
