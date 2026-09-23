<script lang="ts">
	/**
	 * Claimed service point and the user's own trail around it. Bible §14.5. Session 4.
	 *
	 * `preserveDrawingBuffer` is required so the evidence packet can capture the canvas
	 * (bible §15). A text-alternative table sits beside this for accessibility.
	 */
	import { result } from '$copy/en';

	let { claimedAt }: { claimedAt?: string } = $props();
</script>

<figure class="rounded-lg border border-slate-200 p-4">
	<div class="grid h-64 place-items-center bg-slate-50 text-sm text-slate-500">
		Map — session 4{claimedAt ? ` · ${claimedAt}` : ''}
	</div>
	<figcaption class="mt-2 text-sm text-slate-600">{result.mapAlt}</figcaption>
</figure>
