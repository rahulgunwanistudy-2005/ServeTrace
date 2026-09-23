/**
 * The committed demo cases from `fixtures/demo_cases/`, for tests. Never imported by the
 * app, so none of this reaches the bundle.
 *
 * These are the S1 generator's own output: one synthetic day rendered as an Android
 * export, as an iOS export, as a card statement, and as the list of fixes the generator
 * knows it put there. That last file is ground truth that owes nothing to these parsers,
 * which is what makes it worth testing against.
 *
 * They are loaded through Vite's `?raw` glob rather than `node:fs` because the frontend
 * has no Node type definitions and adding them would be a dependency the bible (§8) does
 * not list.
 */

import type { LocationFix } from './types';

const RAW_JSON = import.meta.glob('../../../../fixtures/demo_cases/*/*.json', {
	query: '?raw',
	import: 'default',
	eager: true
}) as Record<string, string>;

const RAW_CSV = import.meta.glob('../../../../fixtures/demo_cases/*/*.csv', {
	query: '?raw',
	import: 'default',
	eager: true
}) as Record<string, string>;

export const DEMO_CASES = [
	'maria_contradicted',
	'james_consistent',
	'lin_affix_mail_diligence'
] as const;

export type DemoCase = (typeof DEMO_CASES)[number];

export type GroundTruth = {
	case_id: string;
	claimed_at: string;
	claimed_address: string;
	dates_covered: string[];
	n_fixes: number;
	true_tier: string;
	method: string;
};

function raw(source: Record<string, string>, name: DemoCase, file: string): string {
	const suffix = `/${name}/${file}`;
	const key = Object.keys(source).find((path) => path.endsWith(suffix));
	if (key === undefined) throw new Error(`demo fixture missing: ${suffix}`);
	return source[key] as string;
}

export function demoText(name: DemoCase, file: string): string {
	return file.endsWith('.csv') ? raw(RAW_CSV, name, file) : raw(RAW_JSON, name, file);
}

export function demoJson<T>(name: DemoCase, file: string): T {
	return JSON.parse(demoText(name, file)) as T;
}

export function groundTruth(name: DemoCase): GroundTruth {
	return demoJson<GroundTruth>(name, 'ground_truth.json');
}

export function expectedFixes(name: DemoCase): LocationFix[] {
	return demoJson<LocationFix[]>(name, 'fixes.json');
}
