import { dev } from '$app/environment';
import { error } from '@sveltejs/kit';

/**
 * The ingest workbench. Development only.
 *
 * adapter-static prerenders every page it is given, so "not in the production build" has
 * to be said twice: this page opts out of prerendering, and refuses to render outside
 * `npm run dev`. The nav link is likewise only there in development. What ships is an
 * inert route, not a hidden page someone can find by typing the URL.
 */
export const prerender = false;

export function load(): void {
	if (!dev) error(404, 'Not found');
}
