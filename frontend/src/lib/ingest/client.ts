/**
 * Driving the ingest worker from the main thread.
 *
 * A worker is a channel, not a function call, and every caller would otherwise have to
 * remember the same four things: terminate it when the component goes away, terminate it
 * when the user cancels, resolve exactly once, and never leave the tab holding a worker
 * that is parsing a file nobody is waiting for any more.
 */

import { ingestErrors } from '$copy/en';

import type { IngestRequest, IngestResponse, ParseResult } from './types';
import { IngestError } from './types';

export type IngestProgress = { bytesRead: number; totalBytes: number; fixes: number };

export type IngestOptions = {
	claims?: string[];
	windowHours?: number;
	onProgress?: (progress: IngestProgress) => void;
	signal?: AbortSignal;
};

/** A worker per call: parsing is one-shot, and a fresh one cannot inherit stale state. */
function createWorker(): Worker {
	return new Worker(new URL('./worker.ts', import.meta.url), { type: 'module' });
}

export function ingestFile(file: File, options: IngestOptions = {}): Promise<ParseResult> {
	return new Promise<ParseResult>((resolve, reject) => {
		const worker = createWorker();
		let settled = false;

		const finish = (action: () => void) => {
			if (settled) return;
			settled = true;
			worker.terminate();
			options.signal?.removeEventListener('abort', onAbort);
			action();
		};

		function onAbort() {
			finish(() => reject(new IngestError('cancelled', ingestErrors.cancelled)));
		}

		worker.addEventListener('message', (event: MessageEvent<IngestResponse>) => {
			const message = event.data;
			switch (message.type) {
				case 'progress':
					options.onProgress?.(message);
					return;
				case 'done':
					finish(() =>
						resolve({ fixes: message.fixes, stats: message.stats, warnings: message.warnings })
					);
					return;
				case 'error':
					finish(() => reject(new IngestError(message.code, message.message)));
			}
		});

		worker.addEventListener('error', () => {
			finish(() =>
				reject(new IngestError('malformed_json', ingestErrors.malformed_json))
			);
		});

		if (options.signal?.aborted) {
			onAbort();
			return;
		}
		options.signal?.addEventListener('abort', onAbort);

		const request: IngestRequest = {
			type: 'parse',
			file,
			claims: options.claims,
			windowHours: options.windowHours
		};
		worker.postMessage(request);
	});
}
