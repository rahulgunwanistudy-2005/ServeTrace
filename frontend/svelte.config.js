import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
export default {
	preprocess: vitePreprocess(),
	kit: {
		// FastAPI serves this build directory at / (bible §7: one deployable).
		adapter: adapter({ pages: 'build', assets: 'build', fallback: '200.html', strict: false }),
		alias: { $copy: 'src/lib/copy' },

		// The page's Content-Security-Policy lives here rather than in a server header,
		// because SvelteKit emits one inline bootstrap script per page and `mode: 'hash'`
		// hashes whatever it actually emitted. A policy written by hand on the server
		// would have to be kept in step with the bundler by hand, and the day it fell out
		// of step is the day it either broke the app or stopped enforcing anything.
		//
		// The server adds the headers a <meta> tag cannot express — frame-ancestors, HSTS
		// — and a far stricter policy for the API, which loads nothing at all.
		csp: {
			mode: 'hash',
			directives: {
				'default-src': ['self'],
				'script-src': ['self'],
				// MapLibre and Svelte both set element styles at runtime. Most of that is
				// CSSOM and outside CSP entirely, but enough of it lands as a style
				// attribute that removing this blanks the map. Style injection is a far
				// weaker vector than script injection, and script-src stays strict.
				'style-src': ['self', 'unsafe-inline'],
				// data: is the evidence packet reading the map back off the canvas;
				// tiles.openfreemap.org is the basemap's raster and sprite layers.
				'img-src': ['self', 'data:', 'blob:', 'https://tiles.openfreemap.org'],
				'font-src': ['self'],
				// Same-origin for the API; OpenFreeMap for the style, vector tiles,
				// glyphs and sprites. Everything the style file names is on that one host.
				'connect-src': ['self', 'https://tiles.openfreemap.org'],
				// MapLibre builds its tile worker from a blob URL. Without this the map
				// renders nothing and says nothing.
				'worker-src': ['self', 'blob:'],
				'child-src': ['self', 'blob:'],
				'frame-ancestors': ['none'],
				'base-uri': ['self'],
				'form-action': ['self'],
				'object-src': ['none']
			}
		}
	}
};
