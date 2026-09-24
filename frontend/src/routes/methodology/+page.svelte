<script lang="ts">
	import published from '$lib/eval/published.json';
	import Callout from '$lib/ui/Callout.svelte';
	import Eyebrow from '$lib/ui/Eyebrow.svelte';
	import { deadlines, methodology as copy, nav, tiers, tierLabels } from '$copy/en';
	import { toneInk, type Tone } from '$lib/ui/tone';

	const p = published.engine_params;
	const pct = (n: number) => `${(n * 100).toFixed(n === 1 ? 0 : 1)}%`;

	const thresholds = [
		{ name: copy.thresholds.radius, value: `${p.match_radius_km * 1000} m`, why: copy.thresholds.radiusWhy },
		{ name: copy.thresholds.window, value: `± ${p.search_window_h} hours`, why: copy.thresholds.windowWhy },
		{ name: copy.thresholds.visitTolerance, value: `± ${p.visit_tolerance_min} min`, why: copy.thresholds.visitToleranceWhy },
		{ name: copy.thresholds.nearWindow, value: `± ${p.consistent_window_min} min`, why: copy.thresholds.nearWindowWhy },
		{ name: copy.thresholds.strong, value: `${p.v_strong_kmh} km/h`, why: copy.thresholds.strongWhy },
		{ name: copy.thresholds.moderate, value: `${p.v_moderate_kmh} km/h`, why: copy.thresholds.moderateWhy },
		{ name: copy.thresholds.age, value: `± ${p.desc_age_tolerance_y} years`, why: copy.thresholds.ageWhy },
		{ name: copy.thresholds.height, value: `± ${p.desc_height_tolerance_in} in`, why: copy.thresholds.heightWhy }
	];

	const TIERS = ['contradicted', 'consistent', 'no_data', 'inconclusive'] as const;
	// The generated file is typed as a plain object, and index access into it is
	// `possibly undefined` under strict TypeScript. Reading it through one helper keeps
	// the table markup readable and the strictness intact.
	const matrix = published.claim_matrix as Record<string, Record<string, number>>;
	const cell = (truth: string, pred: string) => matrix[truth]?.[pred] ?? 0;

	const advocate = published.advocate;
	const robustness = published.robustness;

	/**
	 * The three sweeps, each as a small table. The numbers come straight out of
	 * `published.json`, which the eval rewrites and a backend test refuses to let go
	 * stale — so nothing here can claim a figure the last run did not produce.
	 */
	const sweeps = [
		{
			title: copy.robustnessJitterTitle,
			body: copy.robustnessJitterBody,
			unit: 'm',
			levels: robustness.jitter.levels
		},
		{
			title: copy.robustnessReportedTitle,
			body: copy.robustnessReportedBody,
			unit: 'm',
			levels: robustness.jitter_reported.levels
		},
		{
			title: copy.robustnessGapsTitle,
			body: copy.robustnessGapsBody,
			unit: 'min',
			levels: robustness.gaps.levels
		}
	];
</script>

<svelte:head><title>{nav.methodology} — ServeTrace</title></svelte:head>

<div class="st-shell st-shell-prose">
	<Eyebrow>{nav.methodology}</Eyebrow>
	<h1 class="st-display mt-5 text-3xl sm:text-5xl">{copy.intro}</h1>

	<article class="prose-st mt-10">
		<Callout tone="neutral" title={copy.headlineTitle}>
			{copy.headlineBody(published.n_cases, published.false_accusations, pct(published.claim_accuracy))}
		</Callout>

	<h2>{copy.howTitle}</h2>
	<p>{copy.howBody}</p>
	<ol class="space-y-2 pl-5" style="list-style: decimal">
		{#each copy.howSteps as step (step)}<li class="text-muted">{step}</li>{/each}
	</ol>

	<h2>{copy.tiersTitle}</h2>
	<dl class="grid gap-3 sm:grid-cols-2">
		{#each TIERS as tier (tier)}
			<div class="rounded-card bg-surface p-5">
				<dt class="font-semibold">{tierLabels[tier]}</dt>
				<dd class="mt-1 text-sm leading-relaxed text-muted">{tiers[tier].meaning}</dd>
			</div>
		{/each}
	</dl>

	<h2>{copy.thresholdsTitle}</h2>
	<p>{copy.thresholdsBody(published.params_version)}</p>
	<div class="overflow-x-auto rounded-card bg-surface">
		<table class="w-full border-collapse text-left text-sm">
			<thead class="border-b border-line-strong">
				<tr class="st-eyebrow">
					<th scope="col" class="px-4 py-3 font-semibold">{copy.colThreshold}</th>
					<th scope="col" class="px-4 py-3 font-semibold">{copy.colValue}</th>
					<th scope="col" class="px-4 py-3 font-semibold">{copy.colWhy}</th>
				</tr>
			</thead>
			<tbody>
				{#each thresholds as row (row.name)}
					<tr class="border-b border-line last:border-0 align-top">
						<th scope="row" class="px-4 py-3 font-medium">{row.name}</th>
						<td class="px-4 py-3 font-semibold tabular-nums whitespace-nowrap">{row.value}</td>
						<td class="px-4 py-3 text-muted">{row.why}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>

	<h2>{copy.evalTitle}</h2>
	<p>{copy.evalBody(published.n_cases)}</p>

	<div class="grid gap-3 sm:grid-cols-3">
		{#each [
			{ label: copy.statFalse, value: String(published.false_accusations), tone: 'consistent' },
			{ label: copy.statClaim, value: pct(published.claim_accuracy), tone: 'accent' },
			{ label: copy.statOverall, value: pct(published.overall_accuracy), tone: 'accent' }
		] as stat (stat.label)}
			<div class="rounded-card bg-surface p-5">
				<p class="st-display text-4xl tabular-nums">{stat.value}</p>
				<p class="mt-2 text-sm leading-relaxed text-muted">{stat.label}</p>
			</div>
		{/each}
	</div>

	<h3>{copy.matrixTitle}</h3>
	<p>{copy.matrixBody}</p>
	<div class="overflow-x-auto rounded-card bg-surface">
		<table class="w-full border-collapse text-center text-sm">
			<thead class="border-b border-line-strong">
				<tr class="st-eyebrow">
					<th scope="col" class="px-3 py-3 text-left font-semibold">{copy.colTruth}</th>
					{#each TIERS as tier (tier)}
						<th scope="col" class="px-3 py-3 font-semibold">{tierLabels[tier]}</th>
					{/each}
				</tr>
			</thead>
			<tbody>
				{#each TIERS as truth (truth)}
					<tr class="border-b border-line last:border-0">
						<th scope="row" class="px-3 py-2.5 text-left font-medium">{tierLabels[truth]}</th>
						{#each TIERS as pred (pred)}
							<td
								class="px-3 py-2.5 tabular-nums {truth === pred
									? 'bg-consistent-quiet font-semibold text-consistent'
									: cell(truth, pred)
										? 'bg-caution-quiet text-caution'
										: 'text-muted'}"
							>
								{cell(truth, pred)}
							</td>
						{/each}
					</tr>
				{/each}
			</tbody>
		</table>
	</div>

	<h3>{copy.edgeTitle}</h3>
	<p>{copy.edgeBody}</p>
	<ul>
		{#each Object.entries(published.by_edge_kind) as [kind, row] (kind)}
			<li>
				<strong>{copy.edgeNames[kind as keyof typeof copy.edgeNames]}</strong> — {row.n} cases,
				{pct(row.claim_accuracy)} correct.
			</li>
		{/each}
	</ul>

	<h3>{copy.rulesTitle}</h3>
	<p>{copy.rulesBody}</p>
	<ul>
		{#each Object.entries(published.rule_recall) as [code, row] (code)}
			<li>
				<strong>{code}</strong> — {copy.ruleLine(row.seeded, row.found, row.extra, row.out_of_scope)}
			</li>
		{/each}
	</ul>

	<h3>{copy.descriptionTitle}</h3>
	<p>
		{copy.descriptionBody(
			published.description.mismatches_caught,
			published.description.mismatches_total,
			published.description.false_flags,
			published.description.n_skipped_by_method
		)}
	</p>

	<h2>{copy.advocateTitle}</h2>
	<p>{copy.advocateBody(advocate.n_records, advocate.n_servers)}</p>

	<dl class="not-prose my-6 grid gap-3 sm:grid-cols-3">
		{#each [
			{
				label: copy.advocateStatClean,
				value: `${advocate.clean_servers_accused} of ${advocate.clean_servers}`,
				tone: 'consistent'
			},
			{ label: copy.advocateStatPrecision, value: pct(advocate.precision), tone: 'accent' },
			{ label: copy.advocateStatRecall, value: pct(advocate.recall), tone: 'accent' }
		] as stat (stat.label)}
			<div class="rounded-card bg-surface p-5">
				<dt class="text-sm leading-relaxed text-muted">{stat.label}</dt>
				<dd class="st-display mt-2 text-3xl tabular-nums {toneInk[stat.tone as Tone]}">
					{stat.value}
				</dd>
			</div>
		{/each}
	</dl>

	<p>{copy.advocatePrecisionNote}</p>
	<p>{copy.advocateRuntime(advocate.runtime_ms, advocate.n_records)}</p>

	<h2>{copy.robustnessTitle}</h2>
	<p>{copy.robustnessBody(robustness.n_cases)}</p>

	{#each sweeps as sweep (sweep.title)}
		<h3>{sweep.title}</h3>
		<p>{sweep.body}</p>
		<div class="not-prose my-5 overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-line text-left">
						<th class="py-2 pr-4 font-medium">{copy.robustnessColumnLevel}</th>
						<th class="py-2 pr-4 text-right font-medium">{copy.robustnessColumnPrecision}</th>
						<th class="py-2 pr-4 text-right font-medium">{copy.robustnessColumnRecall}</th>
						<th class="py-2 text-right font-medium">{copy.robustnessColumnFalse}</th>
					</tr>
				</thead>
				<tbody>
					{#each sweep.levels as level (level.value)}
						<tr class="border-b border-line/60">
							<td class="py-2 pr-4 tabular-nums">{level.value} {sweep.unit}</td>
							<td class="py-2 pr-4 text-right tabular-nums">{pct(level.precision ?? 0)}</td>
							<td class="py-2 pr-4 text-right tabular-nums">{pct(level.recall ?? 0)}</td>
							<td
								class="py-2 text-right tabular-nums {level.false_accusations
									? toneInk.contradicted
									: ''}"
							>
								{level.false_accusations}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/each}

	<h2>{copy.limitsTitle}</h2>
	<ul>
		{#each copy.limits as limit (limit)}<li>{limit}</li>{/each}
	</ul>

	<h2>{copy.lawTitle}</h2>
	<p>{deadlines.cplr5015}</p>
	<p>{deadlines.cplr317}</p>
	<p>{deadlines.traverse}</p>

		<h2>{copy.sourcesTitle}</h2>
		<ul>
			{#each copy.sources as source (source.url)}
				<li><a href={source.url} rel="noreferrer noopener" target="_blank">{source.title}</a></li>
			{/each}
		</ul>
	</article>
</div>
