<script lang="ts">
	/**
	 * A drop target that is also a real file input.
	 *
	 * Drag-and-drop is the fast path and never the only path: the input underneath is a
	 * genuine `<input type="file">`, so the keyboard, a screen reader and a phone all
	 * reach it the ordinary way. The label wraps it, which is what makes the whole
	 * rectangle clickable without any JavaScript standing in for the browser.
	 */
	let {
		accept,
		hint,
		label,
		busy = false,
		onfile
	}: {
		accept: string;
		label: string;
		hint?: string;
		busy?: boolean;
		onfile: (file: File) => void;
	} = $props();

	let over = $state(false);

	function take(list: FileList | null | undefined) {
		const file = list?.[0];
		if (file) onfile(file);
	}

	function onDrop(event: DragEvent) {
		event.preventDefault();
		over = false;
		if (!busy) take(event.dataTransfer?.files);
	}
</script>

<!-- Dashed while empty and solid-ink while a file is over it: the state change is a
     shape change, not only a tint, so it survives a colour-blind reader. -->
<label
	ondragover={(event) => {
		event.preventDefault();
		over = true;
	}}
	ondragleave={() => (over = false)}
	ondrop={onDrop}
	class="flex cursor-pointer flex-col items-center gap-3 rounded-card border px-6 py-12
	       text-center transition-colors
	       {over
		? 'border-solid border-accent bg-accent-quiet shadow-card'
		: 'border-dashed border-line-strong bg-surface hover:bg-sunken'}
	       {busy ? 'pointer-events-none opacity-60' : ''}"
>
	<span
		aria-hidden="true"
		class="grid size-11 place-items-center rounded-full bg-accent text-on-accent"
	>
		<svg viewBox="0 0 24 24" class="size-5" fill="none">
			<path
				d="M12 16V4m0 0L8 8m4-4 4 4M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"
				stroke="currentColor"
				stroke-width="1.8"
				stroke-linecap="round"
				stroke-linejoin="round"
			/>
		</svg>
	</span>
	<span class="st-display-sm text-lg text-ink">{label}</span>
	{#if hint}<span class="max-w-md text-sm leading-relaxed text-muted">{hint}</span>{/if}
	<input
		type="file"
		{accept}
		disabled={busy}
		class="sr-only"
		onchange={(event) => take(event.currentTarget.files)}
	/>
</label>
