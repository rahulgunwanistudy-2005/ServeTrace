import { describe, expect, it } from 'vitest';

import type { DocumentExtraction, ExtractedAffidavit } from '$lib/api/client';
import {
	attemptsFrom,
	boxStyle,
	changedPages,
	describeAffidavit,
	flaggedKeys,
	isFlagged,
	mergeRetag,
	pageFor,
	retagPages,
	startReviewTimer,
	unresolved,
	valuesFrom
} from './review';

function found(over: Partial<ExtractedAffidavit['draft']> = {}, notes = [], pages = [0]) {
	return {
		draft: { field_confidence: {}, evidence_quotes: {}, evidence: {}, attempts: [], ...over },
		notes,
		pages
	} as ExtractedAffidavit;
}

function extraction(over: Partial<DocumentExtraction> = {}): DocumentExtraction {
	return {
		page_types: ['affidavit_of_service', 'affidavit_of_service'],
		affidavits: [found({ defendant_name: 'A' }, [], [0, 1])],
		notes: [],
		provider: 'none',
		source_sha256: '0'.repeat(64),
		n_pages: 2,
		has_text_layer: true,
		used_vision: false,
		previews: [],
		...over
	};
}

describe('flags', () => {
	it('flags a field read with confidence under 0.8, and not one at 0.8', () => {
		const f = found({ field_confidence: { served_time: 0.79, served_date: 0.8 } });
		expect(isFlagged(f, 'served_time')).toBe(true);
		expect(isFlagged(f, 'served_date')).toBe(false);
	});

	it('flags a field a validator noted, whatever its score', () => {
		const f = found({ field_confidence: { method: 0.99 } }, [
			{ field: 'method', level: 'warning', message: 'x' }
		] as never);
		expect(isFlagged(f, 'method')).toBe(true);
	});

	it('lists flagged fields in reading order, attempts last', () => {
		const f = found({
			field_confidence: { mailing_date: 0.2, index_number: 0.1, 'attempts[0]': 0.3 },
			attempts: [{ at_date: '2025-01-01' }]
		});
		expect(flaggedKeys(f)).toEqual(['index_number', 'mailing_date', 'attempts[0]']);
	});

	it('a field without a score is not flagged: an empty manual form blocks nothing', () => {
		expect(flaggedKeys(found())).toEqual([]);
		expect(flaggedKeys(null)).toEqual([]);
	});

	it('confirm stays closed until every flag is accepted or changed', () => {
		expect(unresolved(['a', 'b'], new Set(['a']))).toEqual(['b']);
		expect(unresolved(['a', 'b'], new Set(['a', 'b']))).toEqual([]);
	});
});

describe('values', () => {
	it('fills date and time from the instant in New York time, not the browser zone', () => {
		const values = valuesFrom(found({ served_at: '2025-06-12T23:42:00Z' }).draft);
		expect(values.served_date).toBe('2025-06-12');
		expect(values.served_time).toBe('19:42');
		expect(values.method).toBe('unknown');
	});

	it('keeps the printed date and time when the reader gave them', () => {
		const values = valuesFrom(
			found({ served_date: '2025-06-12', served_time: '07:42', served_at: '2025-06-12T11:42:00Z' })
				.draft
		);
		expect(values.served_time).toBe('07:42');
	});

	it('reads attempts, and an unknown outcome becomes other', () => {
		const attempts = attemptsFrom(
			found({
				attempts: [
					{ at_date: '2025-01-02', at_time: '10:00', address: '1 Main St', outcome: 'not_home' },
					{ at: '2025-01-03T15:00:00Z', outcome: 'knocked' }
				]
			}).draft
		);
		expect(attempts[0]).toEqual({
			date: '2025-01-02',
			time: '10:00',
			address: '1 Main St',
			outcome: 'not_home'
		});
		expect(attempts[1]).toMatchObject({ date: '2025-01-03', time: '10:00', outcome: 'other' });
	});
});

describe('the page viewer', () => {
	it('goes to the evidence page, else the affidavit first page', () => {
		const f = found({ evidence: { served_address: { quote: 'x', page: 1, bbox: null } } }, [], [3, 4]);
		expect(pageFor(f, 'served_address')).toBe(1);
		expect(pageFor(f, 'court')).toBe(3);
	});

	it('draws the box as percentages of the page, padded and clamped', () => {
		const box = boxStyle([61.2, 79.2, 122.4, 158.4], { width: 612, height: 792 }, 0);
		expect(box).toEqual({ left: 10, top: 10, width: 10, height: 10 });
		const edge = boxStyle([0, 0, 612, 10], { width: 612, height: 792 });
		expect(edge?.left).toBe(0);
		expect(edge?.width).toBe(100);
		expect(boxStyle([1, 2], { width: 612, height: 792 })).toBeNull();
	});

	it('names an affidavit by its pages, one-based', () => {
		expect(describeAffidavit(found({ defendant_name: 'Lin' }, [], [3, 4])).pages).toBe('4–5');
		expect(describeAffidavit(found({}, [], [0])).pages).toBe('1');
	});
});

describe('re-tagging', () => {
	it('finds the pages whose label changed', () => {
		expect(
			changedPages(['other', 'affidavit_of_service', 'judgment'], ['other', 'other', 'judgment'])
		).toEqual([1]);
	});

	it('re-reads the whole affidavit a changed page belonged to', () => {
		expect(retagPages(extraction(), [1])).toEqual([0, 1]);
	});

	it('shrinks an affidavit rather than losing it', () => {
		const current = extraction();
		const reread = extraction({
			page_types: ['affidavit_of_service', 'other'],
			affidavits: [found({ defendant_name: 'A again' }, [], [0])]
		});
		const merged = mergeRetag(current, reread, retagPages(current, [1]));
		expect(merged.page_types).toEqual(['affidavit_of_service', 'other']);
		expect(merged.affidavits?.map((a) => a.pages)).toEqual([[0]]);
		expect(merged.affidavits?.[0]?.draft.defendant_name).toBe('A again');
	});

	it('keeps an affidavit nobody touched exactly as it was', () => {
		const current = extraction({
			page_types: ['affidavit_of_service', 'other', 'other'],
			n_pages: 3,
			affidavits: [found({ defendant_name: 'kept' }, [], [0])]
		});
		const reread = extraction({
			page_types: ['affidavit_of_service', 'other', 'affidavit_of_service'],
			n_pages: 3,
			affidavits: [found({ defendant_name: 'new' }, [], [2])]
		});
		const merged = mergeRetag(current, reread, retagPages(current, [2]));
		expect(merged.affidavits?.map((a) => a.draft.defendant_name)).toEqual(['kept', 'new']);
	});

	it('keeps the judgment date unless a judgment page was re-tagged', () => {
		const current = extraction({ judgment_entry_date: '2025-08-20' });
		const reread = extraction({ judgment_entry_date: null });
		expect(mergeRetag(current, reread, [1]).judgment_entry_date).toBe('2025-08-20');
	});
});

describe('the review timer', () => {
	it('logs seconds to confirm, once', () => {
		let t = 1000;
		const lines: string[] = [];
		const timer = startReviewTimer(
			() => t,
			(line) => lines.push(line)
		);
		t = 64_250;
		expect(timer.stop('maria')).toBe(63.3);
		timer.stop('maria');
		expect(lines).toEqual(['[review-timer] maria: 63.3s to confirm']);
	});
});
