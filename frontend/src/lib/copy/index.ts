/**
 * Locale plumbing. Build prompt §9. English is the only locale, and nothing in v1.1 is
 * translated: this is the seam a second language would plug into, kept honest by tests.
 *
 * - `locales` is the registry. A second locale is a second module with the same shape as
 *   `en.ts`; `satisfies Record<…, Copy>` makes the compiler hold it to every key.
 * - `t(key, ...args)` reads a string by dotted key, calling it with `args` when the entry
 *   is a function (`methodology.usage`, say). `CopyKey` is the union of every such key, so
 *   a typo is a type error rather than a blank on screen.
 * - `resolveLocale` picks the locale: `?lang=` first, then the stored preference, then
 *   English. Anything not registered falls through to English.
 *
 * Components still import `$copy/en` directly today; that keeps the change in v1.1 small
 * and reviewable. See docs/I18N.md for why legal-facing copy needs review by a qualified
 * native speaker before any second locale ships.
 */

import * as en from './en';

export type Copy = typeof en;

export const locales = { en } as const satisfies Record<string, Copy>;
export type Locale = keyof typeof locales;
export const DEFAULT_LOCALE: Locale = 'en';
export const LOCALE_STORAGE_KEY = 'servetrace.locale';

type Leaf = string | ((...args: never[]) => string);

/** Dotted keys down to two levels, which is as deep as `en.ts` nests a string. */
type KeysOf<T, Prefix extends string> = {
	[K in keyof T & string]: T[K] extends Leaf
		? `${Prefix}${K}`
		: T[K] extends readonly unknown[]
			? never
			: T[K] extends object
				? { [J in keyof T[K] & string]: T[K][J] extends Leaf ? `${Prefix}${K}.${J}` : never }[keyof T[K] & string]
				: never;
}[keyof T & string];

export type CopyKey = KeysOf<Copy, ''>;

type At<T, K extends string> = K extends `${infer Head}.${infer Rest}`
	? Head extends keyof T
		? At<T[Head], Rest>
		: never
	: K extends keyof T
		? T[K]
		: never;

export type ArgsOf<K extends CopyKey> = At<Copy, K> extends (...args: infer A) => string ? A : [];

export function isLocale(value: string | null | undefined): value is Locale {
	return !!value && Object.prototype.hasOwnProperty.call(locales, value);
}

/** `?lang=` beats the stored preference, which beats the default. Pure, so it is testable. */
export function resolveLocale(search: string, stored: string | null): Locale {
	const asked = new URLSearchParams(search).get('lang');
	if (isLocale(asked)) return asked;
	if (isLocale(stored)) return stored;
	return DEFAULT_LOCALE;
}

/** The locale for this browser. Storage can be missing or throw (private windows); that is English. */
export function currentLocale(): Locale {
	if (typeof window === 'undefined') return DEFAULT_LOCALE;
	let stored: string | null = null;
	try {
		stored = window.localStorage.getItem(LOCALE_STORAGE_KEY);
	} catch {
		stored = null;
	}
	return resolveLocale(window.location.search, stored);
}

export function rememberLocale(locale: Locale): void {
	try {
		window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
	} catch {
		// A preference that cannot be kept is asked again next time; nothing else depends on it.
	}
}

export function t<K extends CopyKey>(key: K, ...args: ArgsOf<K>): string;
export function t(key: string, ...args: unknown[]): string {
	return translate(DEFAULT_LOCALE, key, args);
}

export function translate(locale: Locale, key: string, args: unknown[] = []): string {
	let node: unknown = locales[locale];
	for (const part of key.split('.')) {
		if (node === null || typeof node !== 'object' || !(part in node)) {
			throw new Error(`no copy for "${key}" in ${locale}`);
		}
		node = (node as Record<string, unknown>)[part];
	}
	if (typeof node === 'function') return String((node as (...a: unknown[]) => unknown)(...args));
	if (typeof node === 'string') return node;
	throw new Error(`"${key}" in ${locale} is not a string`);
}
