import { describe, expect, it } from 'vitest';

import { ApiError, type DocumentExtraction, type ExtractedAffidavit } from '$lib/api/client';
import { buildAffidavit, placeOf } from '$lib/check/affidavit';
import { valuesFrom } from '$lib/check/review';
import {
	MAX_FILES,
	admit,
	flagCount,
	fromExtraction,
	initials,
	missingRequired,
	pool,
	queued,
	retryable,
	tally,
	withRetry
} from './batch';

const POINT = { lat: 40.68, lng: -73.97 };

function found(over: Partial<ExtractedAffidavit['draft']> = {}, confidence = {}): ExtractedAffidavit {
	return {
		draft: {
			defendant_name: 'Ana Arvel',
			server_name: 'R. Tallowbeck',
			served_date: '2025-03-03',
			served_time: '09:00',
			served_address: '100 Atlantic Ave, Brooklyn',
			served_location: POINT,
			method: '308_2',
			field_confidence: confidence,
			evidence_quotes: {},
			evidence: {},
			attempts: [],
			...over
		},
		notes: [],
		pages: [0]
	} as ExtractedAffidavit;
}

function extraction(affidavits: ExtractedAffidavit[], over: Partial<DocumentExtraction> = {}) {
	return {
		page_types: ['affidavit_of_service'],
		affidavits,
		notes: [],
		provider: 'none',
		source_sha256: 'a'.repeat(64),
		n_pages: 1,
		has_text_layer: true,
		used_vision: false,
		previews: [],
		...over
	} as DocumentExtraction;
}

const file = (name = 'a.pdf') => new File(['%PDF'], name, { type: 'application/pdf' });

describe('reading a file into queue rows', () => {
	it('marks a confident, complete read ok', () => {
		const [row] = fromExtraction(queued(file()), extraction([found()]));
		expect(row!.status).toBe('ok');
	});

	it('sends a flagged field to review', () => {
		const [row] = fromExtraction(queued(file()), extraction([found({}, { served_address: 0.4 })]));
		expect(row!.status).toBe('review');
		expect(flagCount(row!)).toBe(1);
	});

	it('sends a read missing what the engine needs to review, however confident', () => {
		const [row] = fromExtraction(queued(file()), extraction([found({ served_time: null })]));
		expect(row!.status).toBe('review');
	});

	it('makes one row per affidavit in a court file', () => {
		const rows = fromExtraction(queued(file()), extraction([found(), found()]));
		expect(rows.map((r) => r.index)).toEqual([0, 1]);
		expect(new Set(rows.map((r) => r.id)).size).toBe(2);
	});

	it('fails a file with no affidavit in it, and one the reader could not read', () => {
		expect(fromExtraction(queued(file()), extraction([]))[0]!.fail).toBe('no_affidavit');
		const down = extraction([found()], {
			notes: [{ field: 'reader', level: 'error', message: 'down' }]
		});
		expect(fromExtraction(queued(file()), down)[0]!.fail).toBe('reader');
	});

	it('needs a server name or a licence, either will do', () => {
		const values = valuesFrom(found().draft);
		expect(missingRequired(values)).toEqual([]);
		expect(missingRequired({ ...values, server_name: '' })).toEqual(['server_name']);
		expect(missingRequired({ ...values, server_name: '', server_license: '1234567' })).toEqual([]);
	});
});

describe('masking and counting', () => {
	it('shows initials, never the name', () => {
		expect(initials('ana  arvel')).toBe('A. A.');
		expect(initials('')).toBe('—');
		expect(initials(null)).toBe('—');
	});

	it('admits files up to the cap and counts the rest', () => {
		const files = Array.from({ length: 5 }, (_, i) => file(`${i}.pdf`));
		expect(admit(MAX_FILES - 2, files)).toMatchObject({ refused: 3 });
		expect(admit(0, files).accepted).toHaveLength(5);
	});

	it('tallies statuses', () => {
		const rows = [queued(file()), ...fromExtraction(queued(file()), extraction([found()]))];
		expect(tally(rows)).toMatchObject({ queued: 1, ok: 1, review: 0 });
	});
});

describe('trying again', () => {
	it('retries a rate limit once, waiting what the server asked', async () => {
		const waits: number[] = [];
		let calls = 0;
		const result = await withRetry(
			async () => {
				calls += 1;
				if (calls === 1) throw new ApiError('rate_limited', 429, undefined, 7);
				return 'read';
			},
			async (ms) => void waits.push(ms)
		);
		expect(result).toBe('read');
		expect(waits).toEqual([7000]);
	});

	it('uses the default backoff when the server says nothing', async () => {
		const waits: number[] = [];
		let calls = 0;
		await withRetry(
			async () => {
				if (++calls === 1) throw new ApiError('upstream_error', 503);
				return 1;
			},
			async (ms) => void waits.push(ms),
			2
		);
		expect(waits).toEqual([2000]);
	});

	it('retries only once', async () => {
		let calls = 0;
		await expect(
			withRetry(
				async () => {
					calls += 1;
					throw new ApiError('network', 0);
				},
				async () => {}
			)
		).rejects.toBeInstanceOf(ApiError);
		expect(calls).toBe(2);
	});

	it('never retries a refusal about the file itself', async () => {
		let calls = 0;
		await expect(
			withRetry(
				async () => {
					calls += 1;
					throw new ApiError('bad_input', 400);
				},
				async () => {}
			)
		).rejects.toBeInstanceOf(ApiError);
		expect(calls).toBe(1);
		expect(retryable(new Error('x'))).toBe(false);
	});
});

describe('the pool', () => {
	it('never has more than the limit in flight, and finishes everything', async () => {
		let inFlight = 0;
		let peak = 0;
		const done: number[] = [];
		await pool([1, 2, 3, 4, 5, 6, 7], 3, async (n) => {
			inFlight += 1;
			peak = Math.max(peak, inFlight);
			await new Promise((r) => setTimeout(r, 5));
			done.push(n);
			inFlight -= 1;
		});
		expect(peak).toBe(3);
		expect(done.sort()).toEqual([1, 2, 3, 4, 5, 6, 7]);
	});

	it('handles an empty list', async () => {
		await expect(pool([], 3, async () => {})).resolves.toBeUndefined();
	});
});

describe('building the affidavit', () => {
	it("reuses the reader's point when the address is unchanged", async () => {
		let lookups = 0;
		const geocode = async () => {
			lookups += 1;
			return { lat: 0, lng: 0 };
		};
		expect(await placeOf('100 Atlantic Ave', { address: '100 atlantic ave ', location: POINT }, geocode)).toEqual(POINT);
		expect(lookups).toBe(0);
		await placeOf('9 Other St', { address: '100 Atlantic Ave', location: POINT }, geocode);
		expect(lookups).toBe(1);
	});

	it('reads the time as New York wall-clock and marks it confirmed', async () => {
		const draft = found().draft;
		const built = await buildAffidavit({
			values: valuesFrom(draft),
			attempts: [],
			draft,
			sourceSha256: 'b'.repeat(64),
			geocode: async () => null
		});
		expect(built.served_at).toBe('2025-03-03T14:00:00.000Z');
		expect(built.served_location).toEqual(POINT);
		expect(built.user_confirmed).toBe(true);
		expect(built.source_sha256).toBe('b'.repeat(64));
	});

	it('refuses an address nobody can place', async () => {
		const draft = found({ served_location: null }).draft;
		await expect(
			buildAffidavit({
				values: valuesFrom(draft),
				attempts: [],
				draft,
				sourceSha256: null,
				geocode: async () => null
			})
		).rejects.toBeInstanceOf(ApiError);
	});
});

describe('typing one in', () => {
	it('keeps what the validators read and opens for review', async () => {
		const { manual } = await import('./batch');
		const down = extraction([found({ method: '308_4', served_time: null })], {
			notes: [{ field: 'reader', level: 'error', message: 'down' }]
		});
		const [failed] = fromExtraction(queued(file()), down);
		const row = manual(failed!);
		expect(row.status).toBe('review');
		expect(row.values.method).toBe('308_4');
	});
});
