/**
 * The one piece of real state in ServeTrace.
 *
 * Everything else in this product is a pure function of its input: you give the engine an
 * affidavit and some points and it answers, and nothing is remembered. A three-step wizard
 * cannot work that way — step 3 has to know what you did in step 1 — so this is where the
 * case lives while you are filling it in.
 *
 * ## Two promises it has to keep
 *
 * **It never loses your work to a back button.** The wizard's steps read and write this
 * store rather than their own local state, so going back to step 1 and forward again finds
 * everything where it was. That is the whole reason it exists.
 *
 * **It never saves anything you did not ask it to.** Bible §16 and the privacy page both
 * promise there is no account and nothing stored on a server; that promise is cheap to
 * keep and easy to quietly break on the *client*. So: in memory by default, IndexedDB only
 * after an explicit tick, and a clear that really clears. `persisted` being false has to be
 * the path that works, not the degraded one.
 */

import { browser } from '$app/environment';

import type { AnalyzeRequest, CaseAnalysis, ExtractionResult } from '$lib/api/client';
import type { LocationFix } from '$lib/ingest/types';

export type Affidavit = AnalyzeRequest['affidavit'];
export type HouseholdMember = NonNullable<AnalyzeRequest['household']>[number];

/** What the ingest step learned, kept so step 2 can be revisited without re-reading a file. */
export type IngestSummary = {
	source: 'timeline' | 'statement' | 'manual';
	total: number;
	kept: number;
	sent: number;
	daysCovered: string[];
	claimedDaysMissing: string[];
	warnings: string[];
};

const DB_NAME = 'servetrace';
const DB_VERSION = 1;
const STORE = 'case';
const KEY = 'current';

/** Everything worth carrying between steps, and nothing that can be recomputed. */
type Snapshot = {
	extraction: ExtractionResult | null;
	affidavit: Affidavit | null;
	confirmed: boolean;
	fixes: LocationFix[];
	ingest: IngestSummary | null;
	household: HouseholdMember[];
	knowledgeDate: string | null;
	judgmentDate: string | null;
	persisted: boolean;
};

function empty(): Snapshot {
	return {
		extraction: null,
		affidavit: null,
		confirmed: false,
		fixes: [],
		ingest: null,
		household: [],
		knowledgeDate: null,
		judgmentDate: null,
		persisted: false
	};
}

class CaseStore {
	extraction = $state<ExtractionResult | null>(null);
	affidavit = $state<Affidavit | null>(null);
	/** The tick in step 1. `/api/analyze` refuses an affidavit without it (bible §10). */
	confirmed = $state(false);
	fixes = $state<LocationFix[]>([]);
	ingest = $state<IngestSummary | null>(null);
	household = $state<HouseholdMember[]>([]);
	knowledgeDate = $state<string | null>(null);
	judgmentDate = $state<string | null>(null);
	/** Set by the tick in step 1. Nothing touches IndexedDB while this is false. */
	persisted = $state(false);

	/** The result, once there is one. Held here so `/result` survives a client-side nav. */
	analysis = $state<CaseAnalysis | null>(null);
	/** True when the case was loaded from `/demo` rather than filled in. */
	isDemo = $state(false);

	/** Step 1 is done when there is an affidavit and the person has said it matches. */
	get hasAffidavit(): boolean {
		return this.affidavit !== null && this.confirmed;
	}

	get hasFixes(): boolean {
		return this.fixes.length > 0;
	}

	/** What `/result` needs before it can show anything. */
	get isAnalysable(): boolean {
		return this.hasAffidavit && this.hasFixes;
	}

	toRequest(): AnalyzeRequest {
		if (!this.affidavit) throw new Error('no affidavit');
		return {
			affidavit: { ...this.affidavit, user_confirmed: this.confirmed },
			fixes: this.fixes,
			household: this.household,
			knowledge_date: this.knowledgeDate,
			judgment_entry_date: this.judgmentDate
		};
	}

	load(snapshot: Partial<Snapshot>): void {
		const next = { ...empty(), ...snapshot };
		this.extraction = next.extraction;
		this.affidavit = next.affidavit;
		this.confirmed = next.confirmed;
		this.fixes = next.fixes;
		this.ingest = next.ingest;
		this.household = next.household;
		this.knowledgeDate = next.knowledgeDate;
		this.judgmentDate = next.judgmentDate;
		this.persisted = next.persisted;
	}

	snapshot(): Snapshot {
		return {
			extraction: this.extraction,
			affidavit: this.affidavit,
			confirmed: this.confirmed,
			fixes: this.fixes,
			ingest: this.ingest,
			household: this.household,
			knowledgeDate: this.knowledgeDate,
			judgmentDate: this.judgmentDate,
			persisted: this.persisted
		};
	}

	reset(): void {
		this.load(empty());
		this.analysis = null;
		this.isDemo = false;
		void forget();
	}
}

export const caseStore = new CaseStore();

/**
 * IndexedDB, wrapped so a caller never has to think about it.
 *
 * Every function here resolves rather than rejects. Storage can be absent, blocked, full,
 * or refused in a private window, and none of those are reasons to stop somebody filling
 * in a court form — they are reasons to stop offering to save. A failure to persist is
 * reported by `persisted` going false, never by an exception reaching the wizard.
 */
function open(): Promise<IDBDatabase | null> {
	if (!browser || typeof indexedDB === 'undefined') return Promise.resolve(null);
	return new Promise((resolve) => {
		let request: IDBOpenDBRequest;
		try {
			request = indexedDB.open(DB_NAME, DB_VERSION);
		} catch {
			resolve(null);
			return;
		}
		request.onupgradeneeded = () => {
			if (!request.result.objectStoreNames.contains(STORE)) {
				request.result.createObjectStore(STORE);
			}
		};
		request.onsuccess = () => resolve(request.result);
		request.onerror = () => resolve(null);
		request.onblocked = () => resolve(null);
	});
}

export async function save(): Promise<boolean> {
	if (!caseStore.persisted) return false;
	const db = await open();
	if (!db) return false;
	return new Promise((resolve) => {
		try {
			const tx = db.transaction(STORE, 'readwrite');
			// `$state` proxies are not structured-cloneable, so the snapshot goes through
			// JSON. It is all plain data by construction, and this is the one place that
			// assumption is load-bearing enough to say out loud.
			tx.objectStore(STORE).put(JSON.parse(JSON.stringify(caseStore.snapshot())), KEY);
			tx.oncomplete = () => {
				db.close();
				resolve(true);
			};
			tx.onerror = () => {
				db.close();
				resolve(false);
			};
		} catch {
			db.close();
			resolve(false);
		}
	});
}

export async function restore(): Promise<boolean> {
	const db = await open();
	if (!db) return false;
	return new Promise((resolve) => {
		try {
			const tx = db.transaction(STORE, 'readonly');
			const request = tx.objectStore(STORE).get(KEY);
			request.onsuccess = () => {
				const value = request.result as Snapshot | undefined;
				if (value) caseStore.load(value);
				db.close();
				resolve(Boolean(value));
			};
			request.onerror = () => {
				db.close();
				resolve(false);
			};
		} catch {
			db.close();
			resolve(false);
		}
	});
}

export async function forget(): Promise<void> {
	const db = await open();
	if (!db) return;
	try {
		const tx = db.transaction(STORE, 'readwrite');
		tx.objectStore(STORE).delete(KEY);
		tx.oncomplete = () => db.close();
		tx.onerror = () => db.close();
	} catch {
		db.close();
	}
}
