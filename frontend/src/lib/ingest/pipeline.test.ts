import { describe, expect, it } from 'vitest';

import { demoText, expectedFixes, groundTruth } from './demoFixtures';
import { ingestTimelineStream } from './pipeline';
import { IngestError } from './types';

function streamOf(text: string, chunk = 64 * 1024): ReadableStream<Uint8Array> {
	const bytes = new TextEncoder().encode(text);
	let offset = 0;
	return new ReadableStream({
		pull(controller) {
			if (offset >= bytes.length) {
				controller.close();
				return;
			}
			controller.enqueue(bytes.slice(offset, offset + chunk));
			offset += chunk;
		}
	});
}

describe('ingesting a real Android export', () => {
	const text = demoText('maria_contradicted', 'timeline_android.json');
	const truth = groundTruth('maria_contradicted');

	it('finds every fix the generator put there', async () => {
		const result = await ingestTimelineStream(streamOf(text));
		expect(result.fixes).toHaveLength(expectedFixes('maria_contradicted').length);
		expect(result.format).toBe('google_android');
	});

	it('reports the days the export covers, in New York dates', async () => {
		const result = await ingestTimelineStream(streamOf(text));
		expect(result.stats.daysCovered).toEqual(truth.dates_covered);
		expect(result.stats.claimedDaysMissing).toEqual([]);
	});

	it('counts the whole file even when only a few hours are kept', async () => {
		const result = await ingestTimelineStream(streamOf(text), { claims: [truth.claimed_at] });

		expect(result.stats.total).toBe(expectedFixes('maria_contradicted').length);
		expect(result.stats.kept).toBe(result.fixes.length);
		expect(result.stats.kept).toBeLessThan(result.stats.total);
	});

	it('keeps only what is within three hours of the claim', async () => {
		const claim = Date.parse(truth.claimed_at);
		const result = await ingestTimelineStream(streamOf(text), { claims: [truth.claimed_at] });

		for (const fix of result.fixes) {
			const start = Date.parse(fix.t);
			const end = fix.t_end ? Date.parse(fix.t_end) : start;
			expect(start <= claim + 3 * 3_600_000 && end >= claim - 3 * 3_600_000).toBe(true);
		}
	});

	it('warns when the export does not cover the day on the affidavit', async () => {
		const result = await ingestTimelineStream(streamOf(text), {
			claims: ['2024-01-05T19:42:00-05:00']
		});

		expect(result.stats.claimedDaysMissing).toEqual(['2024-01-05']);
		expect(result.warnings.join(' ')).toContain('2024-01-05');
	});

	it('reports progress and the bytes it read', async () => {
		const seen: number[] = [];
		const result = await ingestTimelineStream(streamOf(text, 1024), {
			progressEveryBytes: 1,
			onProgress: ({ bytesRead }) => seen.push(bytesRead)
		});

		expect(seen.length).toBeGreaterThan(1);
		expect(result.stats.bytesRead).toBe(new TextEncoder().encode(text).length);
	});
});

describe('ingesting a real iOS export', () => {
	it('reads it without being told which shape it is', async () => {
		const result = await ingestTimelineStream(
			streamOf(demoText('maria_contradicted', 'timeline_ios.json'))
		);
		expect(result.format).toBe('google_ios');
		expect(result.fixes.length).toBeGreaterThan(0);
	});

	it('agrees with the Android rendering about which days are covered', async () => {
		const ios = await ingestTimelineStream(
			streamOf(demoText('lin_affix_mail_diligence', 'timeline_ios.json'))
		);
		const android = await ingestTimelineStream(
			streamOf(demoText('lin_affix_mail_diligence', 'timeline_android.json'))
		);
		expect(ios.stats.daysCovered).toEqual(android.stats.daysCovered);
	});
});

describe('a file that is not a location history', () => {
	it('says so rather than failing obscurely', async () => {
		await expect(ingestTimelineStream(streamOf('{"orders":[{"total":9.99}]}'))).rejects.toThrow(
			IngestError
		);
	});

	it('carries the code the UI switches on', async () => {
		const error = await ingestTimelineStream(streamOf('{"orders":[{"a":1}]}')).catch((e) => e);
		expect(error).toMatchObject({ code: 'unsupported_format' });
	});

	it('tells the user what it can read', async () => {
		const error = await ingestTimelineStream(streamOf('[]')).catch((e: unknown) => e);
		expect(error).toBeInstanceOf(IngestError);
		expect((error as IngestError).message).toMatch(/Timeline/);
	});

	it('separates "not a history" from "a history we could not read"', async () => {
		// Recognisably Timeline-shaped, but every record is unusable. The user needs to know
		// their export was understood and still gave us nothing.
		const unreadable = JSON.stringify([
			{ startTime: 'whenever', visit: { topCandidate: { placeLocation: 'geo:nope' } } }
		]);
		const error = await ingestTimelineStream(streamOf(unreadable)).catch((e) => e);
		expect(error).toMatchObject({ code: 'no_fixes' });
	});

	it('rejects a truncated download', async () => {
		const whole = demoText('maria_contradicted', 'timeline_ios.json');
		const half = whole.slice(0, Math.floor(whole.length * 0.6));
		const error = await ingestTimelineStream(streamOf(half)).catch((e) => e);
		expect(error).toMatchObject({ code: 'malformed_json' });
	});
});

describe('a large export', () => {
	/** Two years of visits: the shape of a real multi-year history, at a size a test can
	 * afford. The scanner runs at about 17 MB/s, so a 150 MB export is minutes of nothing
	 * on the main thread and about ten seconds in the worker, with progress throughout. */
	function bigAndroidExport(days: number, perDay: number): string {
		const segments: string[] = [];
		for (let day = 0; day < days; day += 1) {
			const date = new Date(Date.UTC(2024, 0, 1) + day * 86_400_000).toISOString().slice(0, 10);
			for (let i = 0; i < perDay; i += 1) {
				const hour = String(i % 24).padStart(2, '0');
				segments.push(
					`{"startTime":"${date}T${hour}:00:00.000-05:00","endTime":"${date}T${hour}:30:00.000-05:00",` +
						`"visit":{"topCandidate":{"placeLocation":{"latLng":"40.${750 + i}000°, -73.98000°"},"semanticType":"HOME"}}}`
				);
			}
		}
		return `{"semanticSegments":[${segments.join(',')}]}`;
	}

	it('windows as it reads, so what it holds is bounded by the window and not the file', async () => {
		const text = bigAndroidExport(730, 60);
		expect(text.length).toBeGreaterThan(8_000_000);

		const result = await ingestTimelineStream(streamOf(text), {
			claims: ['2024-06-15T12:00:00-04:00']
		});

		expect(result.stats.total).toBe(730 * 60);
		// Six hours of one day, out of a file holding nearly forty-four thousand records.
		expect(result.fixes.length).toBeLessThan(30);
		for (const fix of result.fixes) {
			expect(fix.t.startsWith('2024-06-15')).toBe(true);
		}
	});

	it('says so when it has to stop retaining points', async () => {
		const result = await ingestTimelineStream(streamOf(bigAndroidExport(10, 20)), {
			maxRetained: 50
		});

		expect(result.fixes).toHaveLength(50);
		expect(result.stats.total).toBe(200);
		expect(result.warnings.join(' ')).toMatch(/more location points than we can show/);
	});

	it('says so when more points sit around the claim than may be sent', async () => {
		const result = await ingestTimelineStream(streamOf(bigAndroidExport(1, 20)), {
			claims: ['2024-01-01T12:00:00-05:00'],
			maxFixes: 3
		});

		expect(result.fixes).toHaveLength(3);
		expect(result.warnings.join(' ')).toMatch(/closest/);
	});
});
