import { describe, expect, it } from 'vitest';

import { parseManual } from './manual';

const AT_WORK = {
	date: '2025-06-12',
	from: '08:00',
	to: '20:00',
	address: '1400 Lexington Avenue, Manhattan'
};

describe('parseManual', () => {
	it('turns "I was at work from 8 to 8" into one interval', () => {
		const result = parseManual([AT_WORK]);
		expect(result.pending).toHaveLength(1);
		expect(result.pending[0]).toMatchObject({
			t: '2025-06-12T12:00:00.000Z',
			t_end: '2025-06-13T00:00:00.000Z',
			kind: 'manual'
		});
	});

	it('labels it as typed in, so a packet can never read it as recorded', () => {
		expect(parseManual([AT_WORK]).pending[0]?.label).toBe('Typed in by you');
	});

	it('keeps a label the user gave it', () => {
		expect(parseManual([{ ...AT_WORK, label: "My client's flat" }]).pending[0]?.label).toBe(
			"My client's flat"
		);
	});

	it('reads an overnight shift as one evening and not as negative time', () => {
		const result = parseManual([{ ...AT_WORK, from: '20:00', to: '02:00' }]);
		const { t, t_end } = result.pending[0] ?? {};
		expect(Date.parse(t_end as string) - Date.parse(t as string)).toBe(6 * 3_600_000);
	});

	it('asks for what is missing rather than half-reading an entry', () => {
		const result = parseManual([{ ...AT_WORK, address: '  ' }]);
		expect(result.pending).toEqual([]);
		expect(result.skipped).toBe(1);
		expect(result.warnings[0]).toMatch(/address/);
	});

	it('skips an entry with an unreadable time', () => {
		expect(parseManual([{ ...AT_WORK, from: 'after lunch' }]).skipped).toBe(1);
	});

	it('keeps the good entries when one is wrong', () => {
		const result = parseManual([AT_WORK, { ...AT_WORK, from: '' }]);
		expect(result.pending).toHaveLength(1);
		expect(result.skipped).toBe(1);
	});

	it('says which reading it used on the night the clocks change', () => {
		const result = parseManual([
			{ date: '2025-11-02', from: '01:00', to: '01:45', address: '2100 White Plains Road' }
		]);
		expect(result.warnings.join(' ')).toMatch(/clocks change/);
	});

	it('handles being given nothing', () => {
		expect(parseManual([])).toEqual({ pending: [], skipped: 0, warnings: [] });
	});
});
