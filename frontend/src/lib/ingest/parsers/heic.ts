/**
 * Finding the EXIF block inside a HEIC/HEIF photo, reading as little of the file as possible.
 *
 * Why this exists rather than handing the whole file to exifr: exifr 7.1.3 locates the
 * Exif item from the `iloc` box but ignores the item's `base_offset`, so it reads the
 * wrong bytes in any HEIC whose writer uses one. iPhones write a base offset of zero and
 * work; libheif (Samsung, most converters, our own fixtures) writes a real one and fails
 * with "Malformed EXIF data". This walks the ISO-BMFF boxes per ISO/IEC 14496-12 and
 * 23008-12, returns the TIFF block, and exifr parses that.
 *
 * It also keeps the photo parser honest about "metadata only": the reads are the `meta`
 * box and the Exif extent, never the image data. Every size is bounded, because a file
 * picked from a camera roll is input like any other.
 */

/** Read `length` bytes at `offset`. A `Blob.slice` in the browser, a buffer view in tests. */
export type ByteReader = (offset: number, length: number) => Promise<Uint8Array>;

const MAX_META_BYTES = 1 << 20;
const MAX_EXIF_BYTES = 1 << 20;
const MAX_TOP_LEVEL_BOXES = 64;

const BRANDS = ['heic', 'heix', 'hevc', 'heim', 'heis', 'mif1', 'msf1', 'avif'];

type Box = { type: string; start: number; end: number; body: number };

function u16(b: Uint8Array, at: number): number {
	return (b[at]! << 8) | b[at + 1]!;
}

function u32(b: Uint8Array, at: number): number {
	return ((b[at]! << 24) >>> 0) + ((b[at + 1]! << 16) | (b[at + 2]! << 8) | b[at + 3]!);
}

function uN(b: Uint8Array, at: number, size: number): number {
	if (size === 0) return 0;
	if (size === 2) return u16(b, at);
	if (size === 4) return u32(b, at);
	if (size === 8) return u32(b, at) * 2 ** 32 + u32(b, at + 4);
	throw new Error(`unsupported field size ${size}`);
}

function fourcc(b: Uint8Array, at: number): string {
	return String.fromCharCode(b[at]!, b[at + 1]!, b[at + 2]!, b[at + 3]!);
}

/** True when the first bytes say this is an ISO-BMFF image (HEIC, HEIF, AVIF). */
export function isHeif(head: Uint8Array): boolean {
	return head.length >= 12 && fourcc(head, 4) === 'ftyp' && BRANDS.includes(fourcc(head, 8));
}

function children(b: Uint8Array, from: number, to: number): Box[] {
	const boxes: Box[] = [];
	let at = from;
	while (at + 8 <= to) {
		let size = u32(b, at);
		const type = fourcc(b, at + 4);
		let body = at + 8;
		if (size === 1) {
			size = uN(b, at + 8, 8);
			body += 8;
		} else if (size === 0) {
			size = to - at;
		}
		if (size < 8 || at + size > to) break;
		boxes.push({ type, start: at, end: at + size, body });
		at += size;
	}
	return boxes;
}

function exifItemId(meta: Uint8Array, iinf: Box): number | null {
	const version = meta[iinf.body]!;
	let at = iinf.body + 4;
	const count = version === 0 ? u16(meta, at) : u32(meta, at);
	at += version === 0 ? 2 : 4;
	for (const infe of children(meta, at, iinf.end).slice(0, count)) {
		if (infe.type !== 'infe') continue;
		const v = meta[infe.body]!;
		if (v < 2) continue;
		const idAt = infe.body + 4;
		const idSize = v === 3 ? 4 : 2;
		const id = uN(meta, idAt, idSize);
		const type = fourcc(meta, idAt + idSize + 2);
		if (type === 'Exif') return id;
	}
	return null;
}

type Extent = { method: number; offset: number; length: number };

function exifExtent(meta: Uint8Array, iloc: Box, itemId: number): Extent | null {
	const version = meta[iloc.body]!;
	let at = iloc.body + 4;
	const offsetSize = meta[at]! >> 4;
	const lengthSize = meta[at]! & 15;
	const baseSize = meta[at + 1]! >> 4;
	const indexSize = version === 1 || version === 2 ? meta[at + 1]! & 15 : 0;
	at += 2;
	const count = version < 2 ? u16(meta, at) : u32(meta, at);
	at += version < 2 ? 2 : 4;
	for (let i = 0; i < count && at < iloc.end; i++) {
		const id = version < 2 ? u16(meta, at) : u32(meta, at);
		at += version < 2 ? 2 : 4;
		let method = 0;
		if (version === 1 || version === 2) {
			method = u16(meta, at) & 15;
			at += 2;
		}
		at += 2; // data_reference_index
		const base = uN(meta, at, baseSize);
		at += baseSize;
		const extents = u16(meta, at);
		at += 2;
		let first: Extent | null = null;
		for (let e = 0; e < extents; e++) {
			at += indexSize;
			const offset = uN(meta, at, offsetSize);
			at += offsetSize;
			const length = uN(meta, at, lengthSize);
			at += lengthSize;
			if (e === 0) first = { method, offset: base + offset, length };
		}
		if (id === itemId) return first;
	}
	return null;
}

/**
 * The TIFF block ("MM\0*..." or "II*\0...") of a HEIF file's Exif item, or null.
 *
 * Null means "no EXIF here", never "something went wrong": a photo without metadata is
 * an ordinary photo, and the caller reports it as one.
 */
export async function heifTiff(read: ByteReader, fileSize: number): Promise<Uint8Array | null> {
	try {
		let at = 0;
		let meta: { bytes: Uint8Array; offset: number } | null = null;
		for (let n = 0; n < MAX_TOP_LEVEL_BOXES && at + 16 <= fileSize; n++) {
			const head = await read(at, 16);
			let size = u32(head, 0);
			const type = fourcc(head, 4);
			if (size === 1) size = uN(head, 8, 8);
			if (size === 0) size = fileSize - at;
			if (size < 8) return null;
			if (type === 'meta') {
				if (size > MAX_META_BYTES) return null;
				meta = { bytes: await read(at, size), offset: at };
				break;
			}
			at += size;
		}
		if (!meta) return null;

		const bytes = meta.bytes;
		const inner = children(bytes, 12, bytes.length); // `meta` is a full box
		const iinf = inner.find((b) => b.type === 'iinf');
		const iloc = inner.find((b) => b.type === 'iloc');
		if (!iinf || !iloc) return null;
		const id = exifItemId(bytes, iinf);
		if (id === null) return null;
		const extent = exifExtent(bytes, iloc, id);
		if (!extent || extent.length < 10 || extent.length > MAX_EXIF_BYTES) return null;

		let item: Uint8Array;
		if (extent.method === 1) {
			const idat = inner.find((b) => b.type === 'idat');
			if (!idat) return null;
			const from = idat.body + extent.offset;
			item = bytes.subarray(from, from + extent.length);
		} else if (extent.method === 0) {
			item = await read(extent.offset, extent.length);
		} else {
			return null;
		}
		// HEIF's Exif item starts with a 4-byte offset to the TIFF header (ISO/IEC
		// 23008-12 A.2.1), usually 6, skipping an "Exif\0\0" prefix.
		const skip = 4 + u32(item, 0);
		if (skip >= item.length) return null;
		return item.subarray(skip);
	} catch {
		return null;
	}
}
