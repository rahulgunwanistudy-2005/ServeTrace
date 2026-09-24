/**
 * The iridescent field's shader, and the decisions around it that can be tested.
 *
 * `IridescentField.svelte` is the part that touches the GPU. Everything here is pure, so
 * vitest — which runs in `environment: node`, with no canvas and no WebGL — can still
 * hold the parts that are easy to get silently wrong.
 *
 * The one that matters is `UNIFORM_NAMES`. A misspelled or renamed uniform is the classic
 * silent WebGL failure: `getUniformLocation` returns `null`, `gl.uniform*` with a `null`
 * location is defined to be a no-op rather than an error, and the result is a black
 * rectangle with a clean console. It is the same shape as the MapLibre bug in session 5 —
 * real failure, silent tooling — so the contract is asserted in both directions by a test
 * that reads the shader source.
 */

/**
 * Every uniform the renderer sets. The test asserts this list and the `uniform`
 * declarations in `FRAGMENT_SHADER` are the same set, so adding one to either without the
 * other fails rather than dimming the field.
 */
export const UNIFORM_NAMES = [
	'uResolution',
	'uTime',
	'uWarm',
	'uCool',
	'uEdgeWarm',
	'uEdgeCool',
	'uBody',
	'uDeep'
] as const;

export type UniformName = (typeof UNIFORM_NAMES)[number];

/**
 * The field's colours, as they are named in `app.css`.
 *
 * Resolved at runtime through `lib/map/color.ts`, which rasterises one pixel and reads
 * the sRGB bytes back. The palette is authored in `oklch` and WebGL wants linear-ish
 * floats; reimplementing that conversion here is exactly the drift session 5 wrote a
 * module to prevent, so it is not reimplemented here.
 *
 * The fallbacks are the same hues, pre-converted, for the case where the rasterizer is
 * unavailable — some privacy modes block `getImageData`. A field in slightly the wrong
 * grey is a cosmetic problem; the alternative is no field.
 */
export const IRIS_TOKENS = {
	warm: { name: '--st-iris-warm', fallback: '#c79a5c' },
	cool: { name: '--st-iris-cool', fallback: '#6f92c4' },
	edgeWarm: { name: '--st-iris-edge-warm', fallback: '#7c6242' },
	edgeCool: { name: '--st-iris-edge-cool', fallback: '#5b6675' },
	body: { name: '--st-iris-body', fallback: '#1f232b' },
	deep: { name: '--st-iris-deep', fallback: '#0f1014' }
} as const;

export type IrisToken = keyof typeof IRIS_TOKENS;

/** What the renderer needs to know before it decides to exist at all. */
export interface FieldCapabilities {
	/** `prefers-reduced-motion: reduce`. A person asking for less motion gets none. */
	reducedMotion: boolean;
	/** A WebGL2 context was obtained. WebGL1 is not worth a second code path. */
	webgl2: boolean;
	/** False during SSR, and on the server there is no canvas to draw into. */
	documentAvailable: boolean;
}

/**
 * Whether the canvas should run.
 *
 * Every `false` here leaves `.st-iridescent::before` — the CSS field — on screen, which
 * is what the product looked like before this module existed. That is the whole reason
 * the CSS field was kept rather than replaced.
 */
export function shouldRun(caps: FieldCapabilities): boolean {
	return caps.documentAvailable && caps.webgl2 && !caps.reducedMotion;
}

/** `#rrggbb` to three sRGB floats in 0..1. Returns null for anything else. */
export function hexToVec3(hex: string): [number, number, number] | null {
	const match = /^#([0-9a-f]{6})$/i.exec(hex.trim());
	if (!match?.[1]) return null;
	const n = Number.parseInt(match[1], 16);
	return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

/**
 * How many device pixels to actually draw.
 *
 * The field has no detail in it — every profile in the shader is a Gaussian and every
 * warp is smoothed noise — so drawing it at full device resolution buys nothing visible
 * and costs a phone its battery. Six tenths of a CSS pixel, and a hard ceiling on total
 * pixels so a large external display does not quietly ask for eight megapixels a frame.
 */
export const RENDER_SCALE = 0.6;
export const MAX_PIXELS = 1_200_000;

export function renderSize(cssWidth: number, cssHeight: number): { width: number; height: number } {
	const w = Math.max(1, Math.floor(cssWidth * RENDER_SCALE));
	const h = Math.max(1, Math.floor(cssHeight * RENDER_SCALE));
	const pixels = w * h;
	if (pixels <= MAX_PIXELS) return { width: w, height: h };
	const shrink = Math.sqrt(MAX_PIXELS / pixels);
	return {
		width: Math.max(1, Math.floor(w * shrink)),
		height: Math.max(1, Math.floor(h * shrink))
	};
}

/**
 * A full-screen triangle. Larger than the viewport and clipped to it, which costs one
 * fewer vertex than a quad and has no diagonal seam. No attributes: the position comes
 * from `gl_VertexID`, so there is no buffer to create, bind or delete.
 */
export const VERTEX_SHADER = `#version 300 es
void main() {
  vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
  gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}`;

/**
 * The field.
 *
 * The reference is a photograph of light raking across anodised metal. Three things make
 * it read that way rather than as a striped gradient:
 *
 * 1. **The profile is asymmetric.** A wide dark face, then a thin bright specular line.
 *    Equal light and dark bands read as stripes; this reads as a surface.
 * 2. **The bands are warped, not straight.** Two octaves of value noise bend them, and
 *    the noise itself drifts, so bands curve, flatten and re-form rather than sliding
 *    past. That is what the recording actually shows happening over its ten seconds.
 * 3. **The specular edges disperse.** Each channel samples the band coordinate at a
 *    slightly different offset, so an edge fringes warm on one side and cool on the
 *    other. This is the whole iridescence effect and it is three lines.
 *
 * It is decoration and never information — bible §6 reserves colour for verdicts, and no
 * meaning is attached to any hue in here.
 */
export const FRAGMENT_SHADER = `#version 300 es
precision mediump float;

uniform vec2 uResolution;
uniform float uTime;
uniform vec3 uWarm;
uniform vec3 uCool;
uniform vec3 uEdgeWarm;
uniform vec3 uEdgeCool;
uniform vec3 uBody;
uniform vec3 uDeep;

out vec4 fragColor;

float hash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

float vnoise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
    mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x),
    u.y
  );
}

float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  for (int i = 0; i < 3; i++) {
    v += a * vnoise(p);
    p *= 2.03;
    a *= 0.5;
  }
  return v;
}

/*
 * A soft lobe centred on every whole value of x, measured in band widths.
 *
 * The wrap is done here rather than with fract() at the call site so the three dispersed
 * samples stay continuous across a band boundary. With fract() the red channel crosses
 * the seam a fraction before the blue one and leaves a hard coloured line down the field,
 * which is the one artefact that would give the whole thing away as generated.
 */
float lobe(float x, float w) {
  float d = (x - floor(x + 0.5)) / w;
  return exp(-d * d);
}

void main() {
  vec2 uv = gl_FragCoord.xy / uResolution;
  float aspect = uResolution.x / uResolution.y;
  vec2 p = vec2(uv.x * aspect, uv.y);

  /* 114 degrees, the angle the CSS field uses, so the two layers agree about which way
     the light is raking. The tangent runs along a band rather than across it. */
  const float a = 1.9897;
  vec2 dir = vec2(cos(a), sin(a));
  vec2 tangent = vec2(-dir.y, dir.x);

  /* The warp, at low frequency in *space* but not in time: the bands bend in long slow
     curves, the way a hanging sheet does, while the curves themselves reorganise fast
     enough to watch. Higher spatial frequencies here turn the field into ripples.

     The rates are measured, not chosen. Frames sampled from the reference at 8fps differ
     from their neighbours by 7.6 grey levels out of 255, and by 36 over a full second.
     A first cut of this shader ran at roughly a twelfth of that: the pixels changed, so
     every check said it was animating, and on screen it was frozen. Both terms drift at
     different rates and in different directions, so the pattern never returns to where it
     was and no loop point is visible. */
  float warp =
    fbm(p * 0.72 + vec2(uTime * 0.5775, uTime * -0.385)) * 1.20 +
    fbm(p * 1.90 + vec2(uTime * -0.315, uTime * 0.203)) * 0.26;

  /* Few bands and wide. The reference has six or seven across the frame; at two or three
     times that frequency the same shader reads as corduroy. The drift term slides them
     across as they reshape — the reference does both, and warping alone reads as a
     surface breathing in place rather than light travelling over one. */
  float s = dot(p, dir) * 3.6 + warp + uTime * 0.2975;
  float along = dot(p, tangent);
  float band = floor(s);

  /* How brightly this stretch of this band is catching the light. It varies along the
     band and independently from band to band, which is what stops a row of identical
     highlights reading as a machine-made pattern — in the reference a highlight glows
     over part of a fold and dies away over the rest. */
  float lit = smoothstep(0.28, 0.80, fbm(vec2(along * 0.85 + uTime * 0.665, band * 1.37)));

  /* Which way this band is tinted. Some read cool and some warm, as they do on a piece
     of anodised metal, rather than every band carrying both. */
  float tint = smoothstep(0.34, 0.70, fbm(vec2(along * 0.4, band * 0.71 + 3.1)));
  vec3 edge = mix(uEdgeCool, uEdgeWarm, tint);

  /* Dispersion, in band widths. Each channel reads the specular a little to one side of
     the others, so a highlight fringes warm on one edge and cool on the other. This is
     the whole iridescence effect, and it is these three lines. */
  float disp = 0.018 + 0.026 * fbm(p * 1.6 + uTime * 0.315);
  float width = 0.075 + 0.05 * tint;
  vec3 core = vec3(
    lobe(s + disp - 0.58, width),
    lobe(s - 0.58, width),
    lobe(s - disp - 0.58, width)
  );

  /* The band's own face: a broad sheen across it rather than a flat dark stripe. Without
     this the field is black between the highlights and the bands stop reading as
     surfaces that have width. */
  float sheen = pow(max(sin(fract(s) * 3.14159265), 0.0), 1.5);

  vec3 col = uDeep;
  col = mix(col, uBody, sheen * (0.55 + 0.45 * lit));
  /* The face catches some of its own band's light, not just the specular line down it.
     Without this the faces sit at the body token — near-black — and the field reads as
     black with wires on it; in the reference the faces themselves come up to a mid grey
     and the highlight is the top of that range rather than the only part of it. */
  col += edge * sheen * lit * 0.42;
  /* 1.35 rather than the 1.75 this started at. The cool edge token is a desaturated
     slate, so at the higher gain its highlights clipped toward white and read as lit
     glass rather than as lit metal — the reference's brightest points still carry their
     hue. */
  col += edge * core * lit * 1.35;

  /* The two tints, placed where the CSS radials are so the layers agree. */
  float tw = exp(-dot(p - vec2(0.38, 0.66), p - vec2(0.38, 0.66)) * 2.6);
  float tc = exp(-dot(p - vec2(1.05, 0.76), p - vec2(1.05, 0.76)) * 2.9);
  col += uWarm * tw * 0.20;
  col += uCool * tc * 0.17;

  /* The breath.
     Measured from the reference the same way as the drift rates above: mean frame
     brightness over its ten seconds runs from 10.6 to 72.4, a factor of 6.8. A first cut
     here spanned 0.62 to 1.0, a factor of 1.6, which is a field at a constant brightness
     with a wobble on it. Only the floor moves — the peak is what the ceiling below
     guards, and lowering the trough cannot cost contrast anywhere. */
  col *= 0.17 + 0.83 * pow(0.5 + 0.5 * sin(uTime * 0.33), 1.4);

  /*
   * Soft rolloff, with a ceiling.
   *
   * Two reasons, and the second is the one that matters.
   *
   * It looks better: a specular peak that clips to white reads as a blown-out light
   * rather than as metal, which keeps its hue at its brightest. This rolls the top of
   * the range off instead of cutting it.
   *
   * And it is what keeps the field safe under type. The scrim is static and this field
   * is not, so a highlight wanders under copy that a still frame showed as clear. It did
   * exactly that: the 12px eyebrow on the landing hero measured 5.3:1 on the frame it
   * was first checked on and 3.9:1 fourteen seconds later, under a peak that had clipped
   * to white. A ceiling on the brightest pixel the field can ever produce turns the
   * contrast guarantee back into something a measurement can hold, rather than a
   * property of which frame anybody happened to look at.
   */
  col = (1.0 - exp(-col * 1.45)) * 0.66;

  fragColor = vec4(col, 1.0);
}`;
