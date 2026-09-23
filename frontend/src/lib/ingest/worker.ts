/**
 * Location ingest worker. Bible §13: files up to 200 MB are parsed off the main thread,
 * and the full history never leaves the device.
 *
 * Session 2 fills this in. The message contract is fixed here so the UI can be built
 * against it.
 */

import type { LocationFix } from './types';

export type IngestRequest =
	| { kind: 'google'; file: File }
	| { kind: 'csv'; file: File; columns: Record<string, string> };

export type IngestResponse =
	| { status: 'progress'; parsed: number }
	| { status: 'done'; fixes: LocationFix[]; warnings: string[] }
	| { status: 'error'; message: string };

export {};
