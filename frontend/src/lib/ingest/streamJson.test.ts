import { describe, expect, it } from 'vitest';

import { demoText } from './demoFixtures';
import { JsonItemScanner, scanJsonItems, scanJsonString } from './streamJson';
import { IngestError } from './types';

/** A stream that hands out the text in pieces of exactly `size`, to force boundaries. */
function streamOf(text: string, size = 7): ReadableStream<Uint8Array> {
	const bytes = new TextEncoder().encode(text);
	let offset = 0;
	return new ReadableStream({
		pull(controller) {
			if (offset >= bytes.length) {
				controller.close();
				return;
			}
			controller.enqueue(bytes.slice(offset, offset + size));
			offset += size;
		}
	});
}

async function collect(text: string, size = 7, keys?: string[]) {
	const items = [];
	for await (const item of scanJsonItems(streamOf(text, size), keys ? { keys } : {})) {
		items.push(item);
	}
	return items;
}

describe('scanJsonString', () => {
	it('yields each element of a top-level array', () => {
		const items = scanJsonString('[{"a":1},{"a":2}]');
		expect(items.map((i) => i.value)).toEqual([{ a: 1 }, { a: 2 }]);
		expect(items.every((i) => i.key === '')).toBe(true);
	});

	it('tags each element with the key of the array it came from', () => {
		const items = scanJsonString('{"one":[{"a":1}],"two":[{"b":2}]}');
		expect(items).toEqual([
			{ key: 'one', value: { a: 1 } },
			{ key: 'two', value: { b: 2 } }
		]);
	});

	it('reads only the arrays it was asked for', () => {
		const items = scanJsonString('{"wanted":[{"a":1}],"other":[{"b":2}]}', { keys: ['wanted'] });
		expect(items).toEqual([{ key: 'wanted', value: { a: 1 } }]);
	});

	it('steps over values that are not arrays', () => {
		const text = '{"note":"hello","count":42,"ok":true,"nothing":null,"want":[{"a":1}]}';
		expect(scanJsonString(text, { keys: ['want'] })).toEqual([{ key: 'want', value: { a: 1 } }]);
	});

	it('steps over a nested object without collecting it', () => {
		const text = '{"meta":{"deep":{"deeper":[1,2,3]}},"want":[{"a":1}]}';
		expect(scanJsonString(text, { keys: ['want'] })).toEqual([{ key: 'want', value: { a: 1 } }]);
	});

	it('is not confused by braces and brackets inside strings', () => {
		const items = scanJsonString('[{"label":"a } weird ] label"},{"label":"plain"}]');
		expect(items.map((i) => (i.value as { label: string }).label)).toEqual([
			'a } weird ] label',
			'plain'
		]);
	});

	it('is not confused by an escaped quote inside a string', () => {
		const items = scanJsonString('[{"label":"say \\"hi\\" }"},{"label":"next"}]');
		expect((items[0]?.value as { label: string }).label).toBe('say "hi" }');
		expect(items).toHaveLength(2);
	});

	it('is not confused by a key that contains an escaped quote', () => {
		const items = scanJsonString('{"od\\"d":[{"a":1}],"want":[{"b":2}]}', { keys: ['want'] });
		expect(items).toEqual([{ key: 'want', value: { b: 2 } }]);
	});

	it('handles nested arrays inside an item', () => {
		const items = scanJsonString('[{"path":[{"p":1},{"p":2}]}]');
		expect(items).toHaveLength(1);
		expect(items[0]?.value).toEqual({ path: [{ p: 1 }, { p: 2 }] });
	});

	it('ignores scalars sitting in an array of records', () => {
		expect(scanJsonString('[1,"two",{"a":3}]')).toEqual([{ key: '', value: { a: 3 } }]);
	});

	it('accepts whitespace and newlines anywhere', () => {
		const text = '{\n  "want" : [\n    { "a" : 1 } ,\n    { "a" : 2 }\n  ]\n}\n';
		expect(scanJsonString(text, { keys: ['want'] })).toHaveLength(2);
	});

	it('accepts an empty array', () => {
		expect(scanJsonString('{"want":[]}', { keys: ['want'] })).toEqual([]);
	});

	it('refuses a file that is not JSON at all', () => {
		expect(() => scanJsonString('Dear sir, I was never served.')).toThrow(IngestError);
	});

	it('refuses a file that stops in the middle of a record', () => {
		// Asserted on the code, not the sentence: the sentence lives in `copy/en.ts` and is
		// allowed to be reworded without a test having an opinion about it.
		expect(() => scanJsonString('[{"a":1},{"b":')).toThrowError(
			expect.objectContaining({ code: 'malformed_json' })
		);
	});

	it('refuses one absurdly large record rather than reading forever', () => {
		const huge = `[{"x":"${'y'.repeat(5_000)}"}]`;
		expect(() => scanJsonString(huge, { maxItemChars: 1_000 })).toThrow(IngestError);
	});

	it('refuses a record that is not valid JSON on its own', () => {
		expect(() => scanJsonString('[{"a":1,}]')).toThrowError(
			expect.objectContaining({ code: 'malformed_json' })
		);
	});
});

describe('JsonItemScanner across chunk boundaries', () => {
	const document = '{"pad":"xx","semanticSegments":[{"a":{"b":"}]"},"c":[1,2]},{"d":"e"}]}';

	it('gives the same answer wherever the file is cut in two', () => {
		const whole = scanJsonString(document);
		for (let cut = 0; cut <= document.length; cut += 1) {
			const scanner = new JsonItemScanner();
			const items = [];
			for (const part of [document.slice(0, cut), document.slice(cut)]) {
				for (const ch of part) {
					const item = scanner.push(ch);
					if (item) items.push(item);
				}
			}
			expect(items, `cut at ${cut}`).toEqual(whole);
		}
	});
});

describe('scanJsonItems', () => {
	it('reads a real Android export from a chunked stream', async () => {
		const text = demoText('maria_contradicted', 'timeline_android.json');
		const items = await collect(text, 64, ['semanticSegments', 'rawSignals']);
		const segments = items.filter((i) => i.key === 'semanticSegments');
		const signals = items.filter((i) => i.key === 'rawSignals');

		expect(segments).toHaveLength(5);
		expect(signals).toHaveLength(16);
	});

	it('reads a real iOS export from a chunked stream', async () => {
		const text = demoText('maria_contradicted', 'timeline_ios.json');
		const items = await collect(text, 64);

		expect(items).toHaveLength(5);
		expect(items.every((i) => i.key === '')).toBe(true);
	});

	it('survives a multi-byte character split across a chunk boundary', async () => {
		// The degree sign in an Android coordinate is two bytes, so this is the file every
		// export hits, not an exotic case.
		const text = '[{"point":"40.7580992°, -73.9855564°"}]';
		for (let size = 1; size <= 12; size += 1) {
			const items = await collect(text, size);
			expect(items[0]?.value, `chunk size ${size}`).toEqual({
				point: '40.7580992°, -73.9855564°'
			});
		}
	});

	it('reports progress as it reads', async () => {
		const text = demoText('maria_contradicted', 'timeline_android.json');
		const seen: number[] = [];
		for await (const _ of scanJsonItems(streamOf(text, 512), {
			onChunk: (bytes) => {
				seen.push(bytes);
			}
		})) {
			// draining
		}
		expect(seen.length).toBeGreaterThan(1);
		expect(seen).toEqual([...seen].sort((a, b) => a - b));
		expect(seen[seen.length - 1]).toBe(new TextEncoder().encode(text).length);
	});
});
