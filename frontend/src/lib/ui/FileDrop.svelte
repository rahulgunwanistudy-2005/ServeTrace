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

<label
	ondragover={(event) => {
		event.preventDefault();
		over = true;
	}}
	ondragleave={() => (over = false)}
	ondrop={onDrop}
	class="flex cursor-pointer flex-col items-center gap-2 rounded-card border-2 border-dashed
	       px-6 py-10 text-center transition-colors
	       {over ? 'border-accent bg-accent-quiet' : 'border-line-strong bg-surface hover:bg-sunken'}
	       {busy ? 'pointer-events-none opacity-60' : ''}"
>
	<svg viewBox="0 0 24 24" class="size-7 text-accent" fill="none" aria-hidden="true">
		<path
			d="M12 16V4m0 0L8 8m4-4 4 4M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"
			stroke="currentColor"
			stroke-width="1.7"
			stroke-linecap="round"
			stroke-linejoin="round"
		/>
	</svg>
	<span class="font-medium text-ink">{label}</span>
	{#if hint}<span class="max-w-md text-sm leading-relaxed text-muted">{hint}</span>{/if}
	<input
		type="file"
		{accept}
		disabled={busy}
		class="sr-only"
		onchange={(event) => take(event.currentTarget.files)}
	/>
</label>
