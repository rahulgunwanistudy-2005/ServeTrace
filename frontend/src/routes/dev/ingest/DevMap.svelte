<script lang="ts">
	/**
	 * A raw look at whatever was just parsed. Development only — the real result map is
	 * `lib/map/ResultMap.svelte`, which session 7 builds.
	 *
	 * Visits are drawn larger than path points because a visit asserts a stretch of time
	 * and a path point asserts an instant, and on a map they otherwise look equally strong.
	 */
	import maplibregl from 'maplibre-gl';
	import 'maplibre-gl/dist/maplibre-gl.css';

	import type { LocationFix } from '$lib/ingest/types';

	let { fixes }: { fixes: LocationFix[] } = $props();

	const STYLE = 'https://tiles.openfreemap.org/styles/liberty';
	const NYC: [number, number] = [-73.95, 40.75];

	let container = $state<HTMLDivElement | null>(null);
	let map: maplibregl.Map | null = null;

	function toGeoJson(list: LocationFix[]) {
		return {
			type: 'FeatureCollection' as const,
			features: list.map((fix) => ({
				type: 'Feature' as const,
				geometry: { type: 'Point' as const, coordinates: [fix.loc.lng, fix.loc.lat] },
				properties: { kind: fix.kind, t: fix.t, label: fix.label ?? '' }
			}))
		};
	}

	$effect(() => {
		if (!container || map) return;
		const created = new maplibregl.Map({
			container,
			style: STYLE,
			center: NYC,
			zoom: 10,
			// Bible §15: the evidence packet captures the canvas, so the real map needs this.
			// Kept here too, so the dev view behaves like the one that matters.
			preserveDrawingBuffer: true
		});
		created.addControl(new maplibregl.NavigationControl(), 'top-right');
		created.on('load', () => {
			created.addSource('fixes', { type: 'geojson', data: toGeoJson(fixes) });
			created.addLayer({
				id: 'fixes',
				type: 'circle',
				source: 'fixes',
				paint: {
					'circle-radius': ['case', ['==', ['get', 'kind'], 'visit'], 7, 4],
					'circle-color': [
						'match',
						['get', 'kind'],
						'visit',
						'#1d4ed8',
						'transaction',
						'#7c3aed',
						'manual',
						'#059669',
						'#60a5fa'
					],
					'circle-stroke-width': 1,
					'circle-stroke-color': '#ffffff'
				}
			});
			map = created;
		});

		return () => {
			created.remove();
			map = null;
		};
	});

	$effect(() => {
		const source = map?.getSource('fixes') as maplibregl.GeoJSONSource | undefined;
		if (!source) return;
		source.setData(toGeoJson(fixes));
		if (fixes.length === 0) return;

		const bounds = new maplibregl.LngLatBounds();
		for (const fix of fixes) bounds.extend([fix.loc.lng, fix.loc.lat]);
		map?.fitBounds(bounds, { padding: 48, maxZoom: 15, duration: 0 });
	});
</script>

<div bind:this={container} class="h-96 w-full rounded-lg border border-slate-200"></div>
