import { beforeEach, describe, expect, it } from 'vitest';

import { caseStore, type Affidavit, type HouseholdMember } from './store.svelte';
import type { LocationFix } from '$lib/ingest/types';

/**
 * A minimal affidavit that satisfies the contract.
 *
 * Built rather than cast: `as never` type-checks at the assignment and then poisons every
 * read of the value downstream, which is how a test that passes can still fail the gate.
 */
function affidavit(overrides: Partial<Affidavit> = {}): Affidavit {
	return {
		index_number: null,
		court: null,
		plaintiff: null,
		defendant_name: 'A. Defendant',
		server_name: null,
		server_license: null,
		agency_license: null,
		method: '308_2',
		served_at: '2025-06-12T23:42:00Z',
		served_address: '2100 WHITE PLAINS ROAD, Bronx, NY 10462',
		served_location: { lat: 40.853454, lng: -73.867397 },
		recipient_name: null,
		recipient_relationship: null,
		recipient_description: null,
		attempts: [],
		mailing_date: null,
		mailing_address: null,
		proof_filed_date: null,
		source_sha256: '0'.repeat(64),
		field_confidence: {},
		user_confirmed: false,
		...overrides
	} as Affidavit;
}

function fix(): LocationFix {
	return {
		t: '2025-06-12T23:42:00Z',
		t_end: null,
		loc: { lat: 40.7, lng: -73.9 },
		accuracy_m: null,
		kind: 'manual',
		source: 'typed',
		label: null
	} as LocationFix;
}

function member(): HouseholdMember {
	return { label: 'Me', sex: null, age: 34, height_in: null, is_defendant: true } as HouseholdMember;
}

/**
 * The store's promises, not its plumbing.
 *
 * IndexedDB is absent under vitest's node environment, which is the point: every
 * persistence function has to resolve rather than throw when storage is unavailable,
 * because a browser in a private window behaves the same way and a person filling in a
 * court form must not hit an exception for it.
 */
describe('the case store', () => {
	beforeEach(() => {
		caseStore.reset();
	});

	it('starts empty and unanalysable', () => {
		expect(caseStore.affidavit).toBeNull();
		expect(caseStore.fixes).toEqual([]);
		expect(caseStore.hasAffidavit).toBe(false);
		expect(caseStore.isAnalysable).toBe(false);
	});

	it('does not persist unless asked', () => {
		// The privacy page promises nothing is stored by default, and this is the flag the
		// whole IndexedDB path is gated on.
		expect(caseStore.persisted).toBe(false);
	});

	it('needs both the affidavit and the tick before it counts as confirmed', () => {
		caseStore.affidavit = affidavit();
		expect(caseStore.hasAffidavit).toBe(false);
		caseStore.confirmed = true;
		expect(caseStore.hasAffidavit).toBe(true);
	});

	it('is analysable only with an affidavit and at least one point', () => {
		caseStore.affidavit = affidavit();
		caseStore.confirmed = true;
		expect(caseStore.isAnalysable).toBe(false);
		caseStore.fixes = [fix()];
		expect(caseStore.isAnalysable).toBe(true);
	});

	it('sends the tick as user_confirmed, which /api/analyze refuses to run without', () => {
		caseStore.affidavit = affidavit({ user_confirmed: false });
		caseStore.confirmed = true;
		expect(caseStore.toRequest().affidavit.user_confirmed).toBe(true);
	});

	it('refuses to build a request with no affidavit rather than sending a hollow one', () => {
		expect(() => caseStore.toRequest()).toThrow();
	});

	it('reset clears the analysis and the demo flag as well as the inputs', () => {
		caseStore.affidavit = affidavit();
		caseStore.confirmed = true;
		caseStore.fixes = [fix()];
		caseStore.analysis = { overall: 'contradicted' } as unknown as NonNullable<typeof caseStore.analysis>;
		caseStore.isDemo = true;

		caseStore.reset();

		expect(caseStore.affidavit).toBeNull();
		expect(caseStore.confirmed).toBe(false);
		expect(caseStore.fixes).toEqual([]);
		expect(caseStore.analysis).toBeNull();
		expect(caseStore.isDemo).toBe(false);
	});

	it('round-trips a snapshot, so a restored case is the case that was saved', () => {
		caseStore.affidavit = affidavit({ defendant_name: 'Maria' });
		caseStore.confirmed = true;
		caseStore.knowledgeDate = '2026-06-01';
		caseStore.household = [member()];

		const snapshot = caseStore.snapshot();
		caseStore.reset();
		caseStore.load(snapshot);

		expect(caseStore.affidavit?.defendant_name).toBe('Maria');
		expect(caseStore.confirmed).toBe(true);
		expect(caseStore.knowledgeDate).toBe('2026-06-01');
		expect(caseStore.household).toHaveLength(1);
	});

	it('a partial snapshot fills the rest with empty rather than leaving stale values', () => {
		caseStore.fixes = [fix()];
		caseStore.load({ knowledgeDate: '2026-01-01' });
		expect(caseStore.knowledgeDate).toBe('2026-01-01');
		expect(caseStore.fixes).toEqual([]);
	});
});

describe('persistence where there is no storage', () => {
	it('resolves rather than throwing when IndexedDB is absent', async () => {
		// vitest runs in node: there is no `indexedDB`, exactly as in a locked-down browser.
		const { save, restore, forget } = await import('./store.svelte');
		caseStore.persisted = true;
		await expect(save()).resolves.toBe(false);
		await expect(restore()).resolves.toBe(false);
		await expect(forget()).resolves.toBeUndefined();
		caseStore.persisted = false;
	});

	/**
	 * The gate, tested against a fake that records whether it was ever opened.
	 *
	 * This is the promise the privacy page makes, so "returns false" is not enough: the
	 * question is whether the tick being off means storage is never *touched*. A fake that
	 * counts `open` calls is the only way to tell those two apart.
	 */
	it('never opens storage at all while the tick is off', async () => {
		const { save } = await import('./store.svelte');
		let opened = 0;
		Object.defineProperty(globalThis, 'indexedDB', {
			configurable: true,
			value: {
				open: () => {
					opened += 1;
					return { onupgradeneeded: null, onsuccess: null, onerror: null, onblocked: null };
				}
			}
		});
		try {
			caseStore.persisted = false;
			await expect(save()).resolves.toBe(false);
			expect(opened).toBe(0);
		} finally {
			Reflect.deleteProperty(globalThis, 'indexedDB');
		}
	});
});
