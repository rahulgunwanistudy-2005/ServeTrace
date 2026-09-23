/**
 * Card or bank statement CSV. Bible §13. Session 2.
 *
 * Only the address column is ever sent for geocoding. Amounts never leave the device.
 */

import type { ParseResult } from '../types';

export type ColumnMap = {
	date: string;
	time?: string;
	merchant?: string;
	address?: string;
};

export function parseCardCsv(_text: string, _columns: ColumnMap): ParseResult {
	throw new Error('Not implemented until session 2');
}
