<script lang="ts">
	/**
	 * Step 2: the person's own record of where they were. Bible §14.3, §13.
	 *
	 * The privacy promise is kept here or nowhere. The file is opened in a worker on this
	 * device, only the points within a few hours of a sworn moment are ever windowed out
	 * of it, and the line saying exactly how many of how many are leaving is on screen
	 * before the button that sends them. That line is not reassurance — it is the claim
	 * the privacy page makes, made checkable.
	 *
	 * Four doors, because people arrive with different things: a Timeline export, the
	 * photos on their phone (v1.1 — most people never had Timeline on), a bank statement,
	 * or nothing but their memory. The third is not a lesser path — a person
	 * who was at work all evening and can say so has given the engine a MANUAL interval,
	 * which is exactly what the visit test reads.
	 */
	import { ingestFile, type IngestProgress } from '$lib/ingest/client';
	import { IngestError, type LocationFix } from '$lib/ingest/types';
	import { api, ApiError } from '$lib/api/client';
	import Button from '$lib/ui/Button.svelte';
	import Callout from '$lib/ui/Callout.svelte';
	import Card from '$lib/ui/Card.svelte';
	import Eyebrow from '$lib/ui/Eyebrow.svelte';
	import FileDrop from '$lib/ui/FileDrop.svelte';
	import TextField from '$lib/ui/TextField.svelte';
	import { nyLocalToInstant } from '$lib/ingest/tz';
	import { parsePhotos, type PhotoSummary } from '$lib/ingest/parsers/photos';
	import { windowFixes } from '$lib/ingest/window';
	import { ingest } from '$copy/en';

	let {
		claims,
		fixes = $bindable([]),
		summary = $bindable(null)
	}: {
		/** The sworn moments, as ISO instants. Windowing is relative to these (bible §13). */
		claims: string[];
		fixes?: LocationFix[];
		summary?: {
			source: 'timeline' | 'statement' | 'manual' | 'photos';
			total: number;
			kept: number;
			sent: number;
			daysCovered: string[];
			claimedDaysMissing: string[];
			warnings: string[];
		} | null;
	} = $props();

	type Tile = 'timeline' | 'photos' | 'card' | 'manual';

	let tile = $state<Tile | null>(null);
	let busy = $state(false);
	let progress = $state<IngestProgress | null>(null);
	let failure = $state<string | null>(null);
	let controller: AbortController | null = null;

	// Manual entry. A day and two New York wall-clock times, rather than one datetime
	// field: `new Date('2025-06-12T08:00')` reads the *browser's* zone, which silently
	// moves a person's whole evening when they are not sitting in New York.
	let where = $state('');
	let day = $state('');
	let from = $state('');
	let until = $state('');
	let resolving = $state(false);

	const megabytes = (bytes: number) => `${(bytes / 1e6).toFixed(1)} MB`;

	// Photos (bible §13, v1.1). Names are kept for the list on this screen only; they are
	// never put on a fix and never leave the device.
	let photoNames = $state<string[]>([]);
	let photoSummary = $state<(PhotoSummary & { near: number }) | null>(null);

	async function readPhotos(files: File[]) {
		busy = true;
		failure = null;
		try {
			const parsed = await parsePhotos(files);
			const windowed = windowFixes(parsed.fixes, claims);
			photoNames = files.map((f) => f.name);
			photoSummary = { ...parsed, near: windowed.kept.length };
			fixes = [...fixes.filter((f) => f.kind !== 'photo'), ...windowed.kept];
			const warnings: string[] = [];
			if (parsed.withLocation === 0 && parsed.timeOnly > 0) warnings.push(ingest.photosNoLocation);
			else if (parsed.timeOnly > 0) warnings.push(ingest.photosSomeNoLocation(parsed.timeOnly));
			if (parsed.skipped > 0) warnings.push(ingest.photosSkipped(parsed.skipped));
			const assumedNear = windowed.kept.filter((f) => f.tz_assumed).length;
			if (assumedNear > 0) warnings.push(ingest.photosZoneAssumed(assumedNear));
			summary = {
				source: 'photos',
				total: parsed.fixes.length,
				kept: windowed.kept.length,
				sent: fixes.length,
				daysCovered: [],
				claimedDaysMissing: [],
				warnings
			};
		} catch (error) {
			failure = String(error);
		} finally {
			busy = false;
		}
	}

	function clearPhotos() {
		fixes = fixes.filter((f) => f.kind !== 'photo');
		photoNames = [];
		photoSummary = null;
		summary = null;
	}

	async function read(file: File, source: 'timeline' | 'statement') {
		busy = true;
		failure = null;
		progress = null;
		controller = new AbortController();
		try {
			const parsed = await ingestFile(file, {
				claims,
				signal: controller.signal,
				onProgress: (p) => (progress = p)
			});
			fixes = parsed.fixes;
			summary = {
				source,
				total: parsed.stats.total,
				kept: parsed.stats.kept,
				sent: parsed.fixes.length,
				daysCovered: parsed.stats.daysCovered,
				claimedDaysMissing: parsed.stats.claimedDaysMissing,
				warnings: parsed.warnings
			};
		} catch (error) {
			failure = error instanceof IngestError ? error.message : String(error);
		} finally {
			busy = false;
			controller = null;
		}
	}

	/**
	 * A typed-in interval, geocoded to a point.
	 *
	 * `MANUAL` with a `t_end` is an interval, and the engine's visit test reads it exactly
	 * as it reads a recorded stay — which is why "I was at work from 8 to 8" is worth as
	 * much here as a Timeline export covering the same hours.
	 */
	async function addManual() {
		if (!where.trim() || !day || !from || !until) return;
		const start = nyLocalToInstant(day, from);
		const end = nyLocalToInstant(day, until);
		if (!start || !end) {
			failure = ingest.manualBadTime;
			return;
		}
		resolving = true;
		failure = null;
		try {
			const resolved = await api.geocode(where.trim());
			if (!resolved.result) {
				failure = ingest.noneNearClaim;
				return;
			}
			const entry: LocationFix = {
				t: start.iso,
				t_end: end.iso,
				loc: resolved.result.location,
				accuracy_m: null,
				kind: 'manual',
				source: 'typed',
				label: resolved.result.label
			};
			fixes = [...fixes, entry];
			summary = {
				source: 'manual',
				total: fixes.length,
				kept: fixes.length,
				sent: fixes.length,
				daysCovered: [],
				claimedDaysMissing: [],
				warnings: []
			};
			where = '';
			from = '';
			until = '';
		} catch (error) {
			failure = error instanceof ApiError ? error.message : String(error);
		} finally {
			resolving = false;
		}
	}

	function removeManual(index: number) {
		fixes = fixes.filter((_, i) => i !== index);
		if (summary) summary = { ...summary, total: fixes.length, kept: fixes.length, sent: fixes.length };
	}
</script>

<section>
	<Eyebrow>{ingest.title}</Eyebrow>
	<p class="mt-3 leading-relaxed text-muted">{ingest.hint}</p>

	<div class="mt-6 grid gap-3 sm:grid-cols-2">
		{#each [['timeline', ingest.tiles.timeline, ingest.tileHints.timeline], ['photos', ingest.tiles.photos, ingest.tileHints.photos], ['card', ingest.tiles.card, ingest.tileHints.card], ['manual', ingest.tiles.manual, ingest.tileHints.manual]] as [id, label, hint] (id)}
			<button
				type="button"
				onclick={() => (tile = id as Tile)}
				aria-pressed={tile === id}
				class="rounded-card p-5 text-left transition-colors
				       {tile === id ? 'bg-raised shadow-card' : 'bg-surface hover:bg-surface-sunken'}"
			>
				<span class="block font-medium">{label}</span>
				<span class="mt-1.5 block text-sm leading-relaxed text-muted">{hint}</span>
			</button>
		{/each}
	</div>

	<p class="mt-4 text-sm text-muted">{ingest.privacyBadge}</p>

	{#if failure}
		<div class="mt-6"><Callout tone="contradicted" title="That did not work">{failure}</Callout></div>
	{/if}

	{#if tile === 'timeline'}
		<div class="mt-6 space-y-5">
			<div class="grid gap-4 sm:grid-cols-2">
				<Card>
					<Eyebrow>{ingest.howAndroid}</Eyebrow>
					<p class="mt-3 text-sm leading-relaxed text-muted">{ingest.howAndroidBody}</p>
				</Card>
				<Card>
					<Eyebrow>{ingest.howIphone}</Eyebrow>
					<p class="mt-3 text-sm leading-relaxed text-muted">{ingest.howIphoneBody}</p>
				</Card>
			</div>
			<FileDrop
				accept=".json,application/json"
				label={busy ? ingest.reading : ingest.chooseFile}
				hint={ingest.chooseFileHint}
				{busy}
				onfile={(file) => read(file, 'timeline')}
			/>
		</div>
	{:else if tile === 'photos'}
		<div class="mt-6 space-y-5">
			<!-- Metadata only: no <img>, no object URL, no thumbnail. A list of names is all
			     this screen ever shows of a photo (bible §13). -->
			<FileDrop
				accept="image/*,.heic,.heif"
				multiple
				label={busy ? ingest.photosReading : ingest.choosePhotos}
				hint={ingest.choosePhotosHint}
				{busy}
				onfiles={readPhotos}
			/>
			{#if photoSummary}
				<div class="rounded-card bg-surface p-5">
					<p class="font-medium" data-testid="photo-counts">
						{ingest.photosCounts(photoSummary.read, photoSummary.withLocation, photoSummary.near)}
					</p>
					<details class="mt-3 text-sm text-muted">
						<summary class="cursor-pointer">{ingest.photosChosen} ({photoNames.length})</summary>
						<ul class="mt-2 max-h-40 space-y-1 overflow-y-auto">
							{#each photoNames as name, index (name + index)}
								<li class="truncate">{name}</li>
							{/each}
						</ul>
					</details>
					<div class="mt-3">
						<Button variant="quiet" onclick={clearPhotos}>{ingest.photosClear}</Button>
					</div>
				</div>
			{/if}
		</div>
	{:else if tile === 'card'}
		<div class="mt-6">
			<FileDrop
				accept=".csv,text/csv"
				label={busy ? ingest.reading : ingest.chooseCsv}
				hint={ingest.chooseCsvHint}
				{busy}
				onfile={(file) => read(file, 'statement')}
			/>
		</div>
	{:else if tile === 'manual'}
		<div class="mt-6">
			<Card>
				<Eyebrow>{ingest.manualTitle}</Eyebrow>
				<div class="mt-5 grid gap-4 sm:grid-cols-2">
					<div class="sm:col-span-2">
						<TextField id="manual-where" label={ingest.manualWhere} bind:value={where} />
					</div>
					<div class="sm:col-span-2">
						<TextField id="manual-day" label={ingest.manualDay} bind:value={day} type="date" />
					</div>
					<TextField id="manual-from" label={ingest.manualFrom} bind:value={from} placeholder="08:00" />
					<TextField id="manual-to" label={ingest.manualTo} bind:value={until} placeholder="20:00" />
				</div>
				<div class="mt-5">
					<Button onclick={addManual} disabled={resolving || !where.trim() || !day || !from || !until}>
						{resolving ? ingest.resolving : ingest.manualAdd}
					</Button>
				</div>

				{#if fixes.length > 0}
					<ul class="mt-6 divide-y divide-line border-t border-line">
						{#each fixes as entry, index (entry.t + entry.loc.lat + index)}
							<li class="flex items-center justify-between gap-4 py-3 text-sm">
								<span class="min-w-0 truncate text-muted">{entry.label ?? entry.source}</span>
								<Button variant="quiet" onclick={() => removeManual(index)}>
									{ingest.manualRemove}
								</Button>
							</li>
						{/each}
					</ul>
				{:else}
					<p class="mt-5 text-sm text-faint">{ingest.manualNone}</p>
				{/if}
			</Card>
		</div>
	{/if}

	{#if busy && progress}
		<p class="mt-5 text-sm text-muted">
			{megabytes(progress.bytesRead)} of {megabytes(progress.totalBytes)} · {progress.fixes} points so far
		</p>
		<div class="mt-3">
			<Button variant="quiet" onclick={() => controller?.abort()}>{ingest.cancel}</Button>
		</div>
	{/if}

	{#if summary}
		<div class="mt-6 rounded-card bg-surface p-5">
			<!-- Bible §13: how much is leaving, said before it leaves. -->
			<p class="font-medium">{ingest.sending(summary.sent, summary.total)}</p>
			{#if summary.claimedDaysMissing.length > 0}
				<p class="mt-2 text-sm text-caution">{ingest.noneNearClaim}</p>
			{:else if summary.sent > 0}
				<p class="mt-2 text-sm text-muted">{ingest.coverageOk(summary.sent)}</p>
			{/if}
			{#each summary.warnings as warning (warning)}
				<p class="mt-2 text-sm text-caution">{warning}</p>
			{/each}
		</div>
	{/if}
</section>
