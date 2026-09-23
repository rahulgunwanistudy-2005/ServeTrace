/**
 * Getting a design token into MapLibre.
 *
 * `app.css` defines the whole palette in `oklch`, which is the right choice for a design
 * system: it is perceptually uniform, so a dark-mode variant of a colour is one number
 * away rather than a guess. MapLibre parses its own style colours and understands none of
 * it — it wants hex, `rgb()` or a CSS colour name — so a layer painted straight from a
 * token silently fails to draw. That is the bug this module exists to prevent, and it
 * showed up exactly as bible §14's lesson predicts: clean type-check, clean lint, clean
 * tests, and an empty map.
 *
 * The conversion is done by the browser rather than by arithmetic here. One pixel is
 * filled with the token's value and read back, which gives the sRGB bytes the compositor
 * would have painted, including the gamut clamping it would have applied. Reimplementing
 * OKLCH→sRGB would mean the map and the page could disagree about what a colour is, and
 * that disagreement would be invisible until somebody compared two screenshots.
 *
 * Every function takes an explicit fallback. A map that draws in the wrong grey is a
 * cosmetic problem; a map that throws while a paint is in flight is a blank rectangle
 * where the evidence should be.
 */

export type Rasterizer = (value: string) => string | null;

const HEX = /^#[0-9a-f]{6}$/i;

/** Rasterize through a 1×1 canvas. Returns null wherever that is not possible. */
export function canvasRasterizer(): Rasterizer {
	if (typeof document === 'undefined') return () => null;

	let context: CanvasRenderingContext2D | null = null;
	try {
		const canvas = document.createElement('canvas');
		canvas.width = 1;
		canvas.height = 1;
		context = canvas.getContext('2d', { willReadFrequently: true });
	} catch {
		return () => null;
	}
	if (!context) return () => null;
	const ctx = context;

	return (value: string) => {
		try {
			ctx.clearRect(0, 0, 1, 1);
			// Seed with a known colour first: assigning an unparseable value to `fillStyle`
			// is a no-op rather than an error, so without this a bad token would silently
			// inherit whatever the last caller painted.
			ctx.fillStyle = '#000000';
			ctx.fillStyle = value;
			if (ctx.fillStyle === '#000000' && !isBlack(value)) return null;
			ctx.fillRect(0, 0, 1, 1);
			const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data;
			if (r === undefined || g === undefined || b === undefined) return null;
			return `#${[r, g, b].map((channel) => channel.toString(16).padStart(2, '0')).join('')}`;
		} catch {
			// A tainted or unavailable canvas (some privacy modes block `getImageData`).
			return null;
		}
	};
}

function isBlack(value: string): boolean {
	const trimmed = value.trim().toLowerCase();
	return trimmed === '#000' || trimmed === '#000000' || trimmed === 'black';
}

/**
 * The value of a CSS custom property on `:root`, as a colour MapLibre can parse.
 *
 * Reads the property live rather than caching it, because the dark-mode block in
 * `app.css` redefines every token and the map has to be able to ask again when the
 * scheme changes.
 */
export function cssColor(name: string, fallback: string, rasterize?: Rasterizer): string {
	if (typeof document === 'undefined') return fallback;

	const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
	if (!raw) return fallback;
	// Already something MapLibre understands: pass it through untouched rather than
	// round-tripping it through a rasterizer that could clamp it.
	if (HEX.test(raw)) return raw;

	return (rasterize ?? canvasRasterizer())(raw) ?? fallback;
}

/**
 * Resolve a whole palette at once.
 *
 * Layers are painted in one go and repainted in one go when the colour scheme changes,
 * so the tokens are resolved together — one rasterizer, one pass, and no chance of half
 * a map in one scheme and half in the other.
 */
export function resolvePalette<K extends string>(
	tokens: Record<K, { name: string; fallback: string }>,
	rasterize: Rasterizer = canvasRasterizer()
): Record<K, string> {
	const out = {} as Record<K, string>;
	for (const key of Object.keys(tokens) as K[]) {
		const token = tokens[key];
		out[key] = cssColor(token.name, token.fallback, rasterize);
	}
	return out;
}
