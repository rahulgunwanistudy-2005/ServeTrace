/** Manual entries: "I was at work from 8:00 to 20:00 at <address>". Bible §13. Session 2. */

import type { ParseResult } from '../types';

export type ManualEntry = {
	date: string;
	from: string;
	to: string;
	address: string;
};

export function parseManual(_entries: ManualEntry[]): ParseResult {
	throw new Error('Not implemented until session 2');
}
