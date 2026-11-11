/**
 * Photos from that day: where and when a camera says each one was taken. Bible §13 (v1.1).
 *
 * Most people never switched Google Timeline on, and nearly everyone took a photo that
 * evening. A phone writes the place and the time into each photo's EXIF block, and that
 * block is all this module reads:
 *
 * - **Metadata only.** exifr is given the header segments it asks for (or, for HEIC, the
 *   TIFF block `heic.ts` cuts out). Pixels are never decoded, nothing is uploaded, and no
 *   preview or object URL is ever made — the screen lists file names, not thumbnails.
 * - **Never the filename** in anything sent anywhere: every fix is labelled "Photo taken
 *   here". `IMG_0612.jpg` can carry a name in some phones' formats, and it is not evidence.
 *
 * Time source, in order (bible §13):
 * 1. `GPSDateStamp` + `GPSTimeStamp` — UTC from the satellites. Exact.
 * 2. `DateTimeOriginal` + `OffsetTimeOriginal` — the camera's clock with its zone. Exact.
 * 3. `DateTimeOriginal` alone — the camera's clock, zone unknown. New York is assumed and
 *    the fix carries an hour of uncertainty either way, which the engine only ever spends
 *    in the affidavit's favour (bible §11.1.7).
 * 4. No original time — skipped. A file's modified time is when it was copied, not taken.
 *
 * `reviveValues: false` throughout: exifr would otherwise turn "2025:06:12 19:42:00" into a
 * `Date` in the *browser's* zone, which is the exact bug lessons.md records from session 3.
 */

import exifr from 'exifr';

import { nyLocalToInstant } from '../tz';
import type { LocationFix } from '../types';
import { heifTiff, isHeif, type ByteReader } from './heic';

export const PHOTO_DEFAULT_ACCURACY_M = 100;
export const PHOTO_ASSUMED_ZONE_UNCERTAINTY_S = 3600;
export const BURST_METRES = 25;
export const BURST_SECONDS = 60;
export const PHOTO_LABEL = 'Photo taken here';

/** The handful of tags read. Everything else in the block is ignored. */
export const PHOTO_TAGS = [
	'DateTimeOriginal',
	'OffsetTimeOriginal',
	'GPSDateStamp',
	'GPSTimeStamp',
	'GPSLatitude',
	'GPSLatitudeRef',
	'GPSLongitude',
	'GPSLongitudeRef',
	'GPSHPositioningError'
] as const;

const EXIFR_OPTIONS = {
	tiff: true,
	exif: true,
	gps: true,
	ifd1: false,
	interop: false,
	makerNote: false,
	userComment: false,
	xmp: false,
	icc: false,
	iptc: false,
	jfif: false,
	ihdr: false,
	reviveValues: false,
	translateValues: false,
	translateKeys: true,
	silentErrors: true,
	pick: [...PHOTO_TAGS]
};

/** What exifr hands back for the tags above. Every one may be missing. */
export type PhotoMeta = {
	DateTimeOriginal?: unknown;
	OffsetTimeOriginal?: unknown;
	GPSDateStamp?: unknown;
	GPSTimeStamp?: unknown;
	GPSHPositioningError?: unknown;
	latitude?: unknown;
	longitude?: unknown;
};

export type PhotoOutcome =
	| { kind: 'fix'; fix: LocationFix }
	| { kind: 'no_location' }
	| { kind: 'no_time' };

const EXIF_STAMP = /^(\d{4}):(\d{2}):(\d{2})[ T](\d{2}):(\d{2}):(\d{2})/;
const OFFSET = /^([+-])(\d{2}):?(\d{2})$/;

function finite(value: unknown): number | null {
	return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function exactFromGps(meta: PhotoMeta): Date | null {
	if (typeof meta.GPSDateStamp !== 'string' || !Array.isArray(meta.GPSTimeStamp)) return null;
	const day = /^(\d{4})[:-](\d{2})[:-](\d{2})/.exec(meta.GPSDateStamp.trim());
	const [h, m, s] = meta.GPSTimeStamp.map(finite);
	if (!day || h == null || m == null || s == null) return null;
	const ms = Date.UTC(+day[1]!, +day[2]! - 1, +day[3]!, h, m, Math.floor(s), Math.round((s % 1) * 1000));
	return Number.isFinite(ms) ? new Date(ms) : null;
}

function exactFromOffset(stamp: RegExpExecArray, offset: unknown): Date | null {
	if (typeof offset !== 'string') return null;
	const zone = OFFSET.exec(offset.trim());
	if (!zone) return null;
	const sign = zone[1] === '-' ? -1 : 1;
	const offsetMs = sign * (Number(zone[2]) * 60 + Number(zone[3])) * 60_000;
	const wall = Date.UTC(+stamp[1]!, +stamp[2]! - 1, +stamp[3]!, +stamp[4]!, +stamp[5]!, +stamp[6]!);
	return Number.isFinite(wall) ? new Date(wall - offsetMs) : null;
}

/**
 * One photo's metadata to a fix, or to the reason it cannot be one. Pure: the whole time
 * ladder is testable without a file.
 */
export function photoToFix(meta: PhotoMeta): PhotoOutcome {
	const stamp =
		typeof meta.DateTimeOriginal === 'string' ? EXIF_STAMP.exec(meta.DateTimeOriginal) : null;
	if (!stamp) return { kind: 'no_time' };

	let at = exactFromGps(meta) ?? exactFromOffset(stamp, meta.OffsetTimeOriginal);
	let assumed = false;
	if (!at) {
		const local = nyLocalToInstant(
			`${stamp[1]}-${stamp[2]}-${stamp[3]}`,
			`${stamp[4]}:${stamp[5]}:${stamp[6]}`
		);
		if (!local) return { kind: 'no_time' };
		at = new Date(local.iso);
		assumed = true;
	}

	const lat = finite(meta.latitude);
	const lng = finite(meta.longitude);
	if (lat == null || lng == null || Math.abs(lat) > 90 || Math.abs(lng) > 180) {
		return { kind: 'no_location' };
	}
	// (0, 0) is where a phone writes a GPS block it never filled in, not a place in the Gulf
	// of Guinea that someone in the Bronx photographed.
	if (lat === 0 && lng === 0) return { kind: 'no_location' };

	const error = finite(meta.GPSHPositioningError);
	return {
		kind: 'fix',
		fix: {
			t: at.toISOString(),
			loc: { lat, lng },
			accuracy_m: error != null && error > 0 ? error : PHOTO_DEFAULT_ACCURACY_M,
			kind: 'photo',
			source: 'photo',
			label: PHOTO_LABEL,
			time_uncertainty_s: assumed ? PHOTO_ASSUMED_ZONE_UNCERTAINTY_S : 0,
			tz_assumed: assumed
		}
	};
}

function metres(a: LocationFix, b: LocationFix): number {
	const rad = Math.PI / 180;
	const dLat = (b.loc.lat - a.loc.lat) * rad;
	const dLng = (b.loc.lng - a.loc.lng) * rad;
	const h =
		Math.sin(dLat / 2) ** 2 +
		Math.cos(a.loc.lat * rad) * Math.cos(b.loc.lat * rad) * Math.sin(dLng / 2) ** 2;
	return 2 * 6_371_008.8 * Math.asin(Math.min(1, Math.sqrt(h)));
}

/**
 * A burst of shots of the same thing is one observation, not five. Within 25 m and 60 s of
 * the last photo kept, a photo is dropped, so a person who held the shutter down does not
 * outweigh one who took a single picture. The first of the burst is kept.
 */
export function collapseBursts(fixes: LocationFix[]): LocationFix[] {
	const sorted = [...fixes].sort((a, b) => Date.parse(a.t) - Date.parse(b.t));
	const kept: LocationFix[] = [];
	for (const fix of sorted) {
		const last = kept[kept.length - 1];
		if (
			last &&
			Math.abs(Date.parse(fix.t) - Date.parse(last.t)) <= BURST_SECONDS * 1000 &&
			metres(fix, last) <= BURST_METRES
		) {
			continue;
		}
		kept.push(fix);
	}
	return kept;
}

/** Read the tags from one file's bytes. Never throws: an unreadable photo is reported as one. */
export async function readPhotoMeta(read: ByteReader, size: number): Promise<PhotoMeta | null> {
	try {
		const head = await read(0, Math.min(size, 16));
		if (isHeif(head)) {
			const tiff = await heifTiff(read, size);
			if (!tiff) return null;
			return ((await exifr.parse(tiff, EXIFR_OPTIONS)) as PhotoMeta | undefined) ?? null;
		}
		// JPEG and the rest: exifr reads the APP1 segment it needs. The whole file is handed
		// over only when it is small; a large JPEG is read from its first 256 KB, which is
		// where every camera writes its EXIF block.
		const bytes = await read(0, Math.min(size, 256 * 1024));
		return ((await exifr.parse(bytes, EXIFR_OPTIONS)) as PhotoMeta | undefined) ?? null;
	} catch {
		return null;
	}
}

export type PhotoSummary = {
	/** Files given. */
	read: number;
	/** Photos with a usable time and place, before bursts were collapsed. */
	withLocation: number;
	/** Photos with a time but no place: GPS off, or stripped by a messaging app. */
	timeOnly: number;
	/** Photos with no original time, or that could not be read at all. */
	skipped: number;
	/** Of the fixes, how many had their zone assumed. */
	zoneAssumed: number;
	fixes: LocationFix[];
};

/** A `ByteReader` over a `Blob`, reading only the slices asked for. */
export function blobReader(blob: Blob): ByteReader {
	return async (offset, length) =>
		new Uint8Array(await blob.slice(offset, offset + length).arrayBuffer());
}

/** Every chosen photo to fixes. Bounded concurrency so a 500-photo pick stays responsive. */
export async function parsePhotos(files: Blob[], concurrency = 6): Promise<PhotoSummary> {
	const outcomes: (PhotoOutcome | null)[] = new Array(files.length).fill(null);
	let next = 0;
	async function worker(): Promise<void> {
		while (next < files.length) {
			const index = next++;
			const file = files[index]!;
			const meta = await readPhotoMeta(blobReader(file), file.size);
			outcomes[index] = meta ? photoToFix(meta) : null;
		}
	}
	await Promise.all(Array.from({ length: Math.min(concurrency, files.length) }, worker));
	return summarise(outcomes);
}

export function summarise(outcomes: (PhotoOutcome | null)[]): PhotoSummary {
	const fixes = outcomes.flatMap((o) => (o?.kind === 'fix' ? [o.fix] : []));
	const collapsed = collapseBursts(fixes);
	return {
		read: outcomes.length,
		withLocation: fixes.length,
		timeOnly: outcomes.filter((o) => o?.kind === 'no_location').length,
		skipped: outcomes.filter((o) => o === null || o.kind === 'no_time').length,
		zoneAssumed: collapsed.filter((f) => f.tz_assumed).length,
		fixes: collapsed
	};
}
