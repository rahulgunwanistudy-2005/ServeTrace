/**
 * The whole ingest, from a stream of bytes to the fixes that may be sent.
 *
 * This is where the privacy rule in bible §13 is actually enforced. When the claimed times
 * are known, a fix outside ±3h of all of them is dropped *as the file is read* — it is
 * never collected, never counted against memory and never anywhere it could be posted by
 * mistake. What the worker ends up holding is bounded by the window rather than by the
 * size of the file, which is also what makes a 150 MB export survivable.
 *
 * The statistics are accumulated over every fix, including the ones dropped a line later,
 * so the user can still be told what their export covers.
 *
 * It lives apart from `worker.ts` so it can be tested directly: a worker is awkward to
 * drive from a test runner, and the part worth testing is this.
 */

import { ingestErrors, ingestWarnings } from '$copy/en';

import { dedupeFixes } from './dedupe';
import { TIMELINE_KEYS, TimelineRouter } from './parsers/detect';
import { StatsAccumulator } from './stats';
import { scanJsonItems } from './streamJson';
import { IngestError, type IngestFormat, type LocationFix, type ParseResult } from './types';
import { MAX_FIXES, SEARCH_WINDOW_H, windowFixes } from './window';

const HOUR_MS = 3_600_000;

/**
 * With no claimed times to window against, something still has to bound memory. This is
 * the dev page and the "look at my history first" case, not the analysis path.
 */
export const MAX_RETAINED_UNWINDOWED = 200_000;

export type PipelineOptions = {
	claims?: string[];
	windowHours?: number;
	maxFixes?: number;
	maxRetained?: number;
	totalBytes?: number;
	onProgress?: (progress: { bytesRead: number; fixes: number }) => void;
	/** Bytes between progress reports. Every chunk would be noise on a small file. */
	progressEveryBytes?: number;
};

export type TimelineResult = ParseResult & { format: IngestFormat | null };

export async function ingestTimelineStream(
	stream: ReadableStream<Uint8Array>,
	options: PipelineOptions = {}
): Promise<TimelineResult> {
	const claims = (options.claims ?? []).map((iso) => Date.parse(iso)).filter((ms) => !Number.isNaN(ms));
	const span = (options.windowHours ?? SEARCH_WINDOW_H) * HOUR_MS;
	const maxRetained = options.maxRetained ?? MAX_RETAINED_UNWINDOWED;
	const progressEvery = options.progressEveryBytes ?? 1 << 20;

	const router = new TimelineRouter();
	const stats = new StatsAccumulator();
	const retained: LocationFix[] = [];
	const warnings: string[] = [];

	let bytesRead = 0;
	let reportedAt = 0;
	let truncated = false;

	for await (const item of scanJsonItems(stream, {
		keys: TIMELINE_KEYS,
		onChunk: (bytes) => {
			bytesRead = bytes;
			if (options.onProgress && bytes - reportedAt >= progressEvery) {
				reportedAt = bytes;
				options.onProgress({ bytesRead: bytes, fixes: retained.length });
			}
		}
	})) {
		const parsed = router.route(item);
		stats.addSkipped(parsed.skipped);
		for (const fix of parsed.fixes) {
			stats.add(fix);
			if (claims.length > 0 && !overlaps(fix, claims, span)) continue;
			if (retained.length >= maxRetained) {
				truncated = true;
				continue;
			}
			retained.push(fix);
		}
	}

	if (router.format === null) {
		const code = router.sawKnownShape ? 'no_fixes' : 'unsupported_format';
		throw new IngestError(code, ingestErrors[code]);
	}

	const windowed =
		claims.length > 0
			? windowFixes(
					retained,
					options.claims ?? [],
					options.windowHours ?? SEARCH_WINDOW_H,
					options.maxFixes ?? MAX_FIXES
				)
			: { kept: dedupeFixes(retained), total: retained.length, dropped: 0 };

	if (truncated) warnings.push(ingestWarnings.tooManyPoints(maxRetained));
	if (windowed.dropped > 0) {
		warnings.push(ingestWarnings.tooManyNearClaim(options.maxFixes ?? MAX_FIXES));
	}

	const finished = stats.finish(options.claims ?? [], windowed.kept.length, bytesRead);
	if (finished.claimedDaysMissing.length > 0) {
		warnings.push(ingestWarnings.missingDays(finished.claimedDaysMissing));
	}
	if (finished.skipped > 0) warnings.push(ingestWarnings.unreadableEntries(finished.skipped));

	return { fixes: windowed.kept, stats: finished, warnings, format: router.format };
}

function overlaps(fix: LocationFix, claims: number[], span: number): boolean {
	const start = Date.parse(fix.t);
	if (Number.isNaN(start)) return false;
	const end = fix.t_end ? Date.parse(fix.t_end) : start;
	const finish = Number.isNaN(end) ? start : end;
	return claims.some((claim) => start <= claim + span && finish >= claim - span);
}
