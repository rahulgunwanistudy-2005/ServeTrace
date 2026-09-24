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
export type Affidavit = components['schemas']['Affidavit'];
export type LocationFix = components['schemas']['LocationFix'];
export type HouseholdMember = components['schemas']['HouseholdMember'];
export type AnalyzeRequest = components['schemas']['AnalyzeRequest'];
export type CaseAnalysis = components['schemas']['CaseAnalysis'];
export type ClaimVerdict = components['schemas']['ClaimVerdict'];
export type ClaimTier = components['schemas']['ClaimTier'];
export type Finding = components['schemas']['Finding'];
export type Severity = components['schemas']['Severity'];
export type Deadlines = components['schemas']['Deadlines'];
export type AdvocateAnalysis = components['schemas']['AdvocateAnalysis'];
export type AdvocateColumnMapping = components['schemas']['AdvocateColumnMapping'];
export type AdvocateStats = components['schemas']['AdvocateStats'];
export type ServerReport = components['schemas']['ServerReport'];
export type ImpossiblePair = components['schemas']['ImpossiblePair'];
export type ServiceRecord = components['schemas']['ServiceRecord'];
export type RejectedRow = components['schemas']['RejectedRow'];
export type AffiantStatement = components['schemas']['AffiantStatement'];
export type PacketRequest = components['schemas']['PacketRequest'];

const JSON_HEADERS = { 'content-type': 'application/json' } as const;

/** POST JSON, get a PDF back. Shares `toError` so a refusal reads the same everywhere. */
async function pdf(path: string, body: unknown): Promise<Blob> {
	let response: Response;
	try {
		response = await fetch(`/api${path}`, {
			method: 'POST',
			headers: JSON_HEADERS,
			body: JSON.stringify(body)
		});
	} catch {
		throw new ApiError('network', 0);
	}
	if (!response.ok) throw await toError(response);
	return await response.blob();
}

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

	/**
	 * Run the engine. The request carries everything the verdict depends on and the
	 * response carries the whole analysis back: there is no case id, because there is
	 * nothing stored to come back for (bible §16).
	 *
	 * Only fixes already windowed to the hours around the claimed times are sent
	 * (bible §13). `lib/ingest/window.ts` is what makes that true; this function
	 * trusts its caller and the server caps the count either way.
	 */
	analyze: (body: AnalyzeRequest) =>
		request<CaseAnalysis>('/analyze', {
			method: 'POST',
			headers: JSON_HEADERS,
			body: JSON.stringify(body)
		}),

	/**
	 * The two documents, both `application/pdf`. Bible §15.
	 *
	 * The client posts the analysis it already holds rather than a case id, for the same
	 * reason the advocate CSV export does: nothing is stored, so there is no id to post.
	 */
	documents: {
		packet: (analysis: CaseAnalysis, mapPngBase64: string | null, fixes: LocationFix[] = []) =>
			pdf('/documents/packet', {
				analysis,
				fixes,
				map_png_base64: mapPngBase64,
				affiant_name: analysis.affidavit.defendant_name
			}),

		/**
		 * The draft supporting affidavit. `affiant` is not optional and is not inferred:
		 * every boolean on it gates a paragraph somebody is going to swear to, and the only
		 * person who can set one is the person signing.
		 */
		affidavit: (analysis: CaseAnalysis, affiant: AffiantStatement) =>
			pdf('/documents/affidavit', { analysis, affiant })
	},

	advocate: {
		/**
		 * The file's own column names, so the user can map them before anything is
		 * interpreted. A separate call because the mapping is a decision they make, and
		 * the columns have to be on screen before they can make it.
		 */
		columns: (file: File) => {
			const body = new FormData();
			body.append('file', file);
			return request<{ columns: string[] }>('/advocate/columns', { method: 'POST', body });
		},

		/**
		 * A spreadsheet of filings in, servers ranked by impossibility out. Unlike the
		 * defendant flow this file is not windowed in the browser: every row is a sworn
		 * public filing rather than one person's movements, and the whole point is the
		 * sequence across all of them.
		 */
		analyze: (file: File, mapping: AdvocateColumnMapping) => {
			const body = new FormData();
			body.append('file', file);
			body.append('mapping', JSON.stringify(mapping));
			return request<AdvocateAnalysis>('/advocate/analyze', { method: 'POST', body });
		},

		/**
		 * The report as a file to attach to something. The client posts back the report it
		 * already holds: there is no case id because nothing is stored, and re-uploading a
		 * spreadsheet to get a CSV of what is already on screen would be the wrong trade.
		 */
		exportCsv: async (reports: ServerReport[], kind: 'pairs' | 'servers'): Promise<Blob> => {
			let response: Response;
			try {
				response = await fetch(`/api/advocate/export.csv?kind=${kind}`, {
					method: 'POST',
					headers: JSON_HEADERS,
					body: JSON.stringify(reports)
				});
			} catch {
				throw new ApiError('network', 0);
			}
			if (!response.ok) throw await toError(response);
			return await response.blob();
		}
	}
} as const;
