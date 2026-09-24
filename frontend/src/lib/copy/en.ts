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
	/**
	 * The strip under the hero. Where a marketing site puts customer logos, this puts the
	 * provisions the engine actually encodes — bible §5, nothing else. A logo wall is a
	 * claim about who trusts us; this is a claim anyone can go and check.
	 */
	groundedTitle: 'What this checks against',
	grounded: [
		'CPLR 308(1)',
		'CPLR 308(2)',
		'CPLR 308(4)',
		'CPLR 5015(a)(4)',
		'CPLR 317',
		'NYC Admin Code § 20-410'
	],
	/**
	 * Bible §2's impact numbers. Every one carries its source in the tile, because a
	 * statistic without one is exactly the kind of claim this product exists to check.
	 */
	statsTitle: 'Why this happens so often',
	statsBody:
		'A default judgment is what a court enters when the person being sued never answers. Most people never answer because most people never learn they were sued.',
	stats: [
		{
			value: 'Over 70%',
			label: 'of debt collection lawsuits across state courts end in a default judgment rather than a decision on the facts.',
			source: 'Pew Charitable Trusts, 2020'
		},
		{
			value: '17%',
			label: 'of the 366,000 consumer credit cases filed in New York City between 2019 and 2023 got any answer at all from the person being sued.',
			source: 'New York Focus, 2025'
		},
		{
			value: '152,000',
			label: 'default judgments were entered in New York City consumer credit cases between 2019 and 2024.',
			source: 'New York Focus, 2025'
		}
	],
	demoTitle: 'Rather see it work first?',
	demoBody:
		'Three synthetic cases — one where the data conflicts with the affidavit, one where it supports it, and one where it settles nothing. No file to upload, and nothing about them is real.',
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
	knowledgeQuestion: 'When did you first find out about the judgment?',
	knowledgeHint:
		'The day your account was frozen, or the day a letter arrived. An approximate date is fine.',
	judgmentQuestion: 'If you know it, the date the judgment was entered',
	judgmentHint: 'It is on the papers from the court. Leave it blank if you are not sure.',
	reading: 'Reading your papers…',
	readFailed: 'We could not read that file.',
	noLlm:
		'This copy of ServeTrace has no document reader configured, so nothing was read off the file. You can type the details in below — the check works exactly the same either way.',
	reviewTitle: 'Check what we read',
	reviewIntro:
		'These came off your document. Change anything that is wrong. Nothing is compared until you confirm them.',
	quotedAs: 'On the page:',
	fields: {
		index_number: 'Index number',
		court: 'Court',
		plaintiff: 'Who sued you',
		defendant_name: 'Your name, as written on the papers',
		server_name: 'Process server',
		method: 'How they say they served you',
		served_date: 'Date of the service',
		served_time: 'Time of the service',
		served_address: 'Address they say they served you at',
		recipient_name: 'Who they say took the papers',
		recipient_relationship: 'That person\u2019s relationship to you',
		mailing_date: 'Date they say they mailed a copy',
		proof_filed_date: 'Date the proof was filed with the court'
	},
	methodOptions: {
		'308_1': 'Handed to me in person',
		'308_2': 'Left with someone else, and mailed',
		'308_4': 'Taped to the door, and mailed',
		unknown: 'The papers do not say clearly'
	},
	addressNeeded: 'The check needs the address they say they served you at.',
	timeNeeded: 'The check needs the date and time they say they served you.',
	resolving: 'Finding that address…',
	addressNotFound:
		'We could not find that address in New York City. Check the spelling — the check needs a point on the map to measure from.'
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
		`${approximate ? 'More than ' : ''}${n.toLocaleString('en-US')} location point${n === 1 ? '' : 's'}.`,

	title: 'Where were you?',
	hint: 'Bring whatever record you already have. It is read on this device.',
	tileHints: {
		timeline: 'A Google Timeline export, if you had Location History on.',
		card: 'A CSV from your bank or card, if you paid for something that evening.',
		manual: 'No file at all — just tell us where you were.'
	},
	howAndroid: 'On Android',
	howAndroidBody:
		'Settings → Location → Location services → Timeline → Export Timeline data. You get a file called Timeline.json.',
	howIphone: 'On an iPhone',
	howIphoneBody:
		'Google Maps → your profile picture → Settings → Personal content → Export Timeline data.',
	chooseFile: 'Choose your Timeline file',
	chooseFileHint: 'A .json file, up to about 200 MB. It is never uploaded.',
	chooseCsv: 'Choose your statement',
	chooseCsvHint:
		'A .csv from your bank. Only the address of a transaction is ever looked up \u2014 never the merchant or the amount.',
	manualTitle: 'Tell us where you were',
	manualWhere: 'Address or place',
	manualDay: 'Which day',
	manualFrom: 'From (New York time)',
	manualTo: 'Until (New York time)',
	manualBadTime: 'Check the day and the times \u2014 we could not read them.',
	manualAdd: 'Add this',
	manualNone: 'Nothing added yet.',
	manualRemove: 'Remove',
	resolving: 'Finding that address\u2026',
	noneNearClaim:
		'None of your points fall near the time on the affidavit. The check can still run, and it will say it has no data for that moment.',
	coverageOk: (n: number) => `${n} point${n === 1 ? '' : 's'} fall in the hours around the service.`,
	cancel: 'Stop reading'
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
export const household = {
	title: 'Who lives with you?',
	intro:
		'Optional, and only used for one thing: if the affidavit says the papers were left with somebody, we compare that description to the people you list. We never ask for a photograph and never will.',
	label: 'What to call them',
	labelHint: 'A first name or "my daughter" \u2014 whatever you like. It goes in your packet.',
	sex: 'Sex',
	sexOptions: { unknown: 'Prefer not to say', male: 'Male', female: 'Female', other: 'Other' },
	age: 'Age',
	height: 'Height in inches',
	heightHint: "5'6\" is 66 inches.",
	isDefendant: 'This is me',
	add: 'Add this person',
	remove: 'Remove',
	none: 'Nobody added. You can skip this step.',
	skip: 'Skip this step'
} as const;

export const wizard = {
	back: 'Back',
	next: 'Continue',
	run: 'See what we found',
	running: 'Working it out\u2026',
	saveHere: 'Save this on my device so I can come back to it',
	saveHint:
		'Kept in this browser only, never sent anywhere. Clearing it removes it for good.',
	saved: 'Saved on this device.',
	saveFailed: 'This browser would not let us save. Everything still works \u2014 just do not close the tab.',
	restore: 'Pick up where you left off',
	restoreFound: 'There is a saved check on this device.',
	discard: 'Start fresh instead',
	needAffidavit: 'Fill in the details from your papers and tick the box to continue.',
	needFixes: 'Add at least one record of where you were, or go back and use a different source.'
} as const;

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
	/**
	 * The two halves of bible §6's honesty requirement, as prose rather than as a tier.
	 * A person who has just been told their data conflicts with a sworn statement needs
	 * both: what it is worth, and what it is not.
	 */
	whatThisMeansBody:
		'You have a record of where your phone was, made at the time, that does not fit what the process server swore. That is the kind of thing a court can be asked to look at, and it is the reason a judge may order a hearing about whether you were served.',
	whatItDoesNotBody:
		'It does not prove what happened, and nothing here decides your case. A phone shows where a phone was. Someone else may have had it, and a court may hear an explanation nobody has given yet. It also does not touch whether you owe the money — only whether you were told you were being sued.',
	consistentMeansBody:
		'Your own records put you at or near that address at the time the server swore. That is worth knowing before you spend money on a motion, and it is why this check shows you the answer either way.',
	inconclusiveMeansBody:
		'Your data neither backs the affidavit nor conflicts with it under the thresholds this check uses. That is not the same as nothing being wrong — the papers themselves may still have problems, and any findings below stand on their own.',
	noDataMeansBody:
		'There are no usable location points near the time the server swore, so this check cannot say anything about that moment. Anything found in the papers themselves still stands.',
	/**
	 * The draft affidavit's ticks. Bible §15: every paragraph it writes is gated on one of
	 * these, and each is something only the person signing is in a position to state. The
	 * wording is first person because that is how it will read in the document.
	 */
	affiantTitle: 'Before we draft the affidavit',
	affiantIntro:
		'A draft supporting affidavit is written in your own voice and you sign it in front of a notary. We only write a paragraph you tell us is true. Anything you leave unticked is left out of the document rather than softened.',
	affiantName: 'Your full name, as it appears on the court papers',
	affiantAddress: 'Your home address at the time of the service',
	affiantAddressHint: 'Only used if you tick the box below about the address.',
	affiantNotServed: 'Nobody handed me these papers and I did not find them at my door.',
	affiantNotMyAddress: 'The address on the affidavit was not my home or my workplace.',
	affiantNoNotice:
		'I did not learn about this case in time to defend it.',
	affiantNoNoticeHint:
		'CPLR 317 turns on this, and the alternative paragraph it allows cannot be offered without it.',
	affiantDefense: 'If you have a defence to the debt itself, say it in your own words',
	affiantDefenseHint:
		'Optional, and never written for you. CPLR 317 asks for a defence with merit; a judge reads this as yours.',
	affiantCancel: 'Cancel',
	affiantSubmit: 'Draft the affidavit',
	affiantNameNeeded: 'The document needs a name to put on it.',
	nextTitle: 'What you can do next',
	startOver: 'Start a different check',
	emptyTitle: 'There is no case on this device yet',
	emptyBody:
		'This page shows the result of a check. Nothing is stored on our server, so there is nothing to load — start a check, or open a worked example.',
	mapLoading: 'Drawing the map…',
	mapUnavailable:
		'The map could not be drawn on this device. The table below carries the same information.',
	scrubberLabel: 'Time',
	scrubberHint: 'Drag to move through the hours around the claimed service.',
	sourceHint: 'Where these numbers come from',
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

	advocateTitle: 'Batch mode, scored separately',
	advocateBody: (filings: number, servers: number) =>
		`Advocate mode asks a different question of a different corpus: ${filings.toLocaleString('en-US')} filings from ${servers} synthetic process servers, some of whose sequences were deliberately built so that nobody could have travelled them. As with the case corpus, the generator decided which ones from where it placed the records, and never by asking the engine.`,
	advocateStatClean: 'Ordinary servers named',
	advocateStatPrecision: 'Sequences found that were planted',
	advocateStatRecall: 'Planted sequences found',
	advocatePrecisionNote:
		'Precision leads here and recall follows. A sequence this misses costs an advocate one line of evidence; a sequence it reports wrongly costs them their credibility with whoever reads the report.',
	advocateRuntime: (ms: number, filings: number) =>
		`${filings.toLocaleString('en-US')} filings analysed in ${Math.round(ms)} ms. The design target is 50,000 in under three seconds.`,

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

	/**
	 * Why this is a different kind of evidence from the defendant flow, said once and
	 * plainly. It needs no location history from anybody: the conflict is inside the
	 * server\u2019s own filings.
	 */
	premiseTitle: 'What this looks at',
	premiseBody:
		'The defendant check compares one sworn affidavit against one person\u2019s own location history. This compares a process server\u2019s filings against each other. If two services are sworn eleven kilometres apart three minutes apart, the two filings conflict whatever either defendant was doing that day.',

	// --- Step 1: the file
	uploadTitle: 'Your service records',
	upload: 'Upload a CSV or XLSX of service records.',
	uploadHint:
		'Most case-management systems export this. ServeTrace needs a server, a date and time, and either coordinates or a New York City address.',
	chooseFile: 'Choose a file',
	orTryDemo: 'Or open the example file',
	demoFileNote:
		'A synthetic week for four process servers, so you can see the report before you upload anything real.',
	reading: 'Reading your file\u2026',
	analysing: 'Looking for sequences that do not add up\u2026',

	// --- Step 2: the mapping
	mapColumns: 'Match your columns',
	mapColumnsHint:
		'We guessed from your headings. Change anything we got wrong. Nothing is read until you press the button.',
	mapRequired: 'Needed',
	mapOptional: 'Optional, and worth having',
	notMapped: '\u2014 not used \u2014',
	fields: {
		server_id: 'Process server',
		at: 'Date and time',
		date: 'Date',
		time: 'Time',
		lat: 'Latitude',
		lng: 'Longitude',
		address: 'Address',
		case_ref: 'Case number',
		outcome: 'Outcome',
		recipient_desc: 'Description of the person served'
	},
	fieldHints: {
		at: 'One column holding both, or use the date and time columns below.',
		lat: 'Coordinates are best: nothing has to be looked up, and nothing is sent anywhere.',
		address: 'Used only when there are no coordinates. Only the address is ever looked up.',
		outcome: 'Lets us count completed services separately from attempts.',
		recipient_desc: 'Lets us spot one description reused at many different doors.'
	},
	analyse: 'Find the conflicts',
	back: 'Choose a different file',

	// --- The report
	riskTable: 'Servers, ranked',
	riskTableHint: 'Ordered by how much in their own filings does not fit together.',
	columns: {
		rank: 'Rank',
		server: 'Process server',
		filings: 'Filings',
		impossible: 'Sequences that do not add up',
		busiest: 'Busiest hour',
		descriptions: 'Reused descriptions'
	},
	nothingFound: 'Nothing to report',
	nothingFoundBody:
		'None of these servers has a sequence in their own filings that could not have been travelled. That is the result, and it is a real one.',
	impossiblePairs: 'Sequences that do not add up',
	pairSummary: (km: string, minutes: string, speed: string) =>
		`${km} apart, ${minutes} apart. Covering that would mean about ${speed}.`,
	repeatedTitle: 'One description, many doors',
	repeatedBody: (doors: number) =>
		`The same description of the person who took the papers appears at ${doors} different addresses.`,
	repeatedNote:
		'This is worth checking rather than conclusive: coded descriptions are short, and two people can genuinely be described the same way.',
	busiestHourTitle: 'Busiest hour',
	busiestHour: (n: number) =>
		`${n} completed service${n === 1 ? '' : 's'} in a single hour, at the busiest point.`,
	busiestHourOk: 'No hour in this file is unusually busy.',
	selectServer: 'Select a server to see their day on the map.',
	mapTitle: 'That server\u2019s filings',
	mapHint:
		'Each pin is a filing. A red line joins two the server could not have travelled between.',
	mapAlternative: 'The same filings as a table',
	viewDay: 'See this server\u2019s day',

	// --- Rejected rows
	rejectedTitle: (n: number) => `${n} row${n === 1 ? '' : 's'} could not be used`,
	rejectedBody:
		'These are listed rather than dropped, because a report is only as good as the rows it counted.',
	rejectedRow: (row: number) => `Row ${row}`,
	statsLine: (records: number, rows: number, servers: number) =>
		`${records.toLocaleString('en-US')} of ${rows.toLocaleString('en-US')} rows used, across ${servers} process server${servers === 1 ? '' : 's'}.`,

	// --- Exports and next steps
	exportCsv: 'Download the sequences (CSV)',
	exportServers: 'Download the summary (CSV)',
	/** Bible §5 L7. */
	dcwpNote:
		'The NYC Department of Consumer and Worker Protection accepts complaints about process servers from legal advocates.',
	gpsTitle: 'Ask for the GPS record',
	gpsBody:
		'Licensed New York City process servers must carry a device that electronically records the GPS location, date and time of every service and attempt. That record can be asked for, and it either matches these filings or it does not.',
	limitation:
		'This compares filings with each other. It shows where two sworn statements cannot both be right; what happened, and what follows from it, is for a court.'
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
	/**
	 * Bible §16 requires every demo screen to say it is a demo. It has said so three ways
	 * now, and the trend is the point: "Synthetic demo data" satisfied the letter and read
	 * as an apology; a `DEMO` pill beside this sentence said the same word twice, once in
	 * a badge and once in prose. What actually discloses anything is the sentence, so the
	 * badge is gone and the sentence is the whole of it.
	 *
	 * It names what is real as well as what is not, because that is the more useful half:
	 * the addresses are real NYC streets, the provisions are real CPLR, the licence
	 * register is the City's own, and the only invented things are the people and their
	 * cases.
	 */
	provenance: 'Real NYC addresses and real CPLR rules. The people and cases are invented.',
	title: 'Three cases, end to end',
	note: 'Every name, case and document on these screens is invented for demonstration. The addresses are real New York City streets, used as geography and nothing else.',
	open: 'Open this case',
	opening: 'Loading…',
	runNote:
		'Each case runs through the same engine and the same screens a real check uses. Nothing is pre-recorded: the verdict you see is computed when you open it.',
	failed: 'That case could not be loaded.',
	cases: [
		{
			id: 'maria_contradicted',
			name: 'Maria — substituted service',
			tier: 'contradicted',
			summary:
				'The affidavit says papers were left at her Bronx door at 7:42 PM. Her phone puts her at a client\u2019s Manhattan address across that whole evening, and the only other person at home is nine years old.'
		},
		{
			id: 'james_consistent',
			name: 'James — substituted service',
			tier: 'consistent',
			summary:
				'James was home when the papers were left with his partner, and his partner matches the description. His own data supports the server\u2019s account, and ServeTrace says so.'
		},
		{
			id: 'lin_affix_mail_diligence',
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
