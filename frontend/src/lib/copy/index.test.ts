import { describe, expect, it } from 'vitest';

import { DEFAULT_LOCALE, isLocale, resolveLocale, t, translate } from './index';

describe('choosing a locale', () => {
	it('takes ?lang= first, then the stored choice, then English', () => {
		expect(resolveLocale('?lang=en', 'xx')).toBe('en');
		expect(resolveLocale('', 'en')).toBe('en');
		expect(resolveLocale('', null)).toBe(DEFAULT_LOCALE);
	});

	it('never picks a locale that is not registered', () => {
		expect(resolveLocale('?lang=es', 'fr')).toBe('en');
		expect(isLocale('es')).toBe(false);
		expect(isLocale('constructor')).toBe(false);
	});
});

describe('reading a string', () => {
	it('reads plain strings and calls templates with their arguments', () => {
		expect(t('nav.methodology')).toBe('Methodology');
		expect(t('common.version', '1.1.0')).toBe('Version 1.1.0');
	});

	it('refuses a key that does not exist rather than showing a blank', () => {
		expect(() => translate('en', 'nav.nothing')).toThrow();
		expect(() => translate('en', 'methodology')).toThrow();
	});
});

/**
 * Hard-coded copy. Build prompt §9: user-facing text in routes and shared UI comes from
 * `$copy`, so a second locale is a file, not a hunt. Markup text between tags and the
 * text attributes people read (aria-label, title, placeholder, alt) are scanned after
 * scripts, styles and comments are removed. The allowlist is for text that is not
 * language: names, symbols, units.
 */
const SOURCES = import.meta.glob(['/src/routes/**/*.svelte', '/src/lib/ui/**/*.svelte'], {
	query: '?raw',
	import: 'default',
	eager: true
}) as Record<string, string>;
const ALLOWED = new Set<string>(['ServeTrace', 'CPLR', 'km/h', 'PDF', 'CSV']);

function hardCoded(source: string): string[] {
	const markup = source
		.replace(/<script[\s\S]*?<\/script>/g, '')
		.replace(/<style[\s\S]*?<\/style>/g, '')
		.replace(/<!--[\s\S]*?-->/g, '');
	const text = [...markup.matchAll(/>([^<>{}]*)</g)].map((m) => m[1]!.trim());
	const attrs = [
		...markup.matchAll(/\b(?:aria-label|title|placeholder|alt)="([^"{}]*)"/g)
	].map((m) => m[1]!.trim());
	return [...text, ...attrs].filter((s) => /[A-Za-z]{2,}/.test(s) && !ALLOWED.has(s));
}

describe('no hard-coded copy', () => {
	it('keeps every user-facing string in routes and shared UI in $copy', () => {
		const files = Object.entries(SOURCES);
		expect(files.length).toBeGreaterThan(20);
		const found = files.flatMap(([file, source]) => hardCoded(source).map((text) => `${file}: ${text}`));
		expect(found).toEqual([]);
	});

	it('would catch one', () => {
		expect(hardCoded('<script>const a = "x";</script><p>Hello there</p><i aria-label="Close it"></i>')).toEqual([
			'Hello there',
			'Close it'
		]);
		expect(hardCoded('<p>{copy.title}</p><span>ServeTrace</span>')).toEqual([]);
	});
});
