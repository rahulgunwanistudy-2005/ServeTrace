import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, api } from './client';

function mockFetch(status: number, body: unknown, ok = status < 400) {
	vi.stubGlobal(
		'fetch',
		vi.fn(async () => ({ ok, status, json: async () => body }) as unknown as Response)
	);
}

afterEach(() => vi.unstubAllGlobals());

describe('api client', () => {
	it('returns the parsed body on success', async () => {
		mockFetch(200, { status: 'ok', engine_version: '0.1.0' });
		await expect(api.health()).resolves.toMatchObject({ status: 'ok' });
	});

	it('turns the error envelope into a typed ApiError', async () => {
		mockFetch(413, { error: { code: 'upload_too_large', message: 'Too big.' } });
		await expect(api.health()).rejects.toMatchObject({
			code: 'upload_too_large',
			status: 413,
			message: 'Too big.'
		});
	});

	it('falls back to internal_error for an unrecognised code', async () => {
		mockFetch(500, { error: { code: 'something_new' } });
		await expect(api.health()).rejects.toMatchObject({ code: 'internal_error' });
	});

	it('survives a non-JSON failure body', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => ({
				ok: false,
				status: 502,
				json: async () => {
					throw new SyntaxError('not json');
				}
			}) as unknown as Response)
		);
		await expect(api.health()).rejects.toMatchObject({ code: 'internal_error', status: 502 });
	});

	it('reports a network failure as a network error, not a server error', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => {
				throw new TypeError('Failed to fetch');
			})
		);
		await expect(api.health()).rejects.toMatchObject({ code: 'network', status: 0 });
	});

	it('is an Error subclass, so it can be thrown and caught normally', () => {
		expect(new ApiError('bad_input', 400)).toBeInstanceOf(Error);
	});
});
