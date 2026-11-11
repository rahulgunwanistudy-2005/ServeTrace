import { describe, expect, it } from 'vitest';

import type { LocationFix } from '../types';
import { heifTiff, isHeif, type ByteReader } from './heic';
import {
	collapseBursts,
	photoToFix,
	readPhotoMeta,
	summarise,
	PHOTO_ASSUMED_ZONE_UNCERTAINTY_S,
	type PhotoOutcome
} from './photos';

/**
 * Written by `fixtures/generator/photos.py`, from the values the EXIF was written from.
 *
 * Read with Node's `fs` through a dynamic import. The frontend deliberately has no Node
 * types, and Vite's `?inline` hands vitest a path rather than bytes, so this is the one
 * place a test reaches for the runtime it is already running in (environment: 'node').
 */
const fs = (await import(/* @vite-ignore */ 'node:fs' as string)) as {
	readFileSync(path: URL): Uint8Array;
};
const DIR = new URL('../../../../../fixtures/photos/', import.meta.url);

function readFileSync(name: string): Uint8Array {
	return new Uint8Array(fs.readFileSync(new URL(name, DIR)));
}

const expected = JSON.parse(new TextDecoder().decode(readFileSync('expected.json'))) as Record<
	string,
	| { skip: string }
	| {
			t: string;
			lat: number;
			lng: number;
			accuracy_m: number;
			tz_assumed: boolean;
			time_uncertainty_s: number;
	  }
>;

function reader(bytes: Uint8Array): { read: ByteReader; reads: [number, number][] } {
	const reads: [number, number][] = [];
	return {
		reads,
		read: async (offset, length) => {
			reads.push([offset, length]);
			return bytes.subarray(offset, offset + length);
		}
	};
}

async function outcomeFor(name: string): Promise<PhotoOutcome | null> {
	const bytes = readFileSync(name);
	const meta = await readPhotoMeta(reader(bytes).read, bytes.length);
	return meta ? photoToFix(meta) : null;
}

describe('every fixture photo reads as its answer key says', () => {
	for (const [name, answer] of Object.entries(expected)) {
		it(name, async () => {
			const outcome = await outcomeFor(name);
			if ('skip' in answer) {
				const kind = answer.skip === 'no_location' ? 'no_location' : 'no_time';
				expect(outcome?.kind).toBe(kind);
				return;
			}
			expect(outcome?.kind).toBe('fix');
			const fix = (outcome as { kind: 'fix'; fix: LocationFix }).fix;
			expect(fix.t).toBe(answer.t);
			expect(fix.loc.lat).toBeCloseTo(answer.lat, 5);
			expect(fix.loc.lng).toBeCloseTo(answer.lng, 5);
			expect(fix.accuracy_m).toBeCloseTo(answer.accuracy_m, 3);
			expect(fix.tz_assumed).toBe(answer.tz_assumed);
			expect(fix.time_uncertainty_s).toBe(answer.time_uncertainty_s);
			expect(fix.kind).toBe('photo');
			expect(fix.label).toBe('Photo taken here');
			expect(JSON.stringify(fix)).not.toContain(name.split('.')[0]);
		});
	}
});

describe('HEIC', () => {
	it('is recognised from its bytes, not its name', () => {
		const heic = readFileSync('gps_utc.heic');
		const jpeg = readFileSync('gps_utc.jpg');
		expect(isHeif(heic)).toBe(true);
		expect(isHeif(jpeg)).toBe(false);
	});

	it('reads only the meta box and the Exif extent, never the image data', async () => {
		const bytes = readFileSync('gps_utc.heic');
		const { read, reads } = reader(bytes);
		const tiff = await heifTiff(read, bytes.length);
		expect(tiff).not.toBeNull();
		expect(String.fromCharCode(tiff![0]!, tiff![1]!)).toMatch(/MM|II/);
		const touched = reads.reduce((sum, [, n]) => sum + n, 0);
		expect(touched).toBeLessThan(bytes.length);
	});

	it('gives up quietly on bytes that are not a HEIF file', async () => {
		const junk = new Uint8Array(64).fill(7);
		expect(await heifTiff(reader(junk).read, junk.length)).toBeNull();
	});
});

describe('the time ladder', () => {
	const place = { latitude: 40.78, longitude: -73.95 };

	it('prefers the GPS clock over the camera clock', () => {
		const out = photoToFix({
			...place,
			DateTimeOriginal: '2025:06:12 19:38:00',
			OffsetTimeOriginal: '+05:30',
			GPSDateStamp: '2025:06:12',
			GPSTimeStamp: [23, 38, 0]
		});
		expect(out.kind === 'fix' && out.fix.t).toBe('2025-06-12T23:38:00.000Z');
	});

	it('uses the offset when there is no GPS clock', () => {
		const out = photoToFix({ ...place, DateTimeOriginal: '2025:06:12 19:38:00', OffsetTimeOriginal: '+05:30' });
		expect(out.kind === 'fix' && out.fix.t).toBe('2025-06-12T14:08:00.000Z');
		expect(out.kind === 'fix' && out.fix.tz_assumed).toBe(false);
	});

	it('assumes New York, and says so, when the camera kept no zone', () => {
		const out = photoToFix({ ...place, DateTimeOriginal: '2025:01:12 19:38:00' });
		expect(out.kind === 'fix' && out.fix.t).toBe('2025-01-13T00:38:00.000Z');
		expect(out.kind === 'fix' && out.fix.tz_assumed).toBe(true);
		expect(out.kind === 'fix' && out.fix.time_uncertainty_s).toBe(PHOTO_ASSUMED_ZONE_UNCERTAINTY_S);
	});

	it('never uses anything but the original time', () => {
		expect(photoToFix({ ...place }).kind).toBe('no_time');
		expect(photoToFix({ ...place, DateTimeOriginal: 'yesterday' }).kind).toBe('no_time');
	});

	it('treats an empty GPS block as no location', () => {
		expect(photoToFix({ DateTimeOriginal: '2025:06:12 19:38:00', latitude: 0, longitude: 0 }).kind).toBe(
			'no_location'
		);
	});
});

describe('bursts', () => {
	const at = (seconds: number, dLat = 0): LocationFix => ({
		t: new Date(Date.UTC(2025, 5, 12, 23, 50, seconds)).toISOString(),
		loc: { lat: 40.7836 + dLat, lng: -73.9527 },
		kind: 'photo',
		source: 'photo'
	});

	it('collapse to the first shot when close in time and place', () => {
		expect(collapseBursts([at(0), at(20), at(45)])).toHaveLength(1);
	});

	it('do not swallow a photo taken somewhere else, or a minute later', () => {
		expect(collapseBursts([at(0), at(20, 0.001)])).toHaveLength(2);
		expect(collapseBursts([at(0), at(61)])).toHaveLength(2);
	});

	it('are what the burst fixtures do', async () => {
		const outcomes = await Promise.all(['burst_1.jpg', 'burst_2.jpg', 'burst_3.jpg'].map(outcomeFor));
		const summary = summarise(outcomes);
		expect(summary.withLocation).toBe(3);
		expect(summary.fixes).toHaveLength(1);
	});
});

describe('summary', () => {
	it('counts time-only photos separately so the screen can explain them', async () => {
		const names = ['gps_utc.jpg', 'no_gps.jpg', 'no_time.jpg', 'local_only.jpg'];
		const summary = summarise(await Promise.all(names.map(outcomeFor)));
		expect(summary).toMatchObject({ read: 4, withLocation: 2, timeOnly: 1, skipped: 1, zoneAssumed: 1 });
	});
});
