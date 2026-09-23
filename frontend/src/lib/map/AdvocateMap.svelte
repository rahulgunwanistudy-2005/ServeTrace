<script lang="ts">
	/**
	 * One process server's filings, with the sequences that do not add up drawn in red.
	 *
	 * The whole argument of advocate mode is visible in one picture: a tight cluster of
	 * doors in one borough, and then a line shooting across the city and back inside four
	 * minutes. That line is the product.
	 *
	 * Three decisions worth stating:
	 *
	 * - **Red is never the only signal.** Bible §14 forbids colour alone, so an impossible
	 *   edge is a thicker, dashed line with a label carrying the distance and the speed,
	 *   and the same pairs are listed in text beside the map and in the alternative table.
	 * - **The ordinary day is drawn too**, in quiet grey. A map showing only the red edges
	 *   would make four flagged steps look like the server's whole week, which is the
	 *   opposite of honest — the point is that four steps out of sixty do not fit.
	 * - **`preserveDrawingBuffer`** so the canvas can be captured for a report
	 *   (bible §15). It costs a little performance on every frame and is the only way to
	 *   read pixels back after a paint.
	 */
	import maplibregl from 'maplibre-gl';
	import 'maplibre-gl/dist/maplibre-gl.css';

	import type { ImpossiblePair, ServerReport, ServiceRecord } from '$lib/api/client';
	import { advocate } from '$copy/en';
	import { resolvePalette } from './color';
	import { formatDateTime, formatKm, formatSpeed } from '$lib/ui/tone';

	let { report, records }: { report: ServerReport; records: ServiceRecord[] } = $props();

	const STYLE = 'https://tiles.openfreemap.org/styles/liberty';
	const NYC: [number, number] = [-73.95, 40.72];

	/**
	 * A font the tile server actually serves.
	 *
	 * MapLibre's default `text-font` is `Open Sans Regular`, and OpenFreeMap serves only
	 * the Noto family, so leaving it unset asks for glyphs that 404. That failure is not
	 * contained: the worker errors the whole *tile*, and a tile belongs to a source rather
	 * than to a layer — so an unlabelled symbol layer silently took down the two line
	 * layers sharing its source, and the map drew its pins with no red edges between them
	 * and no error in the console.
	 */
	const FONT = ['Noto Sans Bold'];

	/**
	 * The map's colours, taken from the same tokens the page uses.
	 *
	 * `lib/map/color.ts` converts them, because `app.css` defines the palette in `oklch`
	 * and MapLibre parses its own style colours and understands none of it. The fallbacks
	 * are the light-scheme values, so a browser that refuses the conversion still gets a
	 * readable map rather than an empty one.
	 */
	const TOKENS = {
		ink: { name: '--st-muted', fallback: '#6d6a65' },
		surface: { name: '--st-surface', fallback: '#f0efec' },
		alarm: { name: '--st-contradicted', fallback: '#b42318' },
		accent: { name: '--st-accent', fallback: '#211f1c' }
	} as const;

	type Palette = Record<keyof typeof TOKENS, string>;

	let container = $state<HTMLDivElement | null>(null);
	let map = $state<maplibregl.Map | null>(null);
	let ready = $state(false);

	const ordered = $derived(
		[...records].sort((a, b) => a.at.localeCompare(b.at) || (a.address ?? '').localeCompare(b.address ?? ''))
	);

	function pointsGeoJson(rows: ServiceRecord[]) {
		return {
			type: 'FeatureCollection' as const,
			features: rows.map((row, index) => ({
				type: 'Feature' as const,
				geometry: { type: 'Point' as const, coordinates: [row.loc.lng, row.loc.lat] },
				properties: {
					order: index + 1,
					at: row.at,
					address: row.address ?? '',
					outcome: row.outcome ?? ''
				}
			}))
		};
	}

	/** The server's whole route, so the flagged steps are seen against an ordinary week. */
	function routeGeoJson(rows: ServiceRecord[]) {
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
									coordinates: rows.map((row) => [row.loc.lng, row.loc.lat])
								},
								properties: {}
							}
						]
		};
	}

	function pairsGeoJson(pairs: ImpossiblePair[]) {
		return {
			type: 'FeatureCollection' as const,
			features: pairs.map((pair) => ({
				type: 'Feature' as const,
				geometry: {
					type: 'LineString' as const,
					coordinates: [
						[pair.a.loc.lng, pair.a.loc.lat],
						[pair.b.loc.lng, pair.b.loc.lat]
					]
				},
				properties: {
					// Just the speed. The full sentence with the distance and the gap is in the
					// list below, and a label long enough to carry all three is longer than the
					// line it sits on — MapLibre then places it badly or not at all.
					label: formatSpeed(pair.required_speed_kmh)
				}
			}))
		};
	}

	function paint(created: maplibregl.Map) {
		const { ink, surface, alarm, accent } = resolvePalette(TOKENS);

		created.addSource('route', { type: 'geojson', data: routeGeoJson(ordered) });
		created.addSource('filings', { type: 'geojson', data: pointsGeoJson(ordered) });
		created.addSource('pairs', { type: 'geojson', data: pairsGeoJson(report.impossible_pairs) });

		created.addLayer({
			id: 'route',
			type: 'line',
			source: 'route',
			paint: { 'line-color': ink, 'line-width': 2, 'line-opacity': 0.55 }
		});

		// Drawn under the dashes so the alarm colour is never diluted by the halo.
		created.addLayer({
			id: 'pairs-halo',
			type: 'line',
			source: 'pairs',
			layout: { 'line-cap': 'round' },
			paint: { 'line-color': surface, 'line-width': 8, 'line-opacity': 0.85 }
		});
		created.addLayer({
			id: 'pairs',
			type: 'line',
			source: 'pairs',
			layout: { 'line-cap': 'round' },
			paint: { 'line-color': alarm, 'line-width': 3.5, 'line-dasharray': [1.4, 1] }
		});
		created.addLayer({
			id: 'pairs-label',
			type: 'symbol',
			source: 'pairs',
			layout: {
				'symbol-placement': 'line-center',
				'text-field': ['get', 'label'],
				'text-font': FONT,
				// Placed along the line but never rotated with it. A cross-borough hop is
				// usually close to vertical on this map, and a number printed sideways is a
				// number nobody reads.
				'text-rotation-alignment': 'viewport',
				'text-size': 12,
				'text-offset': [0, -1.1],
				// A handful of edges at most, and each one is the point of the picture, so
				// they are drawn even where they crowd each other. Collision avoidance here
				// would silently hide the very thing the map is for.
				'text-allow-overlap': true,
				'text-ignore-placement': true
			},
			paint: { 'text-color': alarm, 'text-halo-color': surface, 'text-halo-width': 2 }
		});

		created.addLayer({
			id: 'filings',
			type: 'circle',
			source: 'filings',
			paint: {
				'circle-radius': 5,
				'circle-color': accent,
				'circle-stroke-width': 1.5,
				'circle-stroke-color': surface
			}
		});
	}

	function fit(created: maplibregl.Map, rows: ServiceRecord[]) {
		if (rows.length === 0) return;
		const bounds = new maplibregl.LngLatBounds();
		for (const row of rows) bounds.extend([row.loc.lng, row.loc.lat]);
		created.fitBounds(bounds, { padding: 48, maxZoom: 14, duration: 0 });
	}

	$effect(() => {
		if (!container) return;
		const created = new maplibregl.Map({
			container,
			style: STYLE,
			center: NYC,
			zoom: 10,
			preserveDrawingBuffer: true,
			attributionControl: { compact: true }
		});
		created.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
		created.on('load', () => {
			paint(created);
			fit(created, ordered);
			map = created;
			ready = true;
		});

		// A filing is a point on a specific day; the popup says which, because a week of
		// them in one borough is otherwise an undifferentiated cluster.
		created.on('click', 'filings', (event) => {
			const feature = event.features?.[0];
			if (!feature) return;
			// A feature's properties come back from the style as loosely typed data, so the
			// popup is built from whatever is actually present rather than from what this
			// component put there — a missing field must not throw inside a click handler.
			const props = (feature.properties ?? {}) as Record<string, string | undefined>;
			const line = [
				props.at ? formatDateTime(props.at) : null,
				props.address,
				props.outcome
			].filter(Boolean);
			if (line.length === 0) return;
			new maplibregl.Popup({ closeButton: false, offset: 10 })
				.setLngLat(event.lngLat)
				.setText(line.join(' · '))
				.addTo(created);
		});
		created.on('mouseenter', 'filings', () => {
			created.getCanvas().style.cursor = 'pointer';
		});
		created.on('mouseleave', 'filings', () => {
			created.getCanvas().style.cursor = '';
		});

		return () => {
			created.remove();
			map = null;
			ready = false;
		};
	});

	/**
	 * Re-fit when the container's width changes.
	 *
	 * MapLibre resizes its own canvas, but it keeps the centre and the zoom — so a map
	 * fitted to a week of filings on a desktop is cropped to a few of them on a phone,
	 * which is the one thing this map must not do. What is being framed is a set of
	 * points, not a viewport, so the framing has to be recomputed.
	 */
	$effect(() => {
		if (!ready || !map || !container || typeof ResizeObserver === 'undefined') return;
		const created = map;
		const rows = ordered;
		let first = true;
		const observer = new ResizeObserver(() => {
			// The observer fires once on attach with the size it already has.
			if (first) {
				first = false;
				return;
			}
			created.resize();
			fit(created, rows);
		});
		observer.observe(container);
		return () => observer.disconnect();
	});

	/**
	 * Repaint when the operating system switches between light and dark.
	 *
	 * The tokens are read once, at load, because reading them is not free — so the map
	 * would otherwise keep a dark palette on a page that has gone light, which on the
	 * `surface`-coloured halo behind every red edge is the difference between a readable
	 * label and an unreadable one.
	 */
	function repaint(created: maplibregl.Map, palette: Palette) {
		created.setPaintProperty('route', 'line-color', palette.ink);
		created.setPaintProperty('pairs-halo', 'line-color', palette.surface);
		created.setPaintProperty('pairs', 'line-color', palette.alarm);
		created.setPaintProperty('pairs-label', 'text-color', palette.alarm);
		created.setPaintProperty('pairs-label', 'text-halo-color', palette.surface);
		created.setPaintProperty('filings', 'circle-color', palette.accent);
		created.setPaintProperty('filings', 'circle-stroke-color', palette.surface);
	}

	$effect(() => {
		if (!ready || !map || typeof window === 'undefined') return;
		const created = map;
		const query = window.matchMedia('(prefers-color-scheme: dark)');
		const onChange = () => repaint(created, resolvePalette(TOKENS));
		query.addEventListener('change', onChange);
		return () => query.removeEventListener('change', onChange);
	});

	// Selecting a different server replaces the data rather than the map: rebuilding the
	// canvas would refetch every tile for a pan across the same city.
	$effect(() => {
		if (!ready || !map) return;
		(map.getSource('route') as maplibregl.GeoJSONSource | undefined)?.setData(
			routeGeoJson(ordered)
		);
		(map.getSource('filings') as maplibregl.GeoJSONSource | undefined)?.setData(
			pointsGeoJson(ordered)
		);
		(map.getSource('pairs') as maplibregl.GeoJSONSource | undefined)?.setData(
			pairsGeoJson(report.impossible_pairs)
		);
		fit(map, ordered);
	});
</script>

<figure class="overflow-hidden rounded-card bg-surface">
	<div
		bind:this={container}
		class="h-[22rem] w-full sm:h-[28rem]"
		role="img"
		aria-label="{advocate.mapTitle}. {advocate.mapAlternative} below."
	></div>
	<figcaption class="border-t border-line px-4 py-3 text-sm text-muted">
		{advocate.mapHint}
	</figcaption>
</figure>
