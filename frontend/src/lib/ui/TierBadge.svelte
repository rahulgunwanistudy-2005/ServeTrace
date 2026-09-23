<script lang="ts">
	import type { ClaimTier } from '$lib/api/client';
	import { tierTone, toneClasses } from './tone';
	import { tierLabels } from '$copy/en';

	let { tier, size = 'md' }: { tier: ClaimTier; size?: 'sm' | 'md' } = $props();
</script>

<!-- The label carries the meaning; the colour only reinforces it. Bible §14 asks for
     WCAG AA, and that includes not encoding a verdict in a hue alone. -->
<span
	class="inline-flex items-center gap-1.5 rounded-full border font-semibold tracking-wide uppercase
	       {size === 'sm' ? 'px-2 py-0.5 text-[0.6875rem]' : 'px-3 py-1 text-xs'}
	       {toneClasses[tierTone(tier)]}"
>
	{tierLabels[tier]}
</span>
