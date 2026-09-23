<script lang="ts">
	import { ingest, nav } from '$copy/en';
</script>

<svelte:head><title>{nav.privacy}</title></svelte:head>

<h1 class="text-2xl font-semibold tracking-tight sm:text-3xl">{nav.privacy}</h1>

<p class="mt-4 text-slate-700">{ingest.privacyBadge}</p>

<ul class="mt-6 list-disc space-y-2 pl-5 text-slate-700">
	<li>There is no account, no database and nothing stored on the server.</li>
	<li>Your location file is read in your browser. The full history never leaves your device.</li>
	<li>Only the few hours around the times the affidavit names are sent for analysis.</li>
	<li>Uploads are processed in memory and discarded.</li>
	<li>Logs record the request, not you: no names, no addresses, no coordinates.</li>
</ul>
