import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	server: {
		proxy: { '/api': 'http://localhost:8000' },
		// The changelog lives at the repository root, one level up; allow that one file.
		fs: { allow: ['.', '../CHANGELOG.md'] }
	},
	test: {
		include: ['src/**/*.{test,spec}.{js,ts}'],
		environment: 'node'
	}
});
