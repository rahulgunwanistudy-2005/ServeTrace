<script lang="ts">
	import ActionRow from '$lib/ui/ActionRow.svelte';
	import Callout from '$lib/ui/Callout.svelte';
	import Eyebrow from '$lib/ui/Eyebrow.svelte';
	import LimitationNote from '$lib/ui/LimitationNote.svelte';
	import { result } from '$copy/en';
</script>

<svelte:head><title>{result.findings} — ServeTrace</title></svelte:head>

<div class="st-shell st-shell-prose">
	<Eyebrow>Step 03 / 03</Eyebrow>
	<h1 class="st-display mt-5 text-3xl sm:text-5xl">{result.findings}</h1>
	<p class="mt-5 text-lg leading-relaxed text-muted">{result.comingSoon}</p>

	<div class="mt-8"><Callout tone="neutral">{result.comingSoonDetail}</Callout></div>

	<div class="mt-6 grid max-w-xl gap-3 sm:grid-cols-2">
		<ActionRow href="/demo" label="See a worked example" />
		<ActionRow href="/methodology" label="How the check works" />
	</div>

	<LimitationNote />
</div>
