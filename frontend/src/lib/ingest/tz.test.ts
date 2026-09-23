import { describe, expect, it } from 'vitest';
import { formatNY, parseLatLng } from './tz';

describe('parseLatLng', () => {
	it('parses the Android degree-string format', () => {
		expect(parseLatLng('40.7580992°, -73.9855564°')).toEqual({
			lat: 40.7580992,
			lng: -73.9855564
		});
	});

	it('parses the iOS geo: format', () => {
		expect(parseLatLng('geo:40.7,-73.9')).toEqual({ lat: 40.7, lng: -73.9 });
	});

	it('tolerates surrounding whitespace', () => {
		expect(parseLatLng('  40.7° , -73.9°  ')).toEqual({ lat: 40.7, lng: -73.9 });
	});

	it.each([
		['', 'empty'],
		['40.7', 'one component'],
		['40.7,-73.9,12', 'three components'],
		['north, west', 'not numbers'],
		['91.0,-73.9', 'latitude out of range'],
		['40.7,-181.0', 'longitude out of range']
	])('returns null for %s (%s)', (raw) => {
		expect(parseLatLng(raw)).toBeNull();
	});

	it('returns null rather than throwing, so one bad row cannot abort an import', () => {
		expect(() => parseLatLng('garbage')).not.toThrow();
	});
});

describe('formatNY', () => {
	it('renders an instant in New York local time whatever offset it arrives in', () => {
		expect(formatNY('2025-06-12T23:42:00Z')).toContain('7:42');
	});

	it('accepts a Date as well as a string', () => {
		expect(formatNY(new Date('2025-06-12T23:42:00Z'))).toContain('7:42');
	});
});
