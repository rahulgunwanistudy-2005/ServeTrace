import { dev } from '$app/environment';
import { error } from '@sveltejs/kit';

/**
 * The engine workbench. Development only.
 *
 * Runs a committed demo case through the real `POST /api/analyze` and renders the result
 * with the same components the result screen will use. It is the smoke test for the whole
 * slice — engine, route, generated types, client, components — in the one place where all
 * five are wired together.
 *
 * Gated the same way as `/dev/ingest`: adapter-static prerenders every page it is given,
 * so "not in the production build" is said twice. No prerender, and a load that refuses
 * outside `npm run dev`.
 */
export const prerender = false;

export function load(): void {
	if (!dev) error(404, 'Not found');
}
