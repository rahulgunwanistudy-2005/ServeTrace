<script lang="ts">
	/** Bible §16: every demo screen says so, in as many words. */
	import { demo } from '$copy/en';

	let { invert = false }: { invert?: boolean } = $props();
</script>

<p
	class="inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold
	       tracking-[0.07em] uppercase
	       {invert
		? 'bg-panel-ink/15 text-panel-ink ring-1 ring-panel-line'
		: 'border border-caution/30 bg-caution-quiet text-caution'}"
>
	<span aria-hidden="true" class="size-1.5 rounded-full bg-current"></span>
	{demo.chip}
</p>
