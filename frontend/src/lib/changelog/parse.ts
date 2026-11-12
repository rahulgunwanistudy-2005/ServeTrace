/**
 * `CHANGELOG.md`, read at build time and turned into data. Bible §19.
 *
 * Only the Keep a Changelog subset the file uses is understood: `## [x.y.z] — date`
 * release headings, `### Section` headings, `- ` bullets (wrapped lines continue the
 * bullet) and `` `code` `` spans. Anything else above the first release is the preamble
 * and is not shown. A hand-rolled reader rather than a Markdown library because bible §8
 * pins the dependencies, and because rendering `{@html}` from a file would be the one
 * place in the app that injects markup.
 */

export interface ChangelogSection {
	title: string;
	items: string[];
}

export interface Release {
	version: string;
	date: string;
	sections: ChangelogSection[];
}

const RELEASE = /^## \[(\d+\.\d+\.\d+)\]\s*[—–-]\s*(\d{4}-\d{2}-\d{2})\s*$/;
const SECTION = /^### (.+?)\s*$/;

export function parseChangelog(text: string): Release[] {
	const releases: Release[] = [];
	let release: Release | null = null;
	let section: ChangelogSection | null = null;
	let item: string[] | null = null;

	const closeItem = () => {
		if (item && section) section.items.push(item.join(' '));
		item = null;
	};

	for (const raw of text.split(/\r?\n/)) {
		const line = raw.trimEnd();
		const isRelease = RELEASE.exec(line);
		if (isRelease) {
			closeItem();
			release = { version: isRelease[1]!, date: isRelease[2]!, sections: [] };
			releases.push(release);
			section = null;
			continue;
		}
		if (!release) continue;
		const isSection = SECTION.exec(line);
		if (isSection) {
			closeItem();
			section = { title: isSection[1]!, items: [] };
			release.sections.push(section);
			continue;
		}
		if (line.startsWith('- ')) {
			closeItem();
			item = [line.slice(2).trim()];
		} else if (item && line.trim()) {
			item.push(line.trim());
		} else if (!line.trim()) {
			closeItem();
		}
	}
	closeItem();
	return releases;
}

export type Span = { code: boolean; text: string };

/** Split `` `code` `` spans out of a bullet, so the page can set them in mono without HTML. */
export function spans(text: string): Span[] {
	return text
		.split(/(`[^`]+`)/)
		.filter(Boolean)
		.map((part) =>
			part.startsWith('`') && part.endsWith('`')
				? { code: true, text: part.slice(1, -1) }
				: { code: false, text: part }
		);
}
