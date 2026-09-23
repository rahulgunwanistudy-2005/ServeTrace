/** Time-zone helpers. All display is New York local; all transport is ISO with offset. */

export const TZ = 'America/New_York';

const formatter = new Intl.DateTimeFormat('en-US', {
	timeZone: TZ,
	dateStyle: 'medium',
	timeStyle: 'short'
});

export function formatNY(value: Date | string): string {
	return formatter.format(typeof value === 'string' ? new Date(value) : value);
}

/**
 * Parse a Google Timeline coordinate string.
 *
 * Android writes `"40.7580123°, -73.9855123°"`; iOS writes `"geo:40.7580123,-73.9855123"`.
 * Returns null rather than throwing, because a single malformed row in a 200 MB export
 * must not abort the whole import.
 */
export function parseLatLng(raw: string): { lat: number; lng: number } | null {
	const cleaned = raw.trim().replace(/^geo:/, '').replace(/°/g, '');
	const parts = cleaned.split(',');
	if (parts.length !== 2) return null;
	const lat = Number(parts[0]?.trim());
	const lng = Number(parts[1]?.trim());
	if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
	if (lat < -90 || lat > 90 || lng < -180 || lng > 180) return null;
	return { lat, lng };
}
