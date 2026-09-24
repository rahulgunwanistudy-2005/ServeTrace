/**
 * The three committed demo cases, for `/demo`.
 *
 * This is the first time fixture data reaches the production bundle, so it is worth being
 * explicit about what and why. Bible §16 wants a demo that never fails and §2 wants one
 * that works with the network off; the only way to have both is for the case to be in the
 * build rather than fetched. What ships is one affidavit, one set of already-windowed
 * location points, and one household roster per case — the inputs a person would have
 * spent ten minutes providing.
 *
 * **Lazily.** `import.meta.glob` without `eager` gives a loader per file, so each case is
 * its own chunk and the landing page carries none of them. Somebody who never opens the
 * demo never downloads it.
 *
 * `ingest/demoFixtures.ts` loads the same directory eagerly for tests and says it never
 * reaches the app. That stays true: this is a separate, narrower door, and it opens onto
 * three files per case rather than everything in the folder.
 */

import type { AnalyzeRequest } from '$lib/api/client';
import type { LocationFix } from '$lib/ingest/types';

export const DEMO_CASE_IDS = [
	'maria_contradicted',
	'james_consistent',
	'lin_affix_mail_diligence'
] as const;

export type DemoCaseId = (typeof DEMO_CASE_IDS)[number];

export type DemoCase = {
	id: DemoCaseId;
	affidavit: AnalyzeRequest['affidavit'];
	fixes: LocationFix[];
	household: NonNullable<AnalyzeRequest['household']>;
	knowledgeDate: string;
	judgmentDate: string;
};

const LOADERS = import.meta.glob('../../../../fixtures/demo_cases/*/*.json') as Record<
	string,
	() => Promise<{ default: unknown }>
>;

/**
 * The two dates the wizard asks for in step 3.
 *
 * They are not in the fixtures because the generator builds an affidavit, not a person's
 * recollection of when their account was frozen. They are here, beside the cases they
 * belong to, rather than inlined at the call site where they would read as magic numbers.
 */
const DATES: Record<DemoCaseId, { knowledge: string; judgment: string }> = {
	maria_contradicted: { knowledge: '2026-06-01', judgment: '2025-08-20' },
	james_consistent: { knowledge: '2026-05-14', judgment: '2025-09-02' },
	lin_affix_mail_diligence: { knowledge: '2026-07-09', judgment: '2025-10-15' }
};

function loader(id: DemoCaseId, file: string): () => Promise<{ default: unknown }> {
	const key = Object.keys(LOADERS).find((path) => path.endsWith(`/${id}/${file}`));
	// A missing fixture is a build-time mistake, not a runtime condition: the files are
	// committed and the ids are a literal union. Failing loudly here beats a demo case
	// that loads with no points and looks like an engine bug.
	if (!key) throw new Error(`demo fixture missing: ${id}/${file}`);
	return LOADERS[key] as () => Promise<{ default: unknown }>;
}

async function json<T>(id: DemoCaseId, file: string): Promise<T> {
	return (await loader(id, file)()).default as T;
}

export async function loadDemoCase(id: DemoCaseId): Promise<DemoCase> {
	const [affidavit, fixes, household] = await Promise.all([
		json<AnalyzeRequest['affidavit']>(id, 'affidavit.json'),
		json<LocationFix[]>(id, 'fixes.json'),
		json<NonNullable<AnalyzeRequest['household']>>(id, 'household.json')
	]);
	const dates = DATES[id];
	return {
		id,
		// The fixtures are written unconfirmed, because a generator cannot tick a box on
		// somebody's behalf. Loading a demo case *is* the tick: the person chose this case
		// the way a real user confirms their own details.
		affidavit: { ...affidavit, user_confirmed: true },
		fixes,
		household,
		knowledgeDate: dates.knowledge,
		judgmentDate: dates.judgment
	};
}
