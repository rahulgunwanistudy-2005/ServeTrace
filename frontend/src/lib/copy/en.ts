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
		`Sending ${sent} of ${total} location points (only around the claimed times).`
} as const;

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
