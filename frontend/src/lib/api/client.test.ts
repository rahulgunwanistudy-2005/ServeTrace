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

type Call = { url: string; init?: RequestInit };

function captureFetch(body: unknown) {
	const calls: Call[] = [];
	vi.stubGlobal(
		'fetch',
		vi.fn(async (url: string, init?: RequestInit) => {
			calls.push({ url, init });
			return { ok: true, status: 200, json: async () => body } as unknown as Response;
		})
	);
	return {
		get first(): Call {
			const call = calls[0];
			if (!call) throw new Error('fetch was never called');
			return call;
		}
	};
}

describe('extract', () => {
	it('posts the file as multipart form data under the name the server expects', async () => {
		const calls = captureFetch({ provider: 'none', draft: {} });
		await api.extract(new File(['%PDF-1.7'], 'affidavit.pdf', { type: 'application/pdf' }));

		const { url, init } = calls.first;
		expect(url).toBe('/api/extract');
		expect(init?.method).toBe('POST');
		const body = init?.body as FormData;
		expect(body).toBeInstanceOf(FormData);
		expect((body.get('file') as File).name).toBe('affidavit.pdf');
	});

	it('lets the browser set the multipart boundary', () => {
		// A hand-written content-type here would have no boundary, and the upload would
		// arrive as an unparseable blob.
		const calls = captureFetch({});
		void api.extract(new File([''], 'a.pdf'));
		expect(calls.first.init?.headers).toBeUndefined();
	});

	it('reports a refused upload as its typed code', async () => {
		mockFetch(415, { error: { code: 'unsupported_file', message: 'No.' } });
		await expect(api.extract(new File([''], 'a.heic'))).rejects.toMatchObject({
			code: 'unsupported_file'
		});
	});
});

describe('geocode', () => {
	it('sends the address and nothing else', async () => {
		const calls = captureFetch({ result: null });
		await api.geocode('2100 White Plains Road, Bronx, NY 10462');

		const { url, init } = calls.first;
		expect(url).toBe('/api/geocode');
		expect(JSON.parse(init?.body as string)).toEqual({
			address: '2100 White Plains Road, Bronx, NY 10462'
		});
	});

	it('never puts the address in the URL', async () => {
		// Bible §16: no personal data in a query string, and an address is personal data.
		const calls = captureFetch({ result: null });
		await api.geocode('2100 White Plains Road');
		expect(calls.first.url).not.toContain('White Plains');
	});

	it('passes through a null result rather than inventing a pin', async () => {
		mockFetch(200, { result: null });
		await expect(api.geocode('nowhere')).resolves.toEqual({ result: null });
	});
});
