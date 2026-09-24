<script lang="ts">
	/**
	 * The claimed service address, and where the person's phone actually was. Bible §14.5.
	 *
	 * This is the picture the whole product exists to produce: one red pin at a door
	 * somebody swore to, a trail of the person's own records somewhere else, and a dashed
	 * line between them carrying the distance and the speed that journey would have taken.
	 *
	 * It follows `AdvocateMap` in every structural decision, and for the reasons recorded
	 * there in session 5:
	 *
	 * - **Colour is never the only signal** (bible §14). The claim is a pin *and* a label;
	 *   the gap is a dashed line *and* a number; and `ClaimTable` beside this carries the
	 *   same facts as text for anyone who cannot use the map at all.
	 * - **`text-font` is set on every symbol layer.** MapLibre defaults to Open Sans,
	 *   OpenFreeMap serves only Noto, and a 404'd glyph errors the whole *tile* — which
	 *   belongs to a source, not a layer, so one unlabelled symbol layer silently takes
	 *   down every line sharing its source.
	 * - **Colours come from the tokens** through `color.ts`, because `app.css` is `oklch`
	 *   and MapLibre understands none of it.
	 * - **`preserveDrawingBuffer`** so the evidence packet can capture this canvas
	 *   (bible §15). It is the only way to read pixels back after a paint.
	 */
	import maplibregl from 'maplibre-gl';
	import 'maplibre-gl/dist/maplibre-gl.css';

	import type { CaseAnalysis, LocationFix } from '$lib/api/client';
	import { result } from '$copy/en';
	import { resolvePalette } from './color';
	import { formatKm, formatSpeed } from '$lib/ui/tone';
	import { formatNY } from '$lib/ingest/tz';

	let {
		analysis,
		fixes,
		onReady
	}: {
		analysis: CaseAnalysis;
		/** All windowed points, when the caller has them. Falls back to what the engine used. */
		fixes?: LocationFix[];
		/**
		 * Handed a function that captures the canvas, once there is a canvas to capture.
		 *
		 * A push — capture on `idle`, hand the parent a PNG — was the first design and it
		 * was wrong twice over. It made the packet depend on an event having fired at some
		 * earlier moment, so a map that never went idle silently produced a packet with no
		 * map; and it captured a frame from before the person had touched the scrubber. A
		 * pull has neither problem: the packet asks at the moment it is built, and gets
		 * exactly what is on screen.
		 */
		onReady?: (capture: () => string | null) => void;
	} = $props();

	const STYLE = 'https://tiles.openfreemap.org/styles/liberty';
	const FONT = ['Noto Sans Bold'];

	const TOKENS = {
		ink: { name: '--st-muted', fallback: '#6d6a65' },
		surface: { name: '--st-surface', fallback: '#f0efec' },
		alarm: { name: '--st-contradicted', fallback: '#b42318' },
		accent: { name: '--st-accent', fallback: '#211f1c' }
	} as const;

	/** Bible §14.5: the trail is the hours either side of the claim, not the whole file. */
	const TRAIL_MINUTES = 90;

	let container = $state<HTMLDivElement | null>(null);
	let map = $state<maplibregl.Map | null>(null);
	let ready = $state(false);
	let failed = $state(false);
	/** Minutes from the claimed moment; the scrubber's value. */
	let offset = $state(TRAIL_MINUTES);

	const claim = $derived(
		analysis.verdicts.find((v) => v.claim_ref === 'served_at') ?? analysis.verdicts[0] ?? null
	);

	/** Every point available to draw, newest information first: the caller's, else the engine's. */
	const allFixes = $derived(
		fixes && fixes.length > 0
			? fixes
			: analysis.verdicts.flatMap((v) => v.fixes_used as unknown as LocationFix[])
	);

	const claimMs = $derived(claim ? Date.parse(claim.claimed_at) : Number.NaN);

	/**
	 * How far a fix is, in time, from the claimed moment.
	 *
	 * A VISIT and a MANUAL entry are intervals, not instants (bible §10), and the engine's
	 * visit test turns on whether the interval *covers* the claim. A first cut here
	 * measured from `t` alone, and so a recorded stay from 8:00 AM to 8:00 PM — the one
	 * that contradicts a 7:42 PM service, and the whole reason the demo case exists —
	 * measured as eleven hours away and was filtered out of its own map. Zero of one.
	 *
	 * Distance to the interval, then: zero while inside it.
	 */
	function gapMs(fix: LocationFix): number {
		const start = Date.parse(fix.t);
		const end = fix.t_end ? Date.parse(fix.t_end) : start;
		if (claimMs >= start && claimMs <= end) return 0;
		return claimMs < start ? start - claimMs : claimMs - end;
	}

	/** The points inside the scrubber's current window, in time order. */
	const shown = $derived.by(() => {
		if (!claim || Number.isNaN(claimMs)) return [];
		const span = offset * 60_000;
		return allFixes
			.filter((fix) => gapMs(fix) <= span)
			.sort((a, b) => a.t.localeCompare(b.t));
	});

	/** The point the engine leaned on: nearest in time to the claim. */
	const nearest = $derived.by(() => {
		if (!claim || allFixes.length === 0 || Number.isNaN(claimMs)) return null;
		return allFixes.reduce((best, fix) => (gapMs(fix) < gapMs(best) ? fix : best));
	});

	/** A stay that covers the claim is described by its span, not by when it started. */
	const nearestCovers = $derived(nearest !== null && gapMs(nearest) === 0 && Boolean(nearest.t_end));

	function trailGeoJson(rows: LocationFix[]) {
		return {
			type: 'FeatureCollection' as const,
			features:
				rows.length < 2
					? []
					: [
							{
								type: 'Feature' as const,
								geometry: {
									type: 'LineString' as const,
									coordinates: rows.map((fix) => [fix.loc.lng, fix.loc.lat])
								},
								properties: {}
							}
						]
		};
	}

	function fixesGeoJson(rows: LocationFix[]) {
		return {
			type: 'FeatureCollection' as const,
			features: rows.map((fix) => ({
				type: 'Feature' as const,
				geometry: { type: 'Point' as const, coordinates: [fix.loc.lng, fix.loc.lat] },
				properties: { at: fix.t, label: fix.label ?? '', kind: fix.kind }
			}))
		};
	}

	function claimGeoJson() {
		if (!claim) return { type: 'FeatureCollection' as const, features: [] };
		return {
			type: 'FeatureCollection' as const,
			features: [
				{
					type: 'Feature' as const,
					geometry: {
						type: 'Point' as const,
						coordinates: [claim.claimed_location.lng, claim.claimed_location.lat]
					},
					properties: { label: result.claimedPin }
				}
			]
		};
	}

	/**
	 * The gap: nearest recorded point to the claimed door.
	 *
	 * Drawn only when the engine found a distance. A line with no number on it would be
	 * decoration, and this one is the argument.
	 */
	function gapGeoJson() {
		const km = claim?.nearest_fix_km;
		if (!claim || !nearest || km === null || km === undefined) {
			return { type: 'FeatureCollection' as const, features: [] };
		}
		const parts = [formatKm(km)];
		const speed = claim.required_speed_kmh;
		if (speed !== null && speed !== undefined) parts.push(formatSpeed(speed));
		return {
			type: 'FeatureCollection' as const,
			features: [
				{
					type: 'Feature' as const,
					geometry: {
						type: 'LineString' as const,
						coordinates: [
							[nearest.loc.lng, nearest.loc.lat],
							[claim.claimed_location.lng, claim.claimed_location.lat]
						]
					},
					properties: { label: parts.join(' · ') }
				}
			]
		};
	}

	function paint(created: maplibregl.Map) {
		const { ink, surface, alarm, accent } = resolvePalette(TOKENS);

		created.addSource('trail', { type: 'geojson', data: trailGeoJson(shown) });
		created.addSource('fixes', { type: 'geojson', data: fixesGeoJson(shown) });
		created.addSource('gap', { type: 'geojson', data: gapGeoJson() });
		created.addSource('claim', { type: 'geojson', data: claimGeoJson() });

		created.addLayer({
			id: 'trail',
			type: 'line',
			source: 'trail',
			layout: { 'line-cap': 'round', 'line-join': 'round' },
			paint: { 'line-color': accent, 'line-width': 3, 'line-opacity': 0.5 }
		});

		created.addLayer({
			id: 'fixes',
			type: 'circle',
			source: 'fixes',
			paint: {
				'circle-radius': 5,
				'circle-color': surface,
				'circle-stroke-color': accent,
				'circle-stroke-width': 2
			}
		});

		// Under the dashes, so the alarm colour is never diluted by its own halo.
		created.addLayer({
			id: 'gap-halo',
			type: 'line',
			source: 'gap',
			layout: { 'line-cap': 'round' },
			paint: { 'line-color': surface, 'line-width': 8, 'line-opacity': 0.85 }
		});

		created.addLayer({
			id: 'gap',
			type: 'line',
			source: 'gap',
			paint: { 'line-color': alarm, 'line-width': 3, 'line-dasharray': [2, 1.5] }
		});

		created.addLayer({
			id: 'gap-label',
			type: 'symbol',
			source: 'gap',
			layout: {
				'text-field': ['get', 'label'],
				'text-font': FONT,
				'text-size': 12,
				'symbol-placement': 'line-center',
				'text-offset': [0, -0.9]
			},
			paint: { 'text-color': alarm, 'text-halo-color': surface, 'text-halo-width': 2 }
		});

		created.addLayer({
			id: 'claim',
			type: 'circle',
			source: 'claim',
			paint: {
				'circle-radius': 9,
				'circle-color': alarm,
				'circle-stroke-color': surface,
				'circle-stroke-width': 3
			}
		});

		created.addLayer({
			id: 'claim-label',
			type: 'symbol',
			source: 'claim',
			layout: {
				'text-field': ['get', 'label'],
				'text-font': FONT,
				'text-size': 12,
				'text-offset': [0, 1.5],
				'text-anchor': 'top'
			},
			paint: { 'text-color': ink, 'text-halo-color': surface, 'text-halo-width': 2 }
		});
	}

	function refresh(created: maplibregl.Map) {
		(created.getSource('trail') as maplibregl.GeoJSONSource | undefined)?.setData(
			trailGeoJson(shown)
		);
		(created.getSource('fixes') as maplibregl.GeoJSONSource | undefined)?.setData(
			fixesGeoJson(shown)
		);
	}

	function fit(created: maplibregl.Map) {
		const bounds = new maplibregl.LngLatBounds();
		let any = false;
		if (claim) {
			bounds.extend([claim.claimed_location.lng, claim.claimed_location.lat]);
			any = true;
		}
		for (const fix of shown) {
			bounds.extend([fix.loc.lng, fix.loc.lat]);
			any = true;
		}
		if (!any) return;
		created.fitBounds(bounds, { padding: 64, maxZoom: 15, duration: 0 });
	}

	/**
	 * How wide the capture is, in pixels, before it goes into the packet.
	 *
	 * The packet is Letter with about six and a half inches of content, so this is a bit
	 * over 200 dpi — past what the paper can show. The raw canvas is the viewport times
	 * the device pixel ratio, which on this machine was 2048px for a 1024px map and about
	 * 1.5 MB of PNG. The server refuses anything over 3 MB (bible §15), so on a 2560px
	 * display the untouched capture would have crossed the limit and the download would
	 * have failed with a size error on exactly the screens most likely to be showing this
	 * to a courtroom. Downscaling is not an optimisation here, it is the thing that keeps
	 * the feature working.
	 */
	const CAPTURE_WIDTH = 1400;

	/**
	 * The canvas as a PNG data URI, read at the moment somebody asks for it.
	 *
	 * Returns null rather than throwing on a tainted canvas or a context the browser will
	 * not read back. The packet prints its text alternative in that case, which is why
	 * this is a fallback and not an error.
	 */
	function capture(created: maplibregl.Map): string | null {
		try {
			const source = created.getCanvas();
			if (source.width <= CAPTURE_WIDTH) return source.toDataURL('image/png');

			const scaled = document.createElement('canvas');
			scaled.width = CAPTURE_WIDTH;
			scaled.height = Math.round((source.height / source.width) * CAPTURE_WIDTH);
			const context = scaled.getContext('2d');
			if (!context) return source.toDataURL('image/png');
			context.drawImage(source, 0, 0, scaled.width, scaled.height);
			return scaled.toDataURL('image/png');
		} catch {
			return null;
		}
	}

	$effect(() => {
		if (!container) return;
		let created: maplibregl.Map;
		try {
			created = new maplibregl.Map({
				container,
				style: STYLE,
				center: claim
					? [claim.claimed_location.lng, claim.claimed_location.lat]
					: [-73.95, 40.72],
				zoom: 12,
				preserveDrawingBuffer: true,
				attributionControl: { compact: true }
			});
		} catch {
			// No WebGL, or a blocked context. The table below still says everything.
			failed = true;
			onReady?.(() => null);
			return;
		}

		created.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');

		/**
		 * No `error` handler nulling the capture.
		 *
		 * A first cut had one, on the reasoning that a half-drawn basemap should not go
		 * into an exhibit. MapLibre fires `error` for any number of survivable things —
		 * one tile that did not arrive, one glyph range that 404'd — so in practice every
		 * successful capture was immediately overwritten with null and every packet
		 * printed its text alternative. The evidence in this picture is the pin, the trail
		 * and the line between them, all of which are ours and none of which are tiles; a
		 * basemap missing a square is worth incomparably more than no map at all.
		 */
		created.on('load', () => {
			paint(created);
			fit(created);
			map = created;
			ready = true;
			onReady?.(() => capture(created));
		});

		return () => {
			created.remove();
			map = null;
			ready = false;
		};
	});

	/** The scrubber moves the window; the layers follow it. */
	$effect(() => {
		if (!ready || !map) return;
		refresh(map);
	});

	/** Same reason as `AdvocateMap`: a resize keeps centre and zoom, so re-frame the points. */
	$effect(() => {
		if (!ready || !map || !container || typeof ResizeObserver === 'undefined') return;
		const created = map;
		let first = true;
		const observer = new ResizeObserver(() => {
			if (first) {
				first = false;
				return;
			}
			created.resize();
			fit(created);
		});
		observer.observe(container);
		return () => observer.disconnect();
	});
</script>

<figure class="overflow-hidden rounded-card bg-surface">
	{#if failed}
		<p class="px-5 py-8 text-sm text-muted">{result.mapUnavailable}</p>
	{:else}
		<div bind:this={container} class="h-80 w-full sm:h-[26rem]" role="presentation"></div>

		{#if allFixes.length > 0 && claim}
			<div class="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-line px-4 py-3">
				<label class="flex flex-1 items-center gap-3 text-sm text-muted">
					<span class="shrink-0">{result.scrubberLabel}</span>
					<input
						type="range"
						min="15"
						max={TRAIL_MINUTES}
						step="15"
						bind:value={offset}
						class="min-w-32 flex-1 accent-ink"
						aria-label={result.scrubberHint}
					/>
					<span class="shrink-0 tabular-nums">± {offset} min</span>
				</label>
				<p class="text-sm text-muted">
					{shown.length} of {allFixes.length}
				</p>
			</div>
		{/if}
	{/if}

	<figcaption class="border-t border-line px-4 py-3 text-sm text-muted">
		{result.mapAlt}
		{#if claim && nearest}
			<span class="block pt-1 text-faint">
				{#if nearestCovers && nearest.t_end}
					Your nearest record is a stay from {formatNY(nearest.t)} to {formatNY(nearest.t_end)},
					which covers the time on the affidavit.
				{:else}
					Nearest record {formatNY(nearest.t)}.
				{/if}
			</span>
		{/if}
	</figcaption>
</figure>
