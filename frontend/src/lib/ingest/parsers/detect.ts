/**
 * Which export is this? Answered by what the file turns out to contain, not by sniffing.
 *
 * The scanner tags every item with the array it came from, so the two shapes separate
 * themselves: items from `semanticSegments` or `rawSignals` are an Android export, items
 * from a top-level array are an iOS one. Nothing has to be decided before reading, which
 * matters because the deciding evidence can be megabytes into the file.
 */

import type { ScannedItem } from '../streamJson';
import type { IngestFormat } from '../types';
import { androidRawSignalToFixes, androidSegmentToFixes } from './googleAndroid';
import { iosItemToFixes } from './googleIos';
import { EMPTY_ITEMS, type ParsedItems } from './shared';

/** The arrays worth reading. Everything else in the document is stepped over. */
export const TIMELINE_KEYS = ['', 'semanticSegments', 'rawSignals'] as const;

export class TimelineRouter {
	/** Set by the first item that actually yields a fix, so a stray array cannot claim it. */
	format: IngestFormat | null = null;
	/** True once something recognisably Timeline-shaped has been seen, readable or not. */
	sawKnownShape = false;

	route(item: ScannedItem): ParsedItems {
		const parsed = this.parse(item);
		if (parsed.fixes.length > 0 || parsed.skipped > 0) this.sawKnownShape = true;
		if (parsed.fixes.length > 0 && this.format === null) {
			this.format = item.key === '' ? 'google_ios' : 'google_android';
		}
		return parsed;
	}

	private parse(item: ScannedItem): ParsedItems {
		switch (item.key) {
			case 'semanticSegments':
				return androidSegmentToFixes(item.value);
			case 'rawSignals':
				return androidRawSignalToFixes(item.value);
			case '':
				return iosItemToFixes(item.value);
			default:
				return EMPTY_ITEMS;
		}
	}
}
