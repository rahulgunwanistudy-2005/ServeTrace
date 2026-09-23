import { describe, expect, it } from 'vitest';

import { demoText } from '../demoFixtures';
import { parseCardCsv, readCsvHeaders, TRANSACTION_ACCURACY_M } from './cardCsv';

const COLUMNS = { date: 'Date', time: 'Time', merchant: 'Description', address: 'Address' };

describe('a real statement from the fixtures', () => {
	const text = demoText('maria_contradicted', 'transactions.csv');

	it('offers its columns for mapping', () => {
		expect(readCsvHeaders(text)).toEqual(['Date', 'Time', 'Description', 'Address', 'Amount']);
	});

	it('reads every row that has a date, a time and an address', () => {
		const result = parseCardCsv(text, COLUMNS);
		expect(result.pending).toHaveLength(3);
		expect(result.skipped).toBe(0);
	});

	it('places each purchase at the New York time printed on the statement', () => {
		const result = parseCardCsv(text, COLUMNS);
		// The fixture's second row is 08:37 on 12 June, which is 12:37 UTC in summer.
		expect(result.pending[1]?.t).toBe('2025-06-12T12:37:00.000Z');
	});

	it('marks a purchase as the coarse location it is', () => {
		const result = parseCardCsv(text, COLUMNS);
		expect(result.pending[0]).toMatchObject({
			kind: 'transaction',
			accuracy_m: TRANSACTION_ACCURACY_M,
			source: 'card_csv'
		});
	});

	it('never reads the amount column', () => {
		// Bible §13: only the address is ever sent. A value that is never read cannot leak,
		// so this asserts on the whole parsed record rather than on what gets posted later.
		const serialised = JSON.stringify(parseCardCsv(text, COLUMNS).pending);
		expect(serialised).not.toContain('26.95');
		expect(serialised).not.toContain('Amount');
	});
});

describe('column mapping', () => {
	const text = 'when,at,shop,where\n2025-06-12,19:42,Corner Deli,"2100 White Plains Road, Bronx"\n';

	it('uses whatever the columns happen to be called', () => {
		const result = parseCardCsv(text, { date: 'when', time: 'at', merchant: 'shop', address: 'where' });
		expect(result.pending[0]).toMatchObject({
			address: '2100 White Plains Road, Bronx',
			label: 'Corner Deli'
		});
	});

	it('says plainly that nothing can be used without an address column', () => {
		const result = parseCardCsv(text, { date: 'when', time: 'at' });
		expect(result.pending).toEqual([]);
		expect(result.warnings[0]).toMatch(/address/);
	});
});

describe('rows that cannot be placed', () => {
	it('leaves out a row with no time rather than inventing one', () => {
		// A purchase with no time places someone on a day. The claim is an hour. Filling in
		// noon would be making evidence up.
		const text = 'Date,Time,Address\n2025-06-12,,"2100 White Plains Road, Bronx"\n';
		const result = parseCardCsv(text, { date: 'Date', time: 'Time', address: 'Address' });

		expect(result.pending).toEqual([]);
		expect(result.skipped).toBe(1);
		expect(result.warnings.join(' ')).toMatch(/1 row/);
	});

	it('leaves out a row with no address', () => {
		const text = 'Date,Time,Address\n2025-06-12,19:42,\n';
		const result = parseCardCsv(text, { date: 'Date', time: 'Time', address: 'Address' });
		expect(result.skipped).toBe(1);
	});

	it('leaves out a row whose date makes no sense', () => {
		const text = 'Date,Time,Address\n12 June-ish,19:42,"2100 White Plains Road"\n';
		const result = parseCardCsv(text, { date: 'Date', time: 'Time', address: 'Address' });
		expect(result.skipped).toBe(1);
	});

	it('keeps the rows it can read when others fail', () => {
		const text =
			'Date,Time,Address\n2025-06-12,19:42,"2100 White Plains Road"\nnonsense,,,\n2025-06-12,20:10,"1400 Lexington Avenue"\n';
		const result = parseCardCsv(text, { date: 'Date', time: 'Time', address: 'Address' });
		expect(result.pending).toHaveLength(2);
	});
});

describe('times as people write them', () => {
	function timeOf(raw: string): string | undefined {
		const text = `Date,Time,Address\n2025-06-12,${raw},"2100 White Plains Road"\n`;
		return parseCardCsv(text, { date: 'Date', time: 'Time', address: 'Address' }).pending[0]?.t;
	}

	it('reads a 24-hour time', () => {
		expect(timeOf('19:42')).toBe('2025-06-12T23:42:00.000Z');
	});

	it('reads an evening time written with PM', () => {
		expect(timeOf('7:42 PM')).toBe('2025-06-12T23:42:00.000Z');
	});

	it('reads a morning time written with am', () => {
		expect(timeOf('8:05 am')).toBe('2025-06-12T12:05:00.000Z');
	});

	it('reads midnight written as 12:05 AM', () => {
		expect(timeOf('12:05 AM')).toBe('2025-06-12T04:05:00.000Z');
	});

	it('reads noon written as 12:30 p.m.', () => {
		expect(timeOf('12:30 p.m.')).toBe('2025-06-12T16:30:00.000Z');
	});
});

describe('the night the clocks change', () => {
	it('says which reading of an ambiguous time it used', () => {
		const text = 'Date,Time,Address\n2025-11-02,01:30,"2100 White Plains Road"\n';
		const result = parseCardCsv(text, { date: 'Date', time: 'Time', address: 'Address' });

		expect(result.pending[0]?.t).toBe('2025-11-02T05:30:00.000Z');
		expect(result.warnings.join(' ')).toMatch(/clocks change/);
	});
});

describe('an empty file', () => {
	it('produces nothing and does not throw', () => {
		expect(parseCardCsv('', COLUMNS).pending).toEqual([]);
	});

	it('produces nothing from a header row on its own', () => {
		expect(parseCardCsv('Date,Time,Address\n', COLUMNS).pending).toEqual([]);
	});
});
