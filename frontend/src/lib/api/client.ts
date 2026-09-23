/**
 * The single place the frontend talks to the backend.
 *
 * Everything the server returns on failure is the envelope from `api/errors.py`:
 * `{ error: { code, message } }`. Components switch on `code`, never on message text.
 */

import { errors, type ErrorCode } from '$copy/en';

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

export type Health = {
	status: string;
	engine_version: string;
	params_version: string;
	llm_provider: string;
};

export const api = {
	health: () => request<Health>('/health'),

	/** Session 2. */
	extract: (_file: File): Promise<never> => {
		throw new Error('Not implemented until session 2');
	},

	/** Session 3. */
	analyze: (_body: unknown): Promise<never> => {
		throw new Error('Not implemented until session 3');
	}
} as const;
