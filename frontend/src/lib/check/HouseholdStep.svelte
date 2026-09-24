<script lang="ts">
	/**
	 * Step 3: who else lives there. Bible §14.4, §11.2.
	 *
	 * Optional, and the page says so plainly, because it is only read by one rule: when an
	 * affidavit claims the papers were left with a person of suitable age and discretion,
	 * the engine compares that description to this roster. With nobody listed the check
	 * simply does not run that comparison, and everything else is unaffected.
	 *
	 * Bible §3 forbids photographs and any inference from them, so this asks for the three
	 * things a stranger at a door could have estimated — and nothing else.
	 */
	import type { HouseholdMember } from '$lib/case/store.svelte';
	import Button from '$lib/ui/Button.svelte';
	import Card from '$lib/ui/Card.svelte';
	import CheckBox from '$lib/ui/CheckBox.svelte';
	import Eyebrow from '$lib/ui/Eyebrow.svelte';
	import TextField from '$lib/ui/TextField.svelte';
	import { household as copy } from '$copy/en';

	let { members = $bindable([]) }: { members?: HouseholdMember[] } = $props();

	let label = $state('');
	let sex = $state<'unknown' | 'male' | 'female' | 'other'>('unknown');
	let age = $state('');
	let height = $state('');
	let isDefendant = $state(false);

	function add() {
		if (!label.trim()) return;
		members = [
			...members,
			{
				label: label.trim(),
				sex: sex === 'unknown' ? null : sex,
				age: age ? Number(age) : null,
				height_in: height ? Number(height) : null,
				is_defendant: isDefendant
			}
		];
		label = '';
		sex = 'unknown';
		age = '';
		height = '';
		isDefendant = false;
	}
</script>

<section>
	<Eyebrow>{copy.title}</Eyebrow>
	<p class="mt-3 max-w-2xl leading-relaxed text-muted">{copy.intro}</p>

	<div class="mt-6">
		<Card>
			<div class="grid gap-4 sm:grid-cols-2">
				<div class="sm:col-span-2">
					<TextField id="hh-label" label={copy.label} bind:value={label} hint={copy.labelHint} />
				</div>

				<div>
					<label class="block text-sm font-medium" for="hh-sex">{copy.sex}</label>
					<select
						id="hh-sex"
						bind:value={sex}
						class="mt-1.5 min-h-11 w-full rounded-control border border-line-strong bg-raised px-3
						       text-sm text-ink"
					>
						{#each Object.entries(copy.sexOptions) as [value, text] (value)}
							<option {value}>{text}</option>
						{/each}
					</select>
				</div>

				<TextField id="hh-age" label={copy.age} bind:value={age} />
				<div class="sm:col-span-2">
					<TextField id="hh-height" label={copy.height} bind:value={height} hint={copy.heightHint} />
				</div>
			</div>

			<div class="mt-5">
				<CheckBox id="hh-me" bind:checked={isDefendant} label={copy.isDefendant} />
			</div>

			<div class="mt-5">
				<Button onclick={add} disabled={!label.trim()}>{copy.add}</Button>
			</div>
		</Card>
	</div>

	{#if members.length > 0}
		<ul class="mt-5 divide-y divide-line rounded-card bg-surface px-5">
			{#each members as member, index (member.label + index)}
				<li class="flex items-center justify-between gap-4 py-4">
					<div class="min-w-0">
						<p class="truncate font-medium">
							{member.label}{#if member.is_defendant}<span class="ml-2 text-sm font-normal text-muted"
									>({copy.isDefendant})</span
								>{/if}
						</p>
						<p class="mt-0.5 text-sm text-muted">
							{[member.sex, member.age ? `${member.age}` : null, member.height_in ? `${member.height_in} in` : null]
								.filter(Boolean)
								.join(' · ') || '—'}
						</p>
					</div>
					<Button variant="quiet" onclick={() => (members = members.filter((_, i) => i !== index))}>
						{copy.remove}
					</Button>
				</li>
			{/each}
		</ul>
	{:else}
		<p class="mt-5 text-sm text-faint">{copy.none}</p>
	{/if}
</section>
