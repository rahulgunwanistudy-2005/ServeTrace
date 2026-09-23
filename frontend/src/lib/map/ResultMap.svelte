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

<figure class="overflow-hidden rounded-card bg-surface">
	<div class="grid h-72 place-items-center bg-sunken text-sm text-faint">
		Map — session 4{claimedAt ? ` · ${claimedAt}` : ''}
	</div>
	<figcaption class="border-t border-line px-4 py-3 text-sm text-muted">{result.mapAlt}</figcaption>
</figure>
