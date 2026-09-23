import { describe, expect, it } from 'vitest';
import { canvasRasterizer, cssColor, resolvePalette, type Rasterizer } from './color';

/**
 * The conversion itself belongs to the browser and is checked there. What is checked here
 * is everything around it, which is where a map goes blank: an unreadable token, an
 * unavailable canvas, a rasterizer that returns nothing. Every one of those has to end in
 * the fallback rather than in an exception or an `oklch()` string reaching MapLibre.
 *
 * Tests run in node, where there is no `document`, so `cssColor` takes the server path
 * unless a rasterizer is injected — which is itself worth asserting, because this module
 * is imported by a component that is server-rendered.
 */

const ALWAYS: Rasterizer = () => '#123456';
const NEVER: Rasterizer = () => null;

describe('without a document', () => {
	it('returns the fallback rather than throwing', () => {
		expect(cssColor('--st-accent', '#1d4ed8')).toBe('#1d4ed8');
	});

	it('still returns the fallback when a rasterizer is handed in', () => {
		// There is no `:root` to read the token off, so there is nothing to rasterize.
		expect(cssColor('--st-accent', '#1d4ed8', ALWAYS)).toBe('#1d4ed8');
	});

	it('builds a rasterizer that safely refuses', () => {
		expect(canvasRasterizer()('oklch(0.5 0 0)')).toBeNull();
	});
});

describe('resolving a palette', () => {
	it('falls back for every token it cannot resolve', () => {
		const palette = resolvePalette(
			{
				ink: { name: '--st-muted', fallback: '#64748b' },
				alarm: { name: '--st-contradicted', fallback: '#c2410c' }
			},
			NEVER
		);

		expect(palette).toEqual({ ink: '#64748b', alarm: '#c2410c' });
	});

	it('returns one entry per token and never an empty string', () => {
		const palette = resolvePalette(
			{ a: { name: '--x', fallback: '#000000' }, b: { name: '--y', fallback: '#ffffff' } },
			NEVER
		);

		expect(Object.keys(palette).sort()).toEqual(['a', 'b']);
		expect(Object.values(palette).every((value) => value.length > 0)).toBe(true);
	});

	it('gives MapLibre something it can parse for every token', () => {
		// The whole point: an `oklch()` string reaching a paint property is the bug.
		const palette = resolvePalette(
			{ ink: { name: '--st-muted', fallback: '#64748b' } },
			ALWAYS
		);

		for (const value of Object.values(palette)) {
			expect(value).toMatch(/^#[0-9a-f]{6}$/i);
		}
	});
});
