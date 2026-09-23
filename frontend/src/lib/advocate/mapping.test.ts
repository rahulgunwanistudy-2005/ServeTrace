import { describe, expect, it } from 'vitest';
import { FIELDS, guessColumns, hasPlace, hasTime, isComplete, missingFields } from './mapping';

/**
 * The guesser only ever saves keystrokes: the server validates whatever mapping it is
 * handed, and every guess is shown to the user before anything is read. So what these
 * tests protect is not correctness of the answer but the shape of the mistake — a wrong
 * guess must be a visible, correctable one, and never a silent reinterpretation of a
 * column into a field that means something different.
 */

describe('guessing which column is which', () => {
	it('reads the headers of the committed demo file', () => {
		const mapping = guessColumns([
			'server_id',
			'service_datetime',
			'latitude',
			'longitude',
			'address',
			'case_number',
			'outcome',
			'person_served_description'
		]);

		expect(mapping).toMatchObject({
			server_id: 'server_id',
			at: 'service_datetime',
			lat: 'latitude',
			lng: 'longitude',
			address: 'address',
			case_ref: 'case_number',
			outcome: 'outcome',
			recipient_desc: 'person_served_description'
		});
	});

	it('does not care about case, spaces or punctuation', () => {
		const mapping = guessColumns(['Process Server', 'Date/Time of Service', 'Lat.', 'Long.']);

		expect(mapping.server_id).toBe('Process Server');
		expect(mapping.at).toBe('Date/Time of Service');
		expect(mapping.lat).toBe('Lat.');
		expect(mapping.lng).toBe('Long.');
	});

	it('keeps a separate date column and time column separate', () => {
		const mapping = guessColumns(['server', 'service_date', 'service_time', 'address']);

		expect(mapping.date).toBe('service_date');
		expect(mapping.time).toBe('service_time');
		expect(mapping.at).toBeUndefined();
	});

	it('drops the split columns when one column already holds both', () => {
		// Offering the server `at` *and* `date` would be ambiguous about which to believe.
		const mapping = guessColumns(['server', 'timestamp', 'date', 'time', 'address']);

		expect(mapping.at).toBe('timestamp');
		expect(mapping.date).toBeUndefined();
		expect(mapping.time).toBeUndefined();
	});

	it('never assigns one column to two fields', () => {
		const mapping = guessColumns(['server', 'date', 'address']);

		const used = FIELDS.map((field) => mapping[field]).filter(Boolean);
		expect(new Set(used).size).toBe(used.length);
	});

	it('leaves a field unguessed rather than guessing wrongly', () => {
		const mapping = guessColumns(['col_a', 'col_b', 'col_c']);

		expect(mapping.server_id).toBe('');
		expect(mapping.at).toBeUndefined();
		expect(isComplete(mapping)).toBe(false);
	});

	it('handles a file with no headers at all', () => {
		expect(guessColumns([])).toEqual({ server_id: '' });
	});

	it('prefers the licence column over a loose "agent" column', () => {
		const mapping = guessColumns(['agent', 'server_license', 'timestamp', 'address']);

		expect(mapping.server_id).toBe('server_license');
	});
});

describe('the rules the server also enforces', () => {
	it('accepts one combined datetime column', () => {
		expect(hasTime({ server_id: 's', at: 'when' })).toBe(true);
	});

	it('accepts a date and a time together, and neither alone', () => {
		expect(hasTime({ server_id: 's', date: 'd', time: 't' })).toBe(true);
		expect(hasTime({ server_id: 's', date: 'd' })).toBe(false);
		expect(hasTime({ server_id: 's', time: 't' })).toBe(false);
	});

	it('accepts coordinates only as a pair', () => {
		expect(hasPlace({ server_id: 's', lat: 'y', lng: 'x' })).toBe(true);
		expect(hasPlace({ server_id: 's', lat: 'y' })).toBe(false);
	});

	it('accepts an address on its own', () => {
		expect(hasPlace({ server_id: 's', address: 'a' })).toBe(true);
	});

	it('names what is still missing, as fields rather than as a sentence', () => {
		expect(missingFields({ server_id: '' })).toEqual(['server_id', 'at', 'address']);
		expect(missingFields({ server_id: 's', at: 'w', address: 'a' })).toEqual([]);
	});

	it('is complete only when a server, a time and a place are all named', () => {
		expect(isComplete({ server_id: 's', at: 'w', address: 'a' })).toBe(true);
		expect(isComplete({ server_id: '', at: 'w', address: 'a' })).toBe(false);
		expect(isComplete({ server_id: 's', address: 'a' })).toBe(false);
		expect(isComplete({ server_id: 's', at: 'w' })).toBe(false);
	});
});
