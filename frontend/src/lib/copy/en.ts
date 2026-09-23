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
	privacyBadge: 'Your location file is read on this device.'
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

export const result = {
	mapAlt: 'Map of the claimed service address and your recorded locations around that time.',
	mapTableCaption: 'The same information as the map, as a table.',
	claimedPin: 'Claimed service location',
	yourTrail: 'Where your phone was',
	whatThisMeans: 'What this means',
	whatItDoesNot: "What this doesn't mean",
	findings: 'What we found',
	downloadPacket: 'Download evidence packet',
	downloadAffidavit: 'Download draft affidavit',
	getHelp: 'Where to get help',
	askForGps:
		"Ask the plaintiff's lawyer for the server's GPS record.",
	/** Bible §5 L7. */
	askForGpsWhy:
		'Licensed New York City process servers must carry a device that electronically records the GPS location, date and time of every service and attempt.'
} as const;

export const deadlines = {
	title: 'Your deadline',
	/** Bible §5 L6. */
	cplr317:
		'If you were served in any way other than in person, and you did not personally get notice in time to defend the case, you may be able to ask the court to reopen it within one year of learning about the judgment, and no more than five years after it was entered.',
	/** Bible §5 L5. */
	cplr5015:
		'A judgment can be reopened when the court did not have jurisdiction, which includes service that was not done properly. There is no stated one-year limit for that ground, but act promptly.',
	traverse:
		'When the facts of service are disputed, the court may hold a hearing about service, called a traverse hearing.'
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
		'The NYC Department of Consumer and Worker Protection accepts complaints about process servers from legal advocates.'
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
	note: 'Every name, case and document on this screen is invented for demonstration.'
} as const;

export const nav = {
	methodology: 'Methodology',
	privacy: 'Privacy',
	home: 'Home'
} as const;
