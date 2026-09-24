<script lang="ts">
	/**
	 * The moving iridescent field. Bible §14, session 8.
	 *
	 * Dropped inside any `.st-panel.st-iridescent`, where it paints over that rule's CSS
	 * field (z −3) and under the scrim (z −1) that makes copy on top of it legible.
	 *
	 * ## Nothing here is load-bearing
	 *
	 * Session 6 declined to borrow the reference's motion because bible §16 wants a demo
	 * that never fails. The answer taken here is to keep the motion off the critical path
	 * rather than to do without it. Every one of these leaves the CSS field on screen and
	 * says nothing to the user:
	 *
	 * - server-side render, or no `document`
	 * - `prefers-reduced-motion: reduce`
	 * - no WebGL2 (an old browser, a blocklisted GPU, a hardened privacy mode)
	 * - a shader that will not compile or link
	 * - `webglcontextlost`, which a browser may fire at any time under memory pressure
	 *
	 * The canvas starts transparent and transitions in only once it has drawn a frame, so
	 * a failure between mount and first paint is not even a flicker.
	 *
	 * ## And nothing here costs more than it has to
	 *
	 * The primary user is on a phone. The field is drawn at `RENDER_SCALE` of CSS
	 * resolution (it has no detail to lose), the loop stops when the tab is hidden and
	 * when the panel scrolls out of view, and the whole context is released on destroy.
	 */
	import { onMount } from 'svelte';
	import { resolvePalette } from '$lib/map/color';
	import {
		FRAGMENT_SHADER,
		IRIS_TOKENS,
		UNIFORM_NAMES,
		VERTEX_SHADER,
		renderSize,
		shouldRun,
		hexToVec3,
		type IrisToken,
		type UniformName
	} from './iridescent';

	let canvas = $state<HTMLCanvasElement | null>(null);
	let live = $state(false);

	onMount(() => {
		if (typeof document === 'undefined' || !canvas) return;

		const reducedMotion =
			typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;

		let gl: WebGL2RenderingContext | null = null;
		try {
			gl = canvas.getContext('webgl2', {
				alpha: false,
				antialias: false,
				depth: false,
				stencil: false,
				// The field is never captured. The evidence packet's map image comes from
				// MapLibre, which sets this itself for exactly that reason (bible §15).
				preserveDrawingBuffer: false,
				powerPreference: 'low-power'
			});
		} catch {
			gl = null;
		}

		if (!shouldRun({ documentAvailable: true, webgl2: gl !== null, reducedMotion })) {
			return;
		}
		// `shouldRun` has established this, but it cannot narrow the type.
		if (!gl) return;
		const ctx = gl;
		const element = canvas;

		const program = build(ctx);
		if (!program) return;

		const locations = {} as Record<UniformName, WebGLUniformLocation | null>;
		for (const name of UNIFORM_NAMES) {
			locations[name] = ctx.getUniformLocation(program, name);
		}

		const palette = resolvePalette(IRIS_TOKENS);
		const rgb = {} as Record<IrisToken, [number, number, number]>;
		for (const key of Object.keys(IRIS_TOKENS) as IrisToken[]) {
			rgb[key] = hexToVec3(palette[key]) ?? [0, 0, 0];
		}

		ctx.useProgram(program);
		ctx.uniform3fv(locations.uWarm, rgb.warm);
		ctx.uniform3fv(locations.uCool, rgb.cool);
		ctx.uniform3fv(locations.uEdgeWarm, rgb.edgeWarm);
		ctx.uniform3fv(locations.uEdgeCool, rgb.edgeCool);
		ctx.uniform3fv(locations.uBody, rgb.body);
		ctx.uniform3fv(locations.uDeep, rgb.deep);

		let frame = 0;
		let running = false;
		let onScreen = true;
		/**
		 * Time advances only while the loop runs, rather than being read from the clock.
		 * A field that had kept moving while the tab was hidden would jump on return, and
		 * the jump is more noticeable than the motion.
		 */
		let clock = 0;
		let last = 0;

		function size() {
			const rect = element.getBoundingClientRect();
			const { width, height } = renderSize(rect.width, rect.height);
			if (element.width === width && element.height === height) return;
			element.width = width;
			element.height = height;
			ctx.viewport(0, 0, width, height);
			ctx.uniform2f(locations.uResolution, width, height);
		}

		function draw(now: number) {
			frame = requestAnimationFrame(draw);
			// Clamped: a tab restored after an hour must not advance the field by an hour.
			clock += Math.min(now - last, 100) / 1000;
			last = now;
			size();
			ctx.uniform1f(locations.uTime, clock);
			ctx.drawArrays(ctx.TRIANGLES, 0, 3);
			if (!live) live = true;
		}

		function start() {
			if (running) return;
			running = true;
			last = performance.now();
			frame = requestAnimationFrame(draw);
		}

		function stop() {
			if (!running) return;
			running = false;
			cancelAnimationFrame(frame);
		}

		function sync() {
			if (onScreen && document.visibilityState === 'visible') start();
			else stop();
		}

		/**
		 * A lost context is not an error and not rare — a browser may drop one whenever it
		 * wants the memory back. The canvas is removed and the CSS field underneath simply
		 * becomes visible again.
		 */
		function onLost(event: Event) {
			event.preventDefault();
			stop();
			live = false;
		}

		const observer =
			typeof IntersectionObserver === 'function'
				? new IntersectionObserver((entries) => {
						onScreen = entries.some((entry) => entry.isIntersecting);
						sync();
					})
				: null;
		observer?.observe(element);

		element.addEventListener('webglcontextlost', onLost);
		document.addEventListener('visibilitychange', sync);
		size();
		sync();

		return () => {
			stop();
			observer?.disconnect();
			element.removeEventListener('webglcontextlost', onLost);
			document.removeEventListener('visibilitychange', sync);
			ctx.deleteProgram(program);
			// Asks the driver for the memory back now rather than at the next GC. Absent on
			// older implementations, hence the guard.
			ctx.getExtension('WEBGL_lose_context')?.loseContext();
		};
	});

	/** Compile and link. Returns null on any failure, which is a fall back to the CSS. */
	function build(gl: WebGL2RenderingContext): WebGLProgram | null {
		const vertex = compile(gl, gl.VERTEX_SHADER, VERTEX_SHADER);
		const fragment = compile(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
		if (!vertex || !fragment) return null;

		const program = gl.createProgram();
		if (!program) return null;
		gl.attachShader(program, vertex);
		gl.attachShader(program, fragment);
		gl.linkProgram(program);
		// Safe once linked, and the driver frees them with the program.
		gl.deleteShader(vertex);
		gl.deleteShader(fragment);

		if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
			gl.deleteProgram(program);
			return null;
		}
		return program;
	}

	function compile(gl: WebGL2RenderingContext, kind: number, source: string): WebGLShader | null {
		const shader = gl.createShader(kind);
		if (!shader) return null;
		gl.shaderSource(shader, source);
		gl.compileShader(shader);
		if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
			gl.deleteShader(shader);
			return null;
		}
		return shader;
	}
</script>

<!--
	`aria-hidden` and no alternative text: this is decoration. Bible §14 asks for a text
	alternative to the *map*, because the map carries evidence. This carries none.
-->
<canvas
	bind:this={canvas}
	aria-hidden="true"
	class="pointer-events-none absolute inset-0 -z-[2] size-full transition-opacity duration-700
	       motion-reduce:hidden"
	style:opacity={live ? 1 : 0}
></canvas>
