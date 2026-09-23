/**
 * The rules about how a verdict looks, as assertions rather than as review comments.
 *
 * Colour is the one place a component could quietly contradict bible §6 — a `CONSISTENT`
 * result rendered in red, or a `NO_DATA` result rendered as an alarm, would tell the user
 * something the engine never said. That is worth a test even though nothing here does
 * arithmetic.
 */

import { describe, expect, it } from 'vitest';

import { tiers, tierLabels, verdictLine } from '$copy/en';
import {
	bySeverity,
	formatDate,
	formatDateTime,
	formatKm,
	formatSpeed,
	severityTone,
	tierTone,
	toneClasses,
	toneEdge,
	toneInk
} from './tone';

const TIERS = ['contradicted', 'consistent', 'no_data', 'inconclusive'] as const;
const SEVERITIES = ['strong', 'moderate', 'info'] as const;

describe('tone', () => {
	it('gives every tier and severity a tone with classes defined for it', () => {
		for (const tier of TIERS) {
			const tone = tierTone(tier);
			expect(toneClasses[tone]).toBeTruthy();
			expect(toneInk[tone]).toBeTruthy();
			expect(toneEdge[tone]).toBeTruthy();
		}
		for (const severity of SEVERITIES) expect(toneClasses[severityTone(severity)]).toBeTruthy();
	});

	it('never renders a consistent result in the colour of a conflict', () => {
		expect(tierTone('consistent')).toBe('consistent');
		expect(tierTone('contradicted')).toBe('contradicted');
	});

	it('leaves the two unsettled tiers neutral rather than alarming', () => {
		expect(tierTone('no_data')).toBe('neutral');
		expect(tierTone('inconclusive')).toBe('neutral');
	});

	it('gives every tier a label and a headline that a badge can show', () => {
		for (const tier of TIERS) {
			expect(tierLabels[tier].length).toBeGreaterThan(0);
			expect(tiers[tier].headline).toMatch(/\.$/);
		}
	});
});

describe('bySeverity', () => {
	it('puts the strongest finding first', () => {
		const findings = [
			{ severity: 'info' as const },
			{ severity: 'strong' as const },
			{ severity: 'moderate' as const }
		];
		expect([...findings].sort(bySeverity).map((f) => f.severity)).toEqual([
			'strong',
			'moderate',
			'info'
		]);
	});

	it('does not sort alphabetically, which would put moderate above strong', () => {
		expect(bySeverity({ severity: 'strong' }, { severity: 'moderate' })).toBeLessThan(0);
	});
});

describe('formatting', () => {
	it('says metres below a kilometre and kilometres above it', () => {
		expect(formatKm(0.45)).toBe('450 metres');
		expect(formatKm(0.03)).toBe('30 metres');
		expect(formatKm(14.23)).toBe('14.2 km');
	});

	it('rounds a speed, because a decimal place there is false precision', () => {
		expect(formatSpeed(170.6)).toBe('171 km/h');
	});

	it('shows a claimed instant in New York time whatever the browser is set to', () => {
		// 23:42 UTC is 7:42 PM the same evening in New York, not 11:42 PM the next day.
		expect(formatDateTime('2025-06-12T23:42:00Z')).toContain('7:42');
		expect(formatDateTime('2025-06-12T23:42:00Z')).toContain('June 12');
	});

	it('does not move a bare date backwards by a day', () => {
		// `new Date('2027-03-14')` is UTC midnight, which is the evening of the 13th in New
		// York. A deadline printed a day early is a deadline someone could miss.
		expect(formatDate('2027-03-14')).toBe('March 14, 2027');
	});
});

describe('verdictLine', () => {
	const at = '2025-06-12T23:42:00Z';

	it('leads with the time and the distance, as bible §14.5 asks', () => {
		expect(verdictLine(at, 14.2, 171)).toBe(
			'At 7:42 PM your phone was 14.2 km from that address. Getting there in time would have taken about 171 km/h.'
		);
	});

	it('leaves out the speed when the engine did not measure one', () => {
		expect(verdictLine(at, 10.6, null)).toBe('At 7:42 PM your phone was 10.6 km from that address.');
	});

	it('says plainly when the phone was at the address', () => {
		expect(verdictLine(at, 0.03, null)).toContain('at that address');
	});

	it('claims nothing at all when there was no data', () => {
		expect(verdictLine(at, null, null)).toBe('We have no location data for 7:42 PM.');
	});
});
