import { describe, expect, it } from 'vitest';
import * as copy from './en';
import { LIMITATION_LINE, DRAFT_BANNER, errors, legalRefs, tiers } from './en';

/**
 * Every string this module exports, however deeply nested. The copy rules in bible §3 and
 * §6 apply to all of it, and a rule enforced on four sentences out of three hundred is not
 * enforced at all.
 */
function allStrings(value: unknown, out: string[] = []): string[] {
	if (typeof value === 'string') out.push(value);
	else if (Array.isArray(value)) for (const item of value) allStrings(item, out);
	else if (value && typeof value === 'object')
		for (const item of Object.values(value)) allStrings(item, out);
	return out;
}

/**
 * Everything ServeTrace says in its own voice.
 *
 * The source list on the Methodology page is excluded, and only the source list: those
 * are the verbatim titles of the articles bible §5 requires be cited, and a citation is
 * a quotation. Rewriting "5 key takeaways on sewer service" to satisfy a rule about what
 * *we* may say would be misquoting someone to look tidy.
 */
const { sources, ...methodologyInOurOwnVoice } = copy.methodology;
const EVERY_STRING = allStrings({ ...copy, methodology: methodologyInOurOwnVoice });

const DENIED = /\b(never|not|no|nothing|cannot|won't|does ?n[o']t)\b/i;

/**
 * Assert a pattern only ever appears inside a sentence that denies it.
 *
 * Bible §6 forbids ServeTrace from saying anyone lied — and requires it to say, in as
 * many words, that it does not. "It never says anyone lied" has to pass and "the server
 * lied" has to fail, so what a rule reads is the sentence, not the phrase.
 */
function onlyEverDenied(pattern: RegExp): void {
	for (const text of EVERY_STRING) {
		for (const sentence of text.split(/(?<=[.!?])\s+/)) {
			if (pattern.test(sentence)) expect(sentence, text).toMatch(DENIED);
		}
	}
}

describe('copy discipline', () => {
	it('has a headline for every tier in the contract', () => {
		expect(Object.keys(tiers).sort()).toEqual([
			'consistent',
			'contradicted',
			'inconclusive',
			'no_data'
		]);
	});

	it('never accuses anyone of lying or fraud, anywhere in the module', () => {
		// Bible §6: ServeTrace says data conflicts. It does not say anyone lied.
		//
		// One phrase is allowed through, and only one: bible §2 asks for the card-fraud
		// analogy by name, because that is where the technique comes from. It describes a
		// bank's own checks and never a person in the case, so it is carved out here
		// rather than by weakening the pattern — the next use of the word should have to
		// argue for itself too.
		const forbidden = /\b(lied|lying|fraudulent|perjury|criminal|sewer service)\b/i;
		onlyEverDenied(forbidden);
	});

	it('uses the word fraud only for the bank analogy bible §2 asks for by name', () => {
		// That analogy is where the technique comes from and is worth saying out loud. It
		// describes a bank's own checks; the word may never attach to anyone in the case.
		for (const text of EVERY_STRING) {
			for (const sentence of text.split(/(?<=[.!?])\s+/)) {
				if (/fraud/i.test(sentence)) expect(sentence).toMatch(/a bank\u2019s fraud checks/i);
			}
		}
	});

	it('never promises an outcome, anywhere in the module', () => {
		// Bible §3: no "you will win" prediction. The phrase is only forbidden as a
		// promise — "ServeTrace never predicts whether you will win" is the disclaimer
		// that same rule requires, so the sentence around the phrase is what decides.
		const promise = /\b(you will win|guaranteed|we will win|certain to|prove(s|n)? (that )?you)\b/i;
		onlyEverDenied(promise);
	});

	it('never offers legal advice in its own voice', () => {
		// Bible §3: no free-text legal advice. Copy may state what the law says and point
		// at the Help Center; it may not tell one person what to do about their case.
		const forbidden = /\byou should (file|sue|argue|claim|tell the (judge|court))\b/i;
		for (const text of EVERY_STRING) expect(text).not.toMatch(forbidden);
	});

	it('sweeps a meaningful amount of copy, so the rules above are not vacuous', () => {
		expect(EVERY_STRING.length).toBeGreaterThan(100);
	});

	it('cites every source bible §5 lists, as a title and a link and nothing else', () => {
		expect(sources.length).toBe(7);
		for (const source of sources) {
			expect(source.url).toMatch(/^https:\/\//);
			expect(source.title.length).toBeGreaterThan(10);
		}
	});

	it('names every legal reference the engine can attach to a finding', () => {
		// The engine emits L1..L4 on findings today and L5..L7 in documents and next-steps
		// copy. A finding whose L-id had no label would silently lose its citation.
		expect(Object.keys(legalRefs).sort()).toEqual(['L1', 'L2', 'L3', 'L4', 'L5', 'L6', 'L7']);
	});

	it('cites only provisions that bible §5 names', () => {
		const allowed = /CPLR 308\(1\)|CPLR 308\(2\)|CPLR 308\(4\)|CPLR 5015|CPLR 317|20-410|courts commonly expect/i;
		for (const label of Object.values(legalRefs)) expect(label).toMatch(allowed);
	});

	it('never invents a statute the bible does not encode', () => {
		// A hallucinated citation in a court document is the worst thing this product
		// could do, so the only CPLR sections that may appear anywhere are the four in §5.
		for (const text of EVERY_STRING) {
			for (const match of text.matchAll(/CPLR\s+(\d+)/gi)) {
				expect(['308', '5015', '317'], text).toContain(match[1]);
			}
		}
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
