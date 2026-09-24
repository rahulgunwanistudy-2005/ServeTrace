import { describe, expect, it } from 'vitest';
import {
	FRAGMENT_SHADER,
	IRIS_TOKENS,
	MAX_PIXELS,
	RENDER_SCALE,
	UNIFORM_NAMES,
	VERTEX_SHADER,
	hexToVec3,
	renderSize,
	shouldRun
} from './iridescent';

/** Every `uniform <type> <name>;` declared in a shader source. */
function declaredUniforms(source: string): string[] {
	return [...source.matchAll(/^\s*uniform\s+\w+\s+(\w+)\s*;/gm)].map((m) => m[1] as string);
}

describe('the uniform contract', () => {
	/**
	 * The failure this guards against is silent by specification: `getUniformLocation`
	 * returns `null` for a name the shader does not use, and `gl.uniform*` with a `null`
	 * location is defined to do nothing. So a renamed uniform dims or blanks the field
	 * with a clean console and a passing type-check — the same shape as the MapLibre bug
	 * in session 5. Asserted in both directions, because either half can drift.
	 */
	it('is exactly the set of uniforms the fragment shader declares', () => {
		expect([...declaredUniforms(FRAGMENT_SHADER)].sort()).toEqual([...UNIFORM_NAMES].sort());
	});

	it('names every colour token as a uniform, so no colour is hard-coded in the shader', () => {
		for (const key of Object.keys(IRIS_TOKENS)) {
			const uniform = `u${key[0]?.toUpperCase()}${key.slice(1)}`;
			expect(UNIFORM_NAMES).toContain(uniform);
		}
	});

	it('declares no uniform in the vertex shader, which takes no inputs at all', () => {
		expect(declaredUniforms(VERTEX_SHADER)).toEqual([]);
	});
});

describe('the shader sources', () => {
	/** GLSL ES 3.00 requires the directive to be the very first characters of the source. */
	it('open with the version directive on line one, as WebGL2 requires', () => {
		expect(FRAGMENT_SHADER.startsWith('#version 300 es\n')).toBe(true);
		expect(VERTEX_SHADER.startsWith('#version 300 es\n')).toBe(true);
	});

	it('use the GLSL ES 3.00 spellings rather than the 1.00 ones', () => {
		expect(FRAGMENT_SHADER).toContain('out vec4 fragColor;');
		expect(FRAGMENT_SHADER).not.toContain('gl_FragColor');
		expect(FRAGMENT_SHADER).not.toContain('varying');
	});

	/**
	 * Both sources are template literals, so a backtick inside a GLSL comment ends the
	 * string. That one is loud — the module stops parsing and every test in this file
	 * fails at import. Its quiet sibling is not: `${` inside the source interpolates
	 * silently, and the shader compiles into something nobody wrote.
	 */
	it('interpolate nothing, being template literals that happen to hold GLSL', () => {
		expect(FRAGMENT_SHADER).not.toContain('${');
		expect(VERTEX_SHADER).not.toContain('${');
	});

	/**
	 * Bible §16: the demo works with the network off, and the privacy page has nothing to
	 * disclose about this field. A texture fetch would change both of those.
	 */
	it('sample no texture, so the field stays a pure function of time', () => {
		expect(FRAGMENT_SHADER).not.toContain('sampler2D');
		expect(FRAGMENT_SHADER).not.toContain('texture(');
	});
});

describe('shouldRun', () => {
	const able = { documentAvailable: true, webgl2: true, reducedMotion: false };

	it('runs when everything is available', () => {
		expect(shouldRun(able)).toBe(true);
	});

	it('stands down for a person who asked for reduced motion', () => {
		expect(shouldRun({ ...able, reducedMotion: true })).toBe(false);
	});

	it('stands down without WebGL2 rather than falling back to WebGL1', () => {
		expect(shouldRun({ ...able, webgl2: false })).toBe(false);
	});

	it('stands down during a server-side render', () => {
		expect(shouldRun({ ...able, documentAvailable: false })).toBe(false);
	});
});

describe('hexToVec3', () => {
	it('converts sRGB bytes to 0..1 floats', () => {
		expect(hexToVec3('#000000')).toEqual([0, 0, 0]);
		expect(hexToVec3('#ffffff')).toEqual([1, 1, 1]);
	});

	it('keeps the channels in order', () => {
		const [r, g, b] = hexToVec3('#804020') ?? [];
		expect(r).toBeGreaterThan(g as number);
		expect(g).toBeGreaterThan(b as number);
	});

	it('returns null for anything that is not a six-digit hex colour', () => {
		// `cssColor` falls back rather than returning these, but the renderer has its own
		// fallback precisely because that promise lives in another module.
		expect(hexToVec3('#fff')).toBeNull();
		expect(hexToVec3('oklch(0.7 0.09 68)')).toBeNull();
		expect(hexToVec3('')).toBeNull();
	});

	it('every token fallback parses, because the fallback is the last line of defence', () => {
		for (const token of Object.values(IRIS_TOKENS)) {
			expect(hexToVec3(token.fallback), token.name).not.toBeNull();
		}
	});
});

describe('renderSize', () => {
	it('draws at a fraction of CSS resolution, because the field has no detail to lose', () => {
		expect(renderSize(1000, 500)).toEqual({ width: 600, height: 300 });
		expect(RENDER_SCALE).toBeLessThan(1);
	});

	it('caps total pixels so a large display cannot ask for a fortune per frame', () => {
		const { width, height } = renderSize(7680, 4320);
		expect(width * height).toBeLessThanOrEqual(MAX_PIXELS);
	});

	it('keeps the aspect ratio when it caps', () => {
		const wide = renderSize(7680, 4320);
		expect(wide.width / wide.height).toBeCloseTo(7680 / 4320, 1);
	});

	it('never returns a zero dimension, which would be an invalid viewport', () => {
		for (const [w, h] of [
			[0, 0],
			[1, 1],
			[0.4, 900]
		]) {
			const size = renderSize(w as number, h as number);
			expect(size.width).toBeGreaterThan(0);
			expect(size.height).toBeGreaterThan(0);
		}
	});
});
