/**
 * The part of papaparse ServeTrace uses.
 *
 * papaparse ships no types of its own and `@types/papaparse` would be a dependency the
 * bible (§8) does not list, so the surface we actually rely on is declared here instead.
 * It is deliberately narrow: if a future change reaches for a papaparse feature that is
 * not in this file, that is a decision to take on purpose rather than by autocomplete.
 */
declare module 'papaparse' {
	export type ParseError = {
		type: string;
		code: string;
		message: string;
		row?: number;
	};

	export type ParseResult<T> = {
		data: T[];
		errors: ParseError[];
		meta: { fields?: string[]; delimiter: string; aborted: boolean; truncated: boolean };
	};

	export type ParseConfig = {
		header?: boolean;
		skipEmptyLines?: boolean | 'greedy';
		delimiter?: string;
		transformHeader?: (header: string, index: number) => string;
		preview?: number;
	};

	export function parse<T = Record<string, string>>(
		input: string,
		config?: ParseConfig
	): ParseResult<T>;

	const Papa: { parse: typeof parse };
	export default Papa;
}
