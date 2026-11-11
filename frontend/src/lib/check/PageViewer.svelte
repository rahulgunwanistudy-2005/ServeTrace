<script lang="ts">
	/**
	 * The pages of the upload, beside the fields read off them. Build prompt §4.3.
	 *
	 * The person checks a value by looking at the words it came from, so the viewer goes
	 * to the page of whichever field is selected and, on a PDF with a text layer, draws a
	 * box around those words. A photo has no word positions, so the quote is printed under
	 * the page instead: a box we guessed at would be worse than none.
	 *
	 * The previews are small JPEGs the server made in memory for this one response. They
	 * are shown from `data:` URLs and never written anywhere.
	 */
	import type { PagePreview, PageType } from '$lib/api/client';
	import { boxStyle } from './review';
	import { upload } from '$copy/en';

	let {
		previews,
		pageTypes,
		page = $bindable(0),
		bbox = null,
		quote = null,
		active = false
	}: {
		previews: PagePreview[];
		pageTypes: PageType[];
		page?: number;
		/** PDF points on `page`: [x0, top, x1, bottom]. */
		bbox?: number[] | null;
		quote?: string | null;
		/** A field is selected, so say something about where it is even when we cannot. */
		active?: boolean;
	} = $props();

	const ZOOMS = [1, 1.5, 2, 3] as const;
	let zoomStep = $state(0);
	const zoom = $derived(ZOOMS[zoomStep] ?? 1);

	let frame = $state<HTMLDivElement | null>(null);
	let sheet = $state<HTMLDivElement | null>(null);

	const shown = $derived(previews.find((p) => p.index === page) ?? previews[0] ?? null);
	const box = $derived(shown && bbox ? boxStyle(bbox, shown) : null);
	const review = upload.review;

	/** Bring the box into view whenever it moves, at whatever zoom the person chose. */
	$effect(() => {
		const target = box;
		if (!frame || !sheet || !target) return;
		void zoom;
		const top = (target.top / 100) * sheet.clientHeight;
		const left = (target.left / 100) * sheet.clientWidth;
		frame.scrollTo({
			top: Math.max(0, top - frame.clientHeight / 3),
			left: Math.max(0, left - frame.clientWidth / 4),
			behavior: 'smooth'
		});
	});

	/** Drag to pan. A pointer, so it is the same on a mouse and a finger. */
	let drag: { x: number; y: number; left: number; top: number } | null = null;
	function down(event: PointerEvent) {
		if (!frame || zoom === 1 || event.pointerType === 'touch') return;
		drag = { x: event.clientX, y: event.clientY, left: frame.scrollLeft, top: frame.scrollTop };
		frame.setPointerCapture(event.pointerId);
	}
	function move(event: PointerEvent) {
		if (!frame || !drag) return;
		frame.scrollLeft = drag.left - (event.clientX - drag.x);
		frame.scrollTop = drag.top - (event.clientY - drag.y);
	}
	function up() {
		drag = null;
	}
</script>

{#if shown}
	<div class="rounded-card border border-line bg-surface">
		<div class="flex items-center justify-between gap-2 border-b border-line px-3 py-2 text-sm">
			<span class="text-muted">{review.page(shown.index + 1, previews.length)}</span>
			<div class="flex items-center gap-1">
				<button
					type="button"
					class="grid size-9 place-items-center rounded-control border border-line-strong disabled:opacity-40"
					aria-label={review.zoomOut}
					disabled={zoomStep === 0}
					onclick={() => (zoomStep = Math.max(0, zoomStep - 1))}>−</button
				>
				<button
					type="button"
					class="min-h-9 rounded-control border border-line-strong px-2.5 text-xs"
					onclick={() => (zoomStep = 0)}>{review.fit}</button
				>
				<button
					type="button"
					class="grid size-9 place-items-center rounded-control border border-line-strong disabled:opacity-40"
					aria-label={review.zoomIn}
					disabled={zoomStep === ZOOMS.length - 1}
					onclick={() => (zoomStep = Math.min(ZOOMS.length - 1, zoomStep + 1))}>+</button
				>
			</div>
		</div>

		<!-- The page itself. Scrolls both ways when zoomed; a drag pans it. -->
		<div
			bind:this={frame}
			class="h-[52vh] overflow-auto bg-sunken lg:h-[64vh] {zoom > 1 ? 'cursor-grab' : ''}"
			onpointerdown={down}
			onpointermove={move}
			onpointerup={up}
			onpointercancel={up}
			role="presentation"
		>
			<div bind:this={sheet} class="relative mx-auto" style="width: {zoom * 100}%">
				<img
					src={shown.image}
					alt={review.page(shown.index + 1, previews.length)}
					class="block w-full select-none"
					draggable="false"
				/>
				{#if box}
					<div
						class="pointer-events-none absolute rounded-sm border-2 border-caution bg-caution/15
						       shadow-[0_0_0_9999px_rgba(0,0,0,0.12)]"
						style="left:{box.left}%;top:{box.top}%;width:{box.width}%;height:{box.height}%"
						data-testid="evidence-box"
					></div>
				{/if}
			</div>
		</div>

		{#if active && !box}
			<p class="border-t border-line px-4 py-3 text-sm leading-relaxed" aria-live="polite">
				{#if quote}
					<span class="text-muted">{review.onThisPage}</span>
					<span class="font-medium">“{quote}”</span>
				{:else}
					<span class="text-muted">{review.notOnPage}</span>
				{/if}
			</p>
		{/if}

		{#if previews.length > 1}
			<ol class="flex gap-2 overflow-x-auto border-t border-line p-2" aria-label={review.pagesTitle}>
				{#each previews as preview (preview.index)}
					<li class="shrink-0">
						<button
							type="button"
							onclick={() => (page = preview.index)}
							aria-current={preview.index === shown.index ? 'page' : undefined}
							class="flex w-20 flex-col items-stretch gap-1 rounded-control border p-1 text-left
							       {preview.index === shown.index ? 'border-accent' : 'border-line'}"
						>
							<img src={preview.image} alt="" class="aspect-[17/22] w-full object-cover object-top" />
							<span class="truncate text-[11px] leading-tight text-muted">
								{preview.index + 1} · {upload.pageTypes[pageTypes[preview.index] ?? 'other']}
							</span>
						</button>
					</li>
				{/each}
			</ol>
		{/if}
	</div>
{/if}
