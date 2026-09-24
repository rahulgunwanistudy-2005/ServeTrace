<script lang="ts">
	/**
	 * Bible §16: every demo screen says so, in as many words — and only in words.
	 *
	 * There is no badge. A pill reading `DEMO` next to a sentence that already says the
	 * people and cases are invented was the same disclosure made twice, and the badge was
	 * the half carrying no information. What is left is the half that does.
	 *
	 * On `/advocate` this stands where the section's eyebrow would be, so it takes the
	 * same muted weight rather than shouting.
	 */
	import { demo } from '$copy/en';

	let { invert = false }: { invert?: boolean } = $props();
</script>

<p class="text-sm {invert ? 'text-panel-muted' : 'text-muted'}">
	{demo.provenance}
</p>
