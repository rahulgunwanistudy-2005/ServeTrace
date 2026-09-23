/**
 * Every user-facing string. Nothing in a component may hardcode English.
 *
 * Two rules govern what may be written here:
 *   - Result language follows bible §6. ServeTrace never says anyone lied or committed
 *     fraud. It says data conflicts.
 *   - Any legal statement must trace to a row of bible §5, and carries its L-id.
 */

export const LIMITATION_LINE =
	'Location history shows where your phone was, not proof of where you were. A judge decides what happened.';

export const DRAFT_BANNER =
	'DRAFT — not legal advice. Review with the NYC Civil Court Help Center or a legal aid organization.';

export const site = {
	name: 'ServeTrace',
	tagline: 'They swore they served you. Your phone says otherwise.'
} as const;

export const landing = {
	headline: 'Frozen bank account? Never got court papers?',
	sub: "Check whether the process server's sworn story matches where you really were.",
	startCheck: 'Start check',
	seeDemo: 'See a demo',
	advocate: "I'm a legal advocate",
	privacyBadge: 'Your location file is read on this device.',
	steps: [
		{
			title: 'Your court papers',
			body: 'Upload the affidavit of service from your court file. We read the names, the address and the time the server swore to.'
		},
		{
			title: 'Where you were',
			body: 'Bring your own location history — Google Timeline, a card statement, or just type it in. It is read on your phone, not ours.'
		},
		{
			title: 'What we found',
			body: 'We compare the two and show you the numbers, with a packet and a draft affidavit you can take to court.'
		}
	],
	/** Bible §2: the technical angle, said plainly and only once. */
	angleTitle: 'The check a bank runs on your card, run on an affidavit',
	angleBody:
		"When a card is used in two cities twenty minutes apart, a bank\u2019s fraud checks flag it: nobody travels that fast. ServeTrace asks the same question of a sworn statement. If an affidavit puts a server at your door at 7:42 PM and your phone was fourteen kilometres away at 7:39, getting there would have taken about 171 km/h. That is the whole idea, and as far as we can tell nobody had pointed it at an affidavit of service before.",
	trustTitle: 'What this is, and what it is not',
	trustPoints: [
		'It is a way to see whether your own records line up with what was sworn.',
		'It never says anyone lied. It says whether the data conflicts, and shows you the numbers.',
		'It will tell you when your data supports the affidavit, or settles nothing at all.',
		'It is not legal advice, and nothing here is sent to a court on your behalf.'
	]
} as const;

export const steps = {
	one: { title: 'Your court papers', hint: 'Upload the affidavit of service.' },
	two: { title: 'Where were you?', hint: 'Bring your own location history.' },
	three: { title: 'Who lives with you?', hint: 'Optional. It helps check the description.' }
} as const;

export const upload = {
	prompt: 'Upload the affidavit of service (photo or PDF).',
	whereDoIGetIt: 'Where do I get this?',
	whereDoIGetItBody:
		'It is in the court file for your case. The Civil Court Help Center can show you how to look it up and print it.',
	confirmCheckbox: 'These details match my papers',
	comingSoon:
		'Uploading and reading your papers arrives with the wizard. The engine behind this check already works — the Methodology page shows exactly what it does and how it scores.',
	lowConfidence: 'Please check this one — we were not sure we read it correctly.',
	knowledgeQuestion: 'When did you first find out about the judgment?'
} as const;

export const ingest = {
	tiles: {
		timeline: 'Google Timeline',
		card: 'Card or bank statement',
		manual: 'Type it in'
	},
	privacyBadge:
		'Your location file is read on this device. We only use the few hours around the claimed time.',
	/** Bible §13: the user is told exactly how much leaves the device, before it leaves. */
	sending: (sent: number, total: number) =>
		`Sending ${sent} of ${total} location points (only around the claimed times).`,
	reading: 'Reading your file on this device…',
	covers: (first: string, last: string) => `Your export covers ${first} to ${last}.`,
	points: (n: number, approximate: boolean) =>
		`${approximate ? 'More than ' : ''}${n.toLocaleString('en-US')} location point${n === 1 ? '' : 's'}.`
} as const;

/**
 * Everything ingest says when something is wrong with a file. Keyed by the code the
 * pipeline raises, so a component switches on the code and never on the sentence.
 */
export const ingestErrors = {
	unsupported_format:
		'We could not recognise that file. ServeTrace reads Google Timeline exports (the Timeline.json or location-history.json from your phone) and card statements saved as CSV.',
	file_too_large: 'That file is too large to read in the browser.',
	empty_file: 'That file is empty.',
	malformed_json: 'We could not read that file. It may be damaged or only partly downloaded.',
	no_fixes:
		'We recognised that as a Timeline export, but could not read any locations out of it.',
	cancelled: 'Reading that file was stopped.',
	truncated: 'That file ends in the middle of a record, so we could not finish reading it.',
	oversizedRecord:
		'One entry in that file is far larger than any location record should be, so we stopped reading it.',
	unreadableRecord:
		'One entry in that file was not readable, so we stopped rather than guess at it.'
} as const;

/**
 * What ingest tells the user about a file it *could* read. Every one of these is a thing
 * left out or assumed, said plainly: a check that silently drops data is worse than no
 * check, because the user cannot tell the difference.
 */
export const ingestWarnings = {
	missingDays: (days: string[]) =>
		days.length === 1
			? `Your export does not include ${days[0]}, which is the day on the affidavit.`
			: `Your export does not include these days from the affidavit: ${days.join(', ')}.`,
	unreadableEntries: (n: number) =>
		`${n.toLocaleString('en-US')} entr${n === 1 ? 'y' : 'ies'} in that file could not be read and ${n === 1 ? 'was' : 'were'} left out.`,
	tooManyPoints: (kept: number) =>
		`That file holds more location points than we can show at once, so we kept the first ${kept.toLocaleString('en-US')}.`,
	tooManyNearClaim: (kept: number) =>
		`There were more points around the claimed times than we send in one go, so we kept the ${kept.toLocaleString('en-US')} closest to them.`,
	csvNeedsAddress:
		'Without an address column we cannot tell where a purchase happened, so none of these rows can be used.',
	csvRowsSkipped: (n: number) =>
		`${n} row${n === 1 ? '' : 's'} had no date, time or address we could read, so ${n === 1 ? 'it was' : 'they were'} left out.`,
	csvMisshapenLines:
		'Some lines in that file were not laid out like the rest and were skipped.',
	manualIncomplete: (n: number) =>
		`${n} entr${n === 1 ? 'y needs' : 'ies need'} a date, a start and end time, and an address.`,
	/** The autumn fold: the same wall clock happens twice, and we say which one we used. */
	clocksChanged: (n: number) =>
		n === 1
			? 'One of those times falls on the night the clocks change, where the same time happens twice. We used the earlier one.'
			: `${n} of those times fall on the night the clocks change, where the same time happens twice. We used the earlier one.`,
	addressesNotFound: (n: number) =>
		`We could not find ${n} of those addresses on the map, so ${n === 1 ? 'it was' : 'they were'} left out. ServeTrace only knows New York City addresses.`
} as const;

export type IngestErrorKey = keyof typeof ingestErrors;

/** Bible §6. The headline for each tier, and the honest framing of each. */
export const tiers = {
	contradicted: {
		headline: 'Your location data conflicts with the affidavit.',
		meaning:
			'Your own records put you somewhere else when the server swore they served you.'
	},
	consistent: {
		headline: 'Your location data is consistent with the affidavit.',
		meaning:
			'Your records put you at or near that address around that time. That does not mean the service was proper, but this particular check does not help you.'
	},
	no_data: {
		headline: "We don't have location data for that time.",
		meaning: 'Your file has no usable points near the claimed time, so this check cannot run.'
	},
	inconclusive: {
		headline: "Your data doesn't settle this either way.",
		meaning: 'There is data, but it neither matches nor conflicts under our thresholds.'
	}
} as const;

/** Short labels for the four tiers, for badges and tables. Bible §6. */
export const tierLabels = {
	contradicted: 'Conflicts',
	consistent: 'Consistent',
	no_data: 'No data',
	inconclusive: 'Unsettled'
} as const;

export const severityLabels = {
	strong: 'Strong',
	moderate: 'Worth checking',
	info: 'Note'
} as const;

/**
 * What each L-id from bible §5 is called on screen. These are names of the provisions the
 * engine encodes, not statements of what they say: the statement is the finding's own
 * text, which comes from the engine's copy module.
 */
export const legalRefs = {
	L1: 'CPLR 308(1) — handing the papers to you in person',
	L2: 'CPLR 308(2) — leaving the papers with someone and mailing a copy',
	L3: 'CPLR 308(4) — taping the papers to the door and mailing a copy',
	L4: 'What courts commonly expect before papers may be taped to a door',
	L5: 'CPLR 5015(a)(4) — reopening a judgment for lack of jurisdiction',
	L6: 'CPLR 317 — the deadline to ask the court to reopen',
	L7: 'NYC Admin Code § 20-410 — process servers must record GPS'
} as const;

/**
 * Bible §14.5: the one sentence under the headline, carrying the key number.
 *
 * It states only what the engine measured. When there is no distance there is no
 * sentence, because a reassuring line with nothing behind it is worse than silence.
 */
export function verdictLine(
	claimedAt: string,
	nearestKm: number | null | undefined,
	requiredSpeed: number | null | undefined
): string {
	const when = new Date(claimedAt).toLocaleTimeString('en-US', {
		timeZone: 'America/New_York',
		hour: 'numeric',
		minute: '2-digit'
	});
	if (nearestKm === null || nearestKm === undefined) {
		return `We have no location data for ${when}.`;
	}
	const distance =
		nearestKm < 1
			? `${Math.round(nearestKm * 1000).toLocaleString('en-US')} metres`
			: `${nearestKm.toFixed(1)} km`;
	const where =
		nearestKm < 0.3
			? `At ${when} your phone was at that address, within ${distance}.`
			: `At ${when} your phone was ${distance} from that address.`;
	if (!requiredSpeed) return where;
	return `${where} Getting there in time would have taken about ${Math.round(requiredSpeed).toLocaleString('en-US')} km/h.`;
}

export const result = {
	mapAlt: 'Map of the claimed service address and your recorded locations around that time.',
	mapTableCaption: 'The same information as the map, as a table.',
	claimedPin: 'Claimed service location',
	yourTrail: 'Where your phone was',
	whatThisMeans: 'What this means',
	whatItDoesNot: "What this doesn't mean",
	findings: 'What we found',
	noFindings: 'Nothing in your papers or your data raised a flag.',
	basedOn: 'Based on:',
	claimService: 'The service',
	claimAttempt: 'An earlier attempt',
	colClaim: 'Claim',
	colWhen: 'When (New York time)',
	colDistance: 'Your phone',
	colVerdict: 'Verdict',
	claimsTitle: 'Every moment the affidavit swears to',
	downloadPacket: 'Download evidence packet',
	downloadAffidavit: 'Download draft affidavit',
	getHelp: 'Where to get help',
	askForGps:
		"Ask the plaintiff's lawyer for the server's GPS record.",
	/** Bible §5 L7. */
	askForGpsWhy:
		'Licensed New York City process servers must carry a device that electronically records the GPS location, date and time of every service and attempt.',
	comingSoon: 'Your result will appear here once you have finished the three steps.',
	comingSoonDetail:
		'The verdict card, the map with a time scrubber, the findings list and the downloads arrive with the wizard. The engine that decides all of it is built and tested.'
} as const;

export const deadlines = {
	title: 'Your deadline',
	fromLearning: 'One year from finding out',
	fromEntry: 'Five years from the judgment',
	/** Bible §5 L6. */
	cplr317:
		'If you were served in any way other than in person, and you did not personally get notice in time to defend the case, you may be able to ask the court to reopen it within one year of learning about the judgment, and no more than five years after it was entered.',
	/** Bible §5 L5. */
	cplr5015:
		'A judgment can be reopened when the court did not have jurisdiction, which includes service that was not done properly. There is no stated one-year limit for that ground, but act promptly.',
	traverse:
		'When the facts of service are disputed, the court may hold a hearing about service, called a traverse hearing.'
} as const;


/**
 * The Methodology page (bible §14.7). Every number on that page comes from
 * `lib/eval/published.json`, which the eval writes; nothing here states a figure, only
 * how to say one. A test in the backend suite fails if that file goes stale.
 */
export const methodology = {
	intro:
		'How the check works, the numbers behind every threshold it uses, how it scores against two hundred synthetic cases, and where it cannot help.',
	headlineTitle: 'The number that matters most',
	headlineBody: (cases: number, falseAccusations: number, accuracy: string) =>
		`Across ${cases} synthetic cases, ServeTrace told ${falseAccusations} people their data conflicted with an affidavit when it did not. It read the claimed moment correctly in ${accuracy} of them.`,

	howTitle: 'How the check works',
	howBody:
		'Everything below is ordinary arithmetic. No model decides anything: the only place ServeTrace uses one is reading the fields off your uploaded papers, and you confirm those before anything is compared.',
	howSteps: [
		'The affidavit names a place and a time. That address is turned into a point on the map.',
		'Your location file is read in your browser, and only the points within a few hours of that time are ever sent.',
		'If your phone recorded a stay that covers the claimed time, we measure how far that stay was from the address.',
		'Otherwise we take the nearest point before the claimed time and the nearest after it, and work out how fast you would have had to travel to be at that door.',
		'The affidavit is also checked against the New York rules about mailing, filing and repeated attempts.',
		'Every finding carries the numbers it came from, so you or a judge can check the arithmetic.'
	],

	tiersTitle: 'The four answers it can give',

	thresholdsTitle: 'Thresholds',
	thresholdsBody: (version: string) =>
		`Every number the engine uses lives in one versioned file, stamped on every result and every document as ${version}. They are deliberately generous towards the affidavit: the engine only disagrees with a sworn statement when your own data leaves no room for doubt.`,
	colThreshold: 'Threshold',
	colValue: 'Value',
	colWhy: 'Why',
	thresholds: {
		radius: 'Match radius',
		radiusWhy:
			'A point this close to the address counts as being there. A phone indoors, a building with two entrances and an address pinned to a block all move a point by this much. A fix\u2019s own stated accuracy is added on top.',
		window: 'Search window',
		windowWhy:
			'Only points this close in time to the claim are considered, or ever sent off your device.',
		visitTolerance: 'Visit tolerance',
		visitToleranceWhy:
			'A recorded stay counts as covering the claimed time if the claim falls this close to either end of it.',
		nearWindow: 'Consistency window',
		nearWindowWhy:
			'A single point inside the match radius this close to the claimed time settles it as consistent, whatever else the data says.',
		strong: 'Impossible speed',
		strongWhy:
			'Door to door across New York, above this is not a journey. A contradiction here is reported as strong.',
		moderate: 'Unlikely speed',
		moderateWhy:
			'Between this and the line above, the trip is possible in a car and unlikely on foot, so it is reported as worth checking rather than as proof.',
		age: 'Age tolerance',
		ageWhy:
			'A description is widened by this much at both ends before anyone is called a mismatch. A stranger guessing an age through a doorway is guessing.',
		height: 'Height tolerance',
		heightWhy: 'The same allowance for a height estimated at a glance.'
	},

	evalTitle: 'How it scores',
	evalBody: (cases: number) =>
		`The engine is scored against ${cases} synthetic cases. The generator that builds them records where it put the person and never asks the engine, so the labels and the thing being measured are independent. Scoring an engine against labels the engine produced would measure nothing.`,
	statFalse: 'False contradictions',
	statClaim: 'Claimed moment read correctly',
	statOverall: 'Whole-case answer',

	matrixTitle: 'Confusion matrix',
	matrixBody:
		'Rows are what the generator built. Columns are what the engine answered about the claimed moment of service.',
	colTruth: 'Built as',

	edgeTitle: 'The awkward cases, counted separately',
	edgeBody:
		'These are the cases where a threshold is either honest or it is not, so they are reported on their own rather than averaged away.',
	edgeNames: {
		dst_fold: 'The night the clocks go back, when the stated time means two moments',
		radius_inside: 'A single point just inside the match radius',
		radius_outside_walkable: 'A single point just outside it, but an easy walk away',
		visit_boundary: 'A claim falling moments outside a recorded stay'
	},

	rulesTitle: 'The paperwork rules',
	rulesBody:
		'The generator deliberately builds some affidavits to break each New York rule, and records which. Every one of those, where the rule applies, is caught.',
	ruleLine: (seeded: number, found: number, extra: number, outOfScope: number) => {
		const parts = [`${found} of ${seeded} deliberate cases caught`];
		if (extra) parts.push(`${extra} more found in cases that were not built to break it`);
		if (outOfScope)
			parts.push(`${outOfScope} seeded on a kind of service this rule does not cover`);
		return `${parts.join(', ')}.`;
	},

	descriptionTitle: 'The description check',
	descriptionBody: (caught: number, total: number, falseFlags: number, skipped: number) =>
		`Where the affidavit says papers were handed to someone, ${caught} of ${total} descriptions that matched nobody in the household were flagged, with ${falseFlags} households wrongly told that nobody matched. ${skipped} cases were not scored, because papers taped to a door were not handed to anyone and there is nobody to compare.`,

	limitsTitle: 'Where this cannot help',
	limits: [
		'Location history shows where your phone was. It is not proof of where you were, and a judge decides what happened.',
		'If your phone was off, out of battery or not recording, the check has nothing to work with and says so.',
		'A consistent result does not mean the service was proper. It means this particular check does not help you.',
		'Only New York City Civil Court consumer credit cases, and only service on a person under CPLR 308(1), 308(2) and 308(4).',
		'Nothing here is legal advice, and ServeTrace never predicts whether you will win.'
	],

	lawTitle: 'The law this encodes',

	sourcesTitle: 'Sources',
	sources: [
		{
			title: 'Pew — How Debt Collectors Are Transforming the Business of State Courts (2020)',
			url: 'https://www.pew.org/en/research-and-analysis/reports/2020/05/how-debt-collectors-are-transforming-the-business-of-state-courts'
		},
		{
			title: 'New York Focus — 5 key takeaways on sewer service (June 2025)',
			url: 'https://nysfocus.com/2025/06/11/nyc-process-servers-investigation'
		},
		{
			title: 'CPLR 308 — the text of the service statute',
			url: 'https://codes.findlaw.com/ny/civil-practice-law-and-rules/cvp-sect-308/'
		},
		{
			title: 'Due diligence under CPLR 308(5), a practitioner guide',
			url: 'https://jtnylaw.com/2020/04/cplr-3085/'
		},
		{
			title: 'Vacating a default judgment in NYC Civil Court (CPLR 5015 and 317)',
			url: 'https://forms.runsensible.com/blog/general-article/vacate-a-default-judgment-nyc/'
		},
		{
			title: 'NYC DCWP — process server rules, GPS records and the advocate complaint form',
			url: 'https://www.nyc.gov/site/dca/businesses/info-process-servers.page'
		},
		{
			title: '6 RCNY § 2-233b — the GPS recording requirement',
			url: 'https://codelibrary.amlegal.com/codes/newyorkcity/latest/NYCrules/0-0-0-149059'
		}
	]
} as const;

export const advocate = {
	title: 'Advocate mode',
	sub: 'Load many service records from one process server and look for sequences nobody could have travelled.',
	upload: 'Upload a CSV or XLSX of service records.',
	mapColumns: 'Match your columns',
	riskTable: 'Servers, ranked',
	impossiblePairs: 'Sequences that do not add up',
	exportCsv: 'Export CSV',
	exportPdf: 'Export report',
	/** Bible §5 L7. */
	dcwpNote:
		'The NYC Department of Consumer and Worker Protection accepts complaints about process servers from legal advocates.',
	gpsTitle: 'Ask for the GPS record',
	comingSoon:
		'Batch analysis — a spreadsheet of service records, ranked servers and a map of the sequences nobody could have travelled — arrives in a later session.'
} as const;

/** The Privacy page (bible §14.7, §16). Every claim here is one the code actually keeps. */
export const privacy = {
	intro:
		'ServeTrace is built so that the thing you are most worried about sharing never leaves your phone.',
	shortVersionTitle: 'The short version',
	shortVersion:
		'There is no account, no database and nothing stored on our server. Your location history is read in your browser, and only the few hours around the times on the affidavit are ever sent anywhere.',

	whatStaysTitle: 'What stays on your device',
	whatStays: [
		'Your whole location file. A Google Timeline export can cover years; it is opened, read and windowed in your browser.',
		'Everything on a bank or card statement except the address: the merchant and the amount never leave the page.',
		'Anything you type and then change your mind about before pressing the button.'
	],

	whatLeavesTitle: 'What is sent, and when',
	whatLeaves: [
		'The affidavit you upload, so its fields can be read. It is processed in memory and not kept.',
		'Addresses, one at a time, to look up where they are on the map.',
		'Only the location points within three hours of a time the affidavit names. The screen tells you how many of your points that is before you send them.',
		'The household details you choose to enter, which are optional.'
	],

	serverTitle: 'What the server does',
	server: [
		'It holds nothing. There is no case id, because there is nothing to come back for.',
		'Uploads are handled in memory and discarded when the request ends.',
		'Logs record the request, not you: a request id, the route, the status and how long it took. No names, no addresses, no coordinates, no document text.',
		'The analysis itself is ordinary arithmetic on our own servers. Your location points are never sent to any third party.'
	],

	mapTitle: 'One thing worth knowing about the map',
	mapBody:
		'The map is drawn with tiles from OpenFreeMap, and it pans to your own points. No location data is sent to them, but which tiles a browser asks for does reveal roughly which part of the city is being looked at. That is a real inference and it seemed better to say so than to leave it out.',

	notDoneTitle: 'What ServeTrace never does',
	notDone: [
		'It never analyses a photograph of a person, and never infers anything from an appearance.',
		'It never files anything, emails anyone or contacts a court on your behalf.',
		'It never tells you whether you will win, and it is not legal advice.',
		'It never says anyone lied. It says whether your data conflicts, and shows you the numbers.'
	]
} as const;

export const errors = {
	bad_input: 'We could not read that file.',
	upload_too_large: 'That file is too large.',
	unsupported_file: 'We cannot read that kind of file yet.',
	affidavit_not_confirmed: 'Please confirm the affidavit details before we analyse them.',
	extraction_unavailable: 'Automatic reading is unavailable. You can type the details in instead.',
	extraction_invalid:
		'We could not read the details off that document. You can type them in instead.',
	demo_only:
		'This is the demo version, so it does not take uploads. The example cases show what a real check looks like.',
	upstream_error: 'Something upstream did not answer. Please try again.',
	rate_limited: 'Too many requests. Please wait a moment.',
	invalid_request: 'Some of the details sent were not in the expected format.',
	not_found: 'We could not find that page.',
	internal_error: 'Something went wrong on our side.',
	network: 'We could not reach the server. Check your connection and try again.'
} as const;

export type ErrorCode = keyof typeof errors;

export const demo = {
	chip: 'Synthetic demo data',
	title: 'Three cases, end to end',
	note: 'Every name, case and document on these screens is invented for demonstration. The addresses are real New York City streets, used as geography and nothing else.',
	comingSoon: 'The full walkthrough, with the map and the downloadable packet, arrives with the result screen.',
	cases: [
		{
			id: 'maria',
			name: 'Maria — substituted service',
			tier: 'contradicted',
			summary:
				'The affidavit says papers were left at her Bronx door at 7:42 PM. Her phone puts her at a client\u2019s Manhattan address across that whole evening, and the only other person at home is nine years old.'
		},
		{
			id: 'james',
			name: 'James — substituted service',
			tier: 'consistent',
			summary:
				'James was home when the papers were left with his partner, and his partner matches the description. His own data supports the server\u2019s account, and ServeTrace says so.'
		},
		{
			id: 'lin',
			name: 'Lin — affix and mail',
			tier: 'contradicted',
			summary:
				'Papers taped to a Queens door at 4:30 PM on a shift day, while Lin\u2019s phone was at work in Brooklyn. The mailing is 34 days later, and both prior attempts fall inside office hours.'
		}
	]
} as const;

export const nav = {
	methodology: 'Methodology',
	privacy: 'Privacy',
	home: 'Home',
	advocate: 'Advocates'
} as const;
