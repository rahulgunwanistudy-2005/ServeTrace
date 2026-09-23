<script lang="ts">
	import type { Severity } from '$lib/api/client';
	import { severityTone, toneClasses } from './tone';
	import { severityLabels } from '$copy/en';

	let { severity }: { severity: Severity } = $props();
</script>

<span
	class="inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-[0.6875rem]
	       font-semibold tracking-[0.07em] uppercase {toneClasses[severityTone(severity)]}"
>
	{severityLabels[severity]}
</span>
