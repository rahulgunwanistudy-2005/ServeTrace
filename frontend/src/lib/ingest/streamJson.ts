/**
 * A scanner that pulls one top-level item at a time out of a very large JSON document.
 *
 * Why this exists: a Google Timeline export can be hundreds of megabytes, and the two
 * obvious approaches both fail on it. Reading the file into a string and calling
 * `JSON.parse` needs the file, the string and the whole object graph in memory at once.
 * Pulling in a streaming JSON parser is not an option either — bible §8 pins the
 * dependencies.
 *
 * So: decode the file in chunks, feed it to a state machine one character at a time, and
 * hand each *item* — one element of the array we care about — to `JSON.parse` on its own.
 * Peak memory is one item, and the browser's own parser still does the parsing, which is
 * the part that has to be exactly right.
 *
 * The machine holds every bit of its state in fields, so a chunk boundary in the middle of
 * a key, a string or a number cannot affect the result. That is the whole reason it is a
 * machine and not a scan with look-ahead: look-ahead is correct until the 64 KB boundary
 * lands in the wrong place, and then it is wrong on exactly the files that are too big to
 * debug by hand.
 *
 * Two document shapes are handled, because those are the two Google writes:
 *   - a top-level array: `[ {...}, {...} ]`                → items tagged `''`
 *   - an object of arrays: `{ "semanticSegments": [...] }`  → items tagged with the key
 * Anything else at the top level is stepped over without being materialised.
 */

import { ingestErrors } from '$copy/en';

import { IngestError } from './types';

export type ScannedItem = {
	/** The object key whose array this item came from; `''` for a top-level array. */
	key: string;
	value: unknown;
};

export type ScanOptions = {
	/** Called after each chunk, so the UI can show progress on a long file. */
	onChunk?: (bytesRead: number) => void | Promise<void>;
	/** Keys whose arrays are wanted. Everything else is stepped over. Empty means all. */
	keys?: readonly string[];
	/** Refuse an item larger than this. A malformed file can otherwise look infinite. */
	maxItemChars?: number;
};

const DEFAULT_MAX_ITEM_CHARS = 8 << 20;

type State =
	| 'start'
	| 'object_key'
	| 'in_key'
	| 'colon'
	| 'value'
	| 'array_item'
	| 'collect'
	| 'skip'
	| 'skip_scalar'
	| 'end';

function malformed(message: string): IngestError {
	return new IngestError('malformed_json', message);
}

const TRUNCATED = ingestErrors.truncated;
const NOT_A_HISTORY = ingestErrors.unsupported_format;

/**
 * The state machine. `push` returns an item when one has just been completed.
 *
 * Exported so it can be tested on whole strings and on deliberately awkward chunkings,
 * without needing a `ReadableStream` in the test.
 */
export class JsonItemScanner {
	private state: State = 'start';
	private readonly wanted: ReadonlySet<string> | null;
	private readonly maxItemChars: number;

	/** Where to go when the array being read ends: the document, or the object above it. */
	private arrayReturn: State = 'end';
	/** Where to go when the value currently being stepped over ends. Kept apart from
	 * `arrayReturn` on purpose: a skipped value inside an array would otherwise overwrite
	 * the array's own return, and the scanner would carry on reading the rest of the
	 * document as if it were still inside that array. */
	private skipReturn: State = 'start';
	private depth = 0;
	private inString = false;
	private escaped = false;

	/** The item being collected, as the pieces it arrived in. Joined once, at the end:
	 * appending to a string per character costs several times the rest of the scan put
	 * together on a file of any size. */
	private buffer: string[] = [];
	private bufferLength = 0;
	private keyBuffer = '';
	private currentKey = '';
	private collectingKey = '';
	private wantThisArray = false;
	/** True once a `[` or `{` has been seen: tells a broken file from a wrong one. */
	sawStructure = false;

	constructor(options: { keys?: readonly string[]; maxItemChars?: number } = {}) {
		this.wanted = options.keys && options.keys.length > 0 ? new Set(options.keys) : null;
		this.maxItemChars = options.maxItemChars ?? DEFAULT_MAX_ITEM_CHARS;
	}

	get settled(): boolean {
		return this.state === 'start' || this.state === 'end';
	}

	push(ch: string): ScannedItem | null {
		switch (this.state) {
			case 'start':
				return this.atStart(ch);
			case 'object_key':
				return this.atObjectKey(ch);
			case 'in_key':
				return this.inKey(ch);
			case 'colon':
				if (ch === ':') this.state = 'value';
				else if (!isWhitespace(ch)) throw malformed(NOT_A_HISTORY);
				return null;
			case 'value':
				return this.atValue(ch);
			case 'array_item':
				return this.atArrayItem(ch);
			case 'collect':
				return this.collect(ch);
			case 'skip':
				return this.skip(ch);
			case 'skip_scalar':
				return this.skipScalar(ch);
			case 'end':
				if (!isWhitespace(ch)) throw malformed(NOT_A_HISTORY);
				return null;
		}
	}

	private atStart(ch: string): null {
		if (isWhitespace(ch)) return null;
		this.sawStructure = true;
		if (ch === '[') {
			this.currentKey = '';
			this.wantThisArray = this.wanted === null || this.wanted.has('');
			this.arrayReturn = 'end';
			this.state = 'array_item';
			return null;
		}
		if (ch === '{') {
			this.state = 'object_key';
			return null;
		}
		this.sawStructure = false;
		throw malformed(NOT_A_HISTORY);
	}

	private atObjectKey(ch: string): null {
		if (isWhitespace(ch) || ch === ',') return null;
		if (ch === '}') {
			this.state = 'end';
			return null;
		}
		if (ch === '"') {
			this.keyBuffer = '';
			this.escaped = false;
			this.state = 'in_key';
			return null;
		}
		throw malformed(NOT_A_HISTORY);
	}

	private inKey(ch: string): null {
		if (this.escaped) {
			this.keyBuffer += ch;
			this.escaped = false;
			return null;
		}
		if (ch === '\\') {
			this.escaped = true;
			return null;
		}
		if (ch === '"') {
			this.currentKey = this.keyBuffer;
			this.state = 'colon';
			return null;
		}
		this.keyBuffer += ch;
		return null;
	}

	private atValue(ch: string): null {
		if (isWhitespace(ch)) return null;
		if (ch === '[') {
			this.wantThisArray = this.wanted === null || this.wanted.has(this.currentKey);
			this.arrayReturn = 'object_key';
			this.state = 'array_item';
			return null;
		}
		// Any other value of a top-level key is of no interest, so it is stepped over.
		return this.beginSkip(ch, 'object_key');
	}

	private atArrayItem(ch: string): null {
		if (isWhitespace(ch) || ch === ',') return null;
		if (ch === ']') {
			this.state = this.arrayReturn;
			return null;
		}
		if (this.wantThisArray && (ch === '{' || ch === '[')) {
			this.buffer = [ch];
			this.bufferLength = 1;
			this.depth = 1;
			this.inString = false;
			this.escaped = false;
			this.collectingKey = this.currentKey;
			this.state = 'collect';
			return null;
		}
		// Either an array we do not want, or a scalar sitting in one we do: step over it and
		// come back for the next element.
		return this.beginSkip(ch, 'array_item');
	}

	private beginSkip(ch: string, back: State): null {
		this.skipReturn = back;
		this.inString = false;
		this.escaped = false;
		if (ch === '{' || ch === '[') {
			this.depth = 1;
			this.state = 'skip';
			return null;
		}
		if (ch === '"') {
			this.inString = true;
			this.depth = 0;
			this.state = 'skip';
			return null;
		}
		this.state = 'skip_scalar';
		return null;
	}

	private collect(ch: string): ScannedItem | null {
		this.buffer.push(ch);
		this.bufferLength += 1;
		if (this.bufferLength > this.maxItemChars) {
			throw malformed(ingestErrors.oversizedRecord);
		}
		if (this.inString) {
			if (this.escaped) this.escaped = false;
			else if (ch === '\\') this.escaped = true;
			else if (ch === '"') this.inString = false;
			return null;
		}
		if (ch === '"') this.inString = true;
		else if (ch === '{' || ch === '[') this.depth += 1;
		else if (ch === '}' || ch === ']') {
			this.depth -= 1;
			if (this.depth === 0) {
				const raw = this.buffer.join('');
				this.buffer = [];
				this.bufferLength = 0;
				this.state = 'array_item';
				return { key: this.collectingKey, value: parseItem(raw) };
			}
		}
		return null;
	}

	private skip(ch: string): null {
		if (this.inString) {
			if (this.escaped) this.escaped = false;
			else if (ch === '\\') this.escaped = true;
			else if (ch === '"') {
				this.inString = false;
				if (this.depth === 0) this.state = this.skipReturn;
			}
			return null;
		}
		if (ch === '"') this.inString = true;
		else if (ch === '{' || ch === '[') this.depth += 1;
		else if (ch === '}' || ch === ']') {
			this.depth -= 1;
			if (this.depth === 0) this.state = this.skipReturn;
		}
		return null;
	}

	private skipScalar(ch: string): ScannedItem | null {
		// A bare number, true, false or null: it ends at the first delimiter, and that
		// delimiter still has to be handled by the state we are going back to. That handoff
		// cannot itself complete an item, but the type says so rather than the comment.
		if (ch === ',' || ch === '}' || ch === ']' || isWhitespace(ch)) {
			this.state = this.skipReturn;
			return this.push(ch);
		}
		return null;
	}
}

/**
 * Yield each item of the interesting array(s) in a JSON stream.
 *
 * Malformed input raises `IngestError('malformed_json')` rather than yielding nonsense: a
 * truncated download is a thing that happens, and "we could not read that file" is a
 * better answer than half a location history.
 */
export async function* scanJsonItems(
	stream: ReadableStream<Uint8Array>,
	options: ScanOptions = {}
): AsyncGenerator<ScannedItem> {
	const scanner = new JsonItemScanner(options);
	const reader = stream.getReader();
	const decoder = new TextDecoder();
	let bytesRead = 0;

	try {
		for (;;) {
			const { done, value } = await reader.read();
			if (done) break;
			bytesRead += value.byteLength;
			const text = decoder.decode(value, { stream: true });
			for (let i = 0; i < text.length; i += 1) {
				const item = scanner.push(text[i] as string);
				if (item) yield item;
			}
			if (options.onChunk) await options.onChunk(bytesRead);
		}
		// Flush whatever the decoder was holding: a multi-byte character can straddle the
		// last chunk boundary, and dropping its tail would corrupt the final record.
		const tail = decoder.decode();
		for (let i = 0; i < tail.length; i += 1) {
			const item = scanner.push(tail[i] as string);
			if (item) yield item;
		}
	} finally {
		reader.releaseLock();
	}

	if (!scanner.sawStructure) throw malformed(NOT_A_HISTORY);
	if (!scanner.settled) throw malformed(TRUNCATED);
}

/** Scan a whole string. Used by tests and by the small-file path. */
export function scanJsonString(text: string, options: ScanOptions = {}): ScannedItem[] {
	const scanner = new JsonItemScanner(options);
	const items: ScannedItem[] = [];
	for (let i = 0; i < text.length; i += 1) {
		const item = scanner.push(text[i] as string);
		if (item) items.push(item);
	}
	if (!scanner.sawStructure) throw malformed(NOT_A_HISTORY);
	if (!scanner.settled) throw malformed(TRUNCATED);
	return items;
}

function parseItem(raw: string): unknown {
	try {
		return JSON.parse(raw) as unknown;
	} catch {
		throw malformed(ingestErrors.unreadableRecord);
	}
}

function isWhitespace(ch: string): boolean {
	return ch === ' ' || ch === '\n' || ch === '\r' || ch === '\t';
}
