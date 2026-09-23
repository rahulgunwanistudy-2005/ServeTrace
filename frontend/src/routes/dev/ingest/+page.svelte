<script lang="ts">
	/**
	 * Ingest workbench. Development only (see `+page.ts`).
	 *
	 * Drop a Timeline export in and see what came out of it: how many points, which days
	 * are covered, what was skipped and why, and where the points actually are. This is the
	 * S3 acceptance gate, and it is also the fastest way to find out what a real export
	 * from a real phone does to the parsers.
	 */
	import Button from '$lib/ui/Button.svelte';
	import { ingestFile, type IngestProgress } from '$lib/ingest/client';
	import { formatNY, formatNYTime } from '$lib/ingest/tz';
	import { IngestError, type IngestStats, type LocationFix } from '$lib/ingest/types';
	import DevMap from './DevMap.svelte';

	let claimText = $state('');
	let busy = $state(false);
	let progress = $state<IngestProgress | null>(null);
	let stats = $state<IngestStats | null>(null);
	let warnings = $state<string[]>([]);
	let fixes = $state<LocationFix[]>([]);
	let failure = $state<{ code: string; message: string } | null>(null);
	let elapsedMs = $state(0);
	let controller: AbortController | null = null;

	const claims = $derived(
		claimText
			.split('\n')
			.map((line) => line.trim())
			.filter((line) => line.length > 0)
	);

	const kinds = $derived(
		[...new Set(fixes.map((f) => f.kind))]
			.map((kind) => `${kind}: ${fixes.filter((f) => f.kind === kind).length}`)
			.join(' · ')
	);

	async function onFile(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;

		busy = true;
		failure = null;
		warnings = [];
		fixes = [];
		stats = null;
		progress = null;
		controller = new AbortController();
		const started = performance.now();

		try {
			const result = await ingestFile(file, {
				claims,
				signal: controller.signal,
				onProgress: (p) => (progress = p)
			});
			fixes = result.fixes;
			stats = result.stats;
			warnings = result.warnings;
		} catch (error) {
			failure =
				error instanceof IngestError
					? { code: error.code, message: error.message }
					: { code: 'unknown', message: String(error) };
		} finally {
			elapsedMs = performance.now() - started;
			busy = false;
			controller = null;
			input.value = '';
		}
	}

	function cancel() {
		controller?.abort();
	}

	function megabytes(bytes: number): string {
		return `${(bytes / 1e6).toFixed(1)} MB`;
	}
</script>

<svelte:head><title>Ingest workbench</title></svelte:head>

<h1 class="text-2xl font-semibold tracking-tight">Ingest workbench</h1>
<p class="mt-2 text-slate-700">
	Development only. Drop a Google Timeline export (Android or iOS) and see what the parsers
	make of it. Nothing here is sent anywhere.
</p>

<label class="mt-6 block text-sm font-medium" for="claims">
	Claimed times, one ISO instant per line (optional — with them, only ±3h around each is kept)
</label>
<textarea
	id="claims"
	bind:value={claimText}
	rows="2"
	placeholder="2025-06-12T19:42:00-04:00"
	class="mt-1 w-full rounded-lg border border-slate-300 p-2 font-mono text-sm"
></textarea>

<div class="mt-4 flex items-center gap-3">
	<input
		type="file"
		accept=".json,application/json"
		onchange={onFile}
		disabled={busy}
		class="text-sm"
	/>
	{#if busy}
		<Button variant="secondary" onclick={cancel}>Cancel</Button>
	{/if}
</div>

{#if busy && progress}
	<p class="mt-4 text-sm text-slate-600">
		Read {megabytes(progress.bytesRead)} of {megabytes(progress.totalBytes)} · {progress.fixes} points
		kept so far
	</p>
{/if}

{#if failure}
	<p class="mt-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-900">
		<strong class="font-mono">{failure.code}</strong> — {failure.message}
	</p>
{/if}

{#if stats}
	<section class="mt-6 grid gap-2 rounded-lg border border-slate-200 p-4 text-sm">
		<p>
			<strong>{stats.total.toLocaleString('en-US')}</strong> distinct points in the file{stats.totalIsApproximate
				? ' (at least)'
				: ''}, <strong>{stats.kept.toLocaleString('en-US')}</strong> kept, {stats.skipped} unreadable.
		</p>
		<p>{kinds}</p>
		<p>
			Covers {stats.firstAt ? formatNY(stats.firstAt) : '—'} to {stats.lastAt
				? formatNY(stats.lastAt)
				: '—'} across {stats.daysCovered.length} day{stats.daysCovered.length === 1 ? '' : 's'}.
		</p>
		{#if stats.claimedDaysMissing.length > 0}
			<p class="text-amber-800">
				Claimed days not in this export: {stats.claimedDaysMissing.join(', ')}
			</p>
		{/if}
		<p class="text-slate-500">
			{megabytes(stats.bytesRead)} read in {(elapsedMs / 1000).toFixed(2)} s ({(
				stats.bytesRead /
				1e6 /
				(elapsedMs / 1000)
			).toFixed(1)} MB/s)
		</p>
	</section>
{/if}

{#each warnings as warning}
	<p class="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
		{warning}
	</p>
{/each}

{#if fixes.length > 0}
	<div class="mt-6">
		<DevMap {fixes} />
	</div>

	<h2 class="mt-6 text-lg font-semibold">First 50 points</h2>
	<div class="mt-2 overflow-x-auto">
		<table class="w-full text-left text-sm">
			<thead class="border-b border-slate-200">
				<tr>
					<th class="py-1 pr-4">When (NY)</th>
					<th class="py-1 pr-4">Until</th>
					<th class="py-1 pr-4">Kind</th>
					<th class="py-1 pr-4">Lat</th>
					<th class="py-1 pr-4">Lng</th>
					<th class="py-1 pr-4">±m</th>
					<th class="py-1">Label</th>
				</tr>
			</thead>
			<tbody class="font-mono text-xs">
				{#each fixes.slice(0, 50) as fix (fix.t + fix.loc.lat + fix.loc.lng + fix.kind)}
					<tr class="border-b border-slate-100">
						<td class="py-1 pr-4">{formatNY(fix.t)}</td>
						<td class="py-1 pr-4">{fix.t_end ? formatNYTime(fix.t_end) : ''}</td>
						<td class="py-1 pr-4">{fix.kind}</td>
						<td class="py-1 pr-4">{fix.loc.lat.toFixed(5)}</td>
						<td class="py-1 pr-4">{fix.loc.lng.toFixed(5)}</td>
						<td class="py-1 pr-4">{fix.accuracy_m ?? ''}</td>
						<td class="py-1">{fix.label ?? ''}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{/if}
