import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
export default {
	preprocess: vitePreprocess(),
	kit: {
		// FastAPI serves this build directory at / (bible §7: one deployable).
		adapter: adapter({ pages: 'build', assets: 'build', fallback: '200.html', strict: false }),
		alias: { $copy: 'src/lib/copy' }
	}
};
