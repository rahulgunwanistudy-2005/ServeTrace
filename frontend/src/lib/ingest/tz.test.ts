import { describe, expect, it } from 'vitest';
import {
	formatNY,
	nyDayKey,
	nyDaysSpanned,
	nyLocalToInstant,
	parseLatLng,
	toEpochMs
} from './tz';

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

describe('toEpochMs', () => {
	it('reads an offset timestamp as the instant it names', () => {
		expect(toEpochMs('2025-06-12T19:42:00.000-04:00')).toBe(Date.parse('2025-06-12T23:42:00Z'));
	});

	it('accepts a Z timestamp', () => {
		expect(toEpochMs('2025-06-12T23:42:00Z')).toBe(Date.parse('2025-06-12T23:42:00Z'));
	});

	it('refuses a timestamp with no offset rather than guessing the reader machine', () => {
		// Read as local time, this would move a Los Angeles user's whole day by three hours.
		expect(toEpochMs('2025-06-12T19:42:00')).toBeNull();
	});

	it('refuses nonsense', () => {
		expect(toEpochMs('last Tuesday')).toBeNull();
	});
});

describe('nyDayKey', () => {
	it('answers in New York, not in UTC', () => {
		// 8pm on the 12th in New York is already the 13th in UTC.
		expect(nyDayKey('2025-06-13T00:42:00Z')).toBe('2025-06-12');
	});

	it('handles a winter offset', () => {
		expect(nyDayKey('2025-01-15T04:30:00Z')).toBe('2025-01-14');
	});
});

describe('nyDaysSpanned', () => {
	it('returns one day for an interval inside a day', () => {
		const start = Date.parse('2025-06-12T09:00:00-04:00');
		const end = Date.parse('2025-06-12T17:00:00-04:00');
		expect(nyDaysSpanned(start, end)).toEqual(['2025-06-12']);
	});

	it('covers both days when a visit crosses midnight', () => {
		const start = Date.parse('2025-06-12T20:00:00-04:00');
		const end = Date.parse('2025-06-13T07:00:00-04:00');
		expect(nyDaysSpanned(start, end)).toEqual(['2025-06-12', '2025-06-13']);
	});

	it('counts every day of a long interval, including the DST fold', () => {
		const start = Date.parse('2025-11-01T12:00:00-04:00');
		const end = Date.parse('2025-11-03T12:00:00-05:00');
		expect(nyDaysSpanned(start, end)).toEqual(['2025-11-01', '2025-11-02', '2025-11-03']);
	});

	it('treats a zero-length interval as its own single day', () => {
		const t = Date.parse('2025-06-12T19:42:00-04:00');
		expect(nyDaysSpanned(t, t)).toEqual(['2025-06-12']);
	});
});

describe('nyLocalToInstant', () => {
	it('applies the summer offset', () => {
		expect(nyLocalToInstant('2025-06-12', '19:42')?.iso).toBe('2025-06-12T23:42:00.000Z');
	});

	it('applies the winter offset', () => {
		expect(nyLocalToInstant('2025-01-15', '08:00')?.iso).toBe('2025-01-15T13:00:00.000Z');
	});

	it('takes the earlier reading of a wall clock that happened twice', () => {
		// 2 November 2025, 01:30 happened at 05:30Z (EDT) and again at 06:30Z (EST).
		const result = nyLocalToInstant('2025-11-02', '01:30');
		expect(result?.iso).toBe('2025-11-02T05:30:00.000Z');
		expect(result?.ambiguous).toBe(true);
	});

	it('reports a wall clock that never happened, and moves it past the gap', () => {
		// 9 March 2025 skips 02:00 to 03:00.
		const result = nyLocalToInstant('2025-03-09', '02:30');
		expect(result?.nonexistent).toBe(true);
		expect(result?.iso).toBe('2025-03-09T07:30:00.000Z');
	});

	it('marks an ordinary time as neither ambiguous nor missing', () => {
		const result = nyLocalToInstant('2025-06-12', '08:00');
		expect(result).toMatchObject({ ambiguous: false, nonexistent: false });
	});

	it('accepts seconds and a single-digit hour', () => {
		expect(nyLocalToInstant('2025-06-12', '9:05:30')?.iso).toBe('2025-06-12T13:05:30.000Z');
	});

	it.each([
		['2025-13-01', '10:00'],
		['2025-02-31', '10:00'],
		['12/06/2025', '10:00'],
		['2025-06-12', '25:00'],
		['2025-06-12', 'noon']
	])('returns null for %s %s', (date, time) => {
		expect(nyLocalToInstant(date, time)).toBeNull();
	});
});
