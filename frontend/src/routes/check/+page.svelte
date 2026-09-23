<script lang="ts">
	import ActionRow from '$lib/ui/ActionRow.svelte';
	import Callout from '$lib/ui/Callout.svelte';
	import Eyebrow from '$lib/ui/Eyebrow.svelte';
	import StepHeader from '$lib/ui/StepHeader.svelte';
	import { steps, upload } from '$copy/en';
</script>

<svelte:head><title>{steps.one.title} — ServeTrace</title></svelte:head>

<div class="st-shell st-shell-prose">
	<StepHeader step={1} total={3} title={steps.one.title} hint={steps.one.hint} />

	<p class="text-lg leading-relaxed text-muted">{upload.prompt}</p>

	<details class="group mt-6 rounded-card bg-surface">
		<summary
			class="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 px-5
			       font-medium [&::-webkit-details-marker]:hidden"
		>
			{upload.whereDoIGetIt}
			<span
				aria-hidden="true"
				class="grid size-6 shrink-0 place-items-center rounded-full border border-line-strong
				       transition-transform group-open:rotate-45"
			>
				<svg viewBox="0 0 16 16" class="size-3" fill="none">
					<path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
				</svg>
			</span>
		</summary>
		<p class="px-5 pb-5 leading-relaxed text-muted">{upload.whereDoIGetItBody}</p>
	</details>

	<div class="mt-10 border-t border-line pt-8">
		<Eyebrow>Not built yet</Eyebrow>
		<div class="mt-4"><Callout tone="neutral">{upload.comingSoon}</Callout></div>
		<div class="mt-4 max-w-sm"><ActionRow href="/methodology" label="Read the methodology" /></div>
	</div>
</div>
