/**
 * The single place the frontend talks to the backend.
 *
 * Everything the server returns on failure is the envelope from `api/errors.py`:
 * `{ error: { code, message } }`. Components switch on `code`, never on message text.
 */

import { errors, type ErrorCode } from '$copy/en';
import type { components } from './schema';

export class ApiError extends Error {
	readonly code: ErrorCode;
	readonly status: number;

	constructor(code: ErrorCode, status: number, message?: string) {
		super(message ?? errors[code] ?? errors.internal_error);
		this.name = 'ApiError';
		this.code = code;
		this.status = status;
	}
}

type Envelope = { error?: { code?: string; message?: string } };

function isErrorCode(value: string): value is ErrorCode {
	return value in errors;
}

async function toError(response: Response): Promise<ApiError> {
	let body: Envelope = {};
	try {
		body = (await response.json()) as Envelope;
	} catch {
		// A non-JSON failure (a proxy error page, say) still has to reach the user as a
		// typed error rather than as raw HTML.
		return new ApiError('internal_error', response.status);
	}
	const raw = body.error?.code ?? 'internal_error';
	const code: ErrorCode = isErrorCode(raw) ? raw : 'internal_error';
	return new ApiError(code, response.status, body.error?.message);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
	let response: Response;
	try {
		response = await fetch(`/api${path}`, init);
	} catch {
		throw new ApiError('network', 0);
	}
	if (!response.ok) throw await toError(response);
	return (await response.json()) as T;
}

/** Generated from the backend's OpenAPI document. Never hand-written. Bible §7. */
export type Health = components['schemas']['Health'];
export type ExtractionResult = components['schemas']['ExtractionResult'];
export type AffidavitDraft = components['schemas']['AffidavitDraft'];
export type ValidationNote = components['schemas']['ValidationNote'];
export type GeocodeResponse = components['schemas']['GeocodeResponse'];
export type GeocodeResult = components['schemas']['GeocodeResult'];

const JSON_HEADERS = { 'content-type': 'application/json' } as const;

export const api = {
	health: () => request<Health>('/health'),

	/**
	 * Upload one affidavit of service. The file leaves the device; nothing else does,
	 * and the server keeps no copy of it (bible §16).
	 */
	extract: (file: File) => {
		const body = new FormData();
		body.append('file', file);
		return request<ExtractionResult>('/extract', { method: 'POST', body });
	},

	/**
	 * Resolve one New York City address. The address is the entire request: when the
	 * source is a bank statement, the merchant and the amount stay in the browser
	 * (bible §13).
	 */
	geocode: (address: string) =>
		request<GeocodeResponse>('/geocode', {
			method: 'POST',
			headers: JSON_HEADERS,
			body: JSON.stringify({ address })
		}),

	/** Session 4, with the engine. Only windowed fixes are ever sent here (bible §13). */
	analyze: (_body: unknown): Promise<never> => {
		throw new Error('Not implemented until session 4');
	}
} as const;
