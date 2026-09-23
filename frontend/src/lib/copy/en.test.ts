import { describe, expect, it } from 'vitest';
import { LIMITATION_LINE, DRAFT_BANNER, errors, tiers } from './en';

describe('copy discipline', () => {
	it('has a headline for every tier in the contract', () => {
		expect(Object.keys(tiers).sort()).toEqual([
			'consistent',
			'contradicted',
			'inconclusive',
			'no_data'
		]);
	});

	it('never accuses anyone of lying or fraud', () => {
		// Bible §6: ServeTrace says data conflicts. It does not say anyone lied.
		const forbidden = /\b(lied|lying|fraud|fraudulent|perjury|criminal)\b/i;
		for (const [tier, text] of Object.entries(tiers)) {
			expect(text.headline, tier).not.toMatch(forbidden);
			expect(text.meaning, tier).not.toMatch(forbidden);
		}
	});

	it('never promises an outcome', () => {
		// Bible §3: no "you will win" prediction, anywhere.
		const forbidden = /\b(you will win|guaranteed|we will win|certain to)\b/i;
		const everything = [
			...Object.values(tiers).flatMap((t) => [t.headline, t.meaning]),
			...Object.values(errors)
		];
		for (const text of everything) expect(text).not.toMatch(forbidden);
	});

	it('keeps the limitation line intact', () => {
		expect(LIMITATION_LINE).toContain('not proof of where you were');
		expect(LIMITATION_LINE).toContain('A judge decides');
	});

	it('keeps the draft banner intact', () => {
		expect(DRAFT_BANNER).toContain('not legal advice');
	});

	it('has a message for every error code the backend can return', () => {
		for (const code of [
			'bad_input',
			'upload_too_large',
			'unsupported_file',
			'affidavit_not_confirmed',
			'extraction_unavailable',
			'upstream_error',
			'rate_limited',
			'invalid_request',
			'not_found',
			'internal_error'
		]) {
			expect(errors, code).toHaveProperty(code);
		}
	});
});
