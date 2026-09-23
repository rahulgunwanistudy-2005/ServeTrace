/**
 * Location ingest worker. Bible §13: files up to 200 MB are parsed off the main thread,
 * and the full history never leaves the device.
 *
 * This file is deliberately thin — it is the part that cannot be unit-tested, so there is
 * as little of it as possible. It receives a message, hands the file's stream to
 * `pipeline.ts`, and posts what comes back. Everything that can be got wrong lives next
 * door, where a test can reach it.
 */

/// <reference lib="webworker" />

import { ingestErrors } from '$copy/en';

import { ingestTimelineStream } from './pipeline';
import { IngestError, type IngestRequest, type IngestResponse } from './types';

const scope = self as unknown as DedicatedWorkerGlobalScope;

function post(message: IngestResponse): void {
	scope.postMessage(message);
}

scope.addEventListener('message', (event: MessageEvent<IngestRequest>) => {
	const request = event.data;
	if (request?.type !== 'parse') return;
	void run(request);
});

async function run(request: IngestRequest): Promise<void> {
	const { file } = request;
	try {
		if (file.size === 0) {
			throw new IngestError('empty_file', ingestErrors.empty_file);
		}

		const result = await ingestTimelineStream(file.stream(), {
			claims: request.claims,
			windowHours: request.windowHours,
			totalBytes: file.size,
			onProgress: ({ bytesRead, fixes }) =>
				post({ type: 'progress', bytesRead, totalBytes: file.size, fixes })
		});

		post({
			type: 'done',
			fixes: result.fixes,
			stats: result.stats,
			warnings: result.warnings
		});
	} catch (error) {
		if (error instanceof IngestError) {
			post({ type: 'error', code: error.code, message: error.message });
			return;
		}
		// An unexpected failure must still reach the user as something they can act on, and
		// must not carry anything read out of the file into a message or a console line.
		post({ type: 'error', code: 'malformed_json', message: ingestErrors.malformed_json });
	}
}
