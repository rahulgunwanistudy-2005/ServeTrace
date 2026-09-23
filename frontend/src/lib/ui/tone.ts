/**
 * The mapping from what the engine decided to how it looks.
 *
 * It lives in a module rather than inside components for two reasons. It is the only
 * place a tier or a severity turns into a colour, so the result card, the findings list
 * and the advocate table cannot drift apart. And it is plain TypeScript, so the rule that
 * `CONSISTENT` is never red and `NO_DATA` is never alarming is something a test can hold
 * us to rather than something a reviewer has to notice.
 *
 * Bible §6: a consistent result is shown honestly and is not a failure, so it gets the
 * same visual weight as a contradiction rather than being quietly greyed out.
 */

import type { ClaimTier, Severity } from '$lib/api/client';

export type Tone = 'contradicted' | 'consistent' | 'caution' | 'neutral' | 'accent';

/** Background, border and text classes for a tone, in both colour schemes. */
export const toneClasses: Record<Tone, string> = {
	contradicted: 'bg-contradicted-quiet text-contradicted border-contradicted/25',
	consistent: 'bg-consistent-quiet text-consistent border-consistent/25',
	caution: 'bg-caution-quiet text-caution border-caution/30',
	neutral: 'bg-neutral-quiet text-neutral border-line',
	accent: 'bg-accent-quiet text-accent border-accent/25'
};

/** Just the ink, for a rule, an icon or a number that sits on the page background. */
export const toneInk: Record<Tone, string> = {
	contradicted: 'text-contradicted',
	consistent: 'text-consistent',
	caution: 'text-caution',
	neutral: 'text-muted',
	accent: 'text-accent'
};

export const toneEdge: Record<Tone, string> = {
	contradicted: 'border-contradicted',
	consistent: 'border-consistent',
	caution: 'border-caution',
	neutral: 'border-line-strong',
	accent: 'border-accent'
};

const TIER_TONE: Record<ClaimTier, Tone> = {
	contradicted: 'contradicted',
	consistent: 'consistent',
	no_data: 'neutral',
	inconclusive: 'neutral'
};

const SEVERITY_TONE: Record<Severity, Tone> = {
	strong: 'contradicted',
	moderate: 'caution',
	info: 'neutral'
};

export function tierTone(tier: ClaimTier): Tone {
	return TIER_TONE[tier];
}

export function severityTone(severity: Severity): Tone {
	return SEVERITY_TONE[severity];
}

/** Strongest first, which is the order the engine already sorts findings into. */
export const SEVERITY_ORDER: Record<Severity, number> = { strong: 0, moderate: 1, info: 2 };

export function bySeverity(a: { severity: Severity }, b: { severity: Severity }): number {
	return SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity];
}

/**
 * A distance the way a person says it. Under a kilometre is metres, because "0.3 km" is
 * a number and "300 metres" is a distance.
 */
export function formatKm(km: number): string {
	if (km < 1) return `${Math.round(km * 1000).toLocaleString('en-US')} metres`;
	return `${km.toFixed(1)} km`;
}

export function formatSpeed(kmh: number): string {
	return `${Math.round(kmh).toLocaleString('en-US')} km/h`;
}

/** New York time, always: an affidavit states a wall clock and never an offset. */
const NY = 'America/New_York';

export function formatDateTime(iso: string): string {
	return new Date(iso).toLocaleString('en-US', {
		timeZone: NY,
		day: 'numeric',
		month: 'long',
		year: 'numeric',
		hour: 'numeric',
		minute: '2-digit'
	});
}

export function formatDate(iso: string): string {
	// A bare `YYYY-MM-DD` parses as UTC midnight, which is the previous evening in New
	// York and would print the day before. Splitting the parts avoids the whole question.
	const [year = 1970, month = 1, day = 1] = iso.slice(0, 10).split('-').map(Number);
	return new Date(Date.UTC(year, month - 1, day)).toLocaleDateString('en-US', {
		timeZone: 'UTC',
		day: 'numeric',
		month: 'long',
		year: 'numeric'
	});
}
