import { describe, expect, it } from 'vitest';

import text from '../../../../CHANGELOG.md?raw';
import { parseChangelog, spans } from './parse';

const SAMPLE = `# Changelog

Preamble that is not shown.

## [1.1.0] — 2026-11-12

### Added

- One thing, written
  over two lines.
- \`code\` here.

### Security

- Safe.

## [1.0.0] — 2026-09-27

### Added

- First.
`;

describe('reading the changelog', () => {
	it('reads releases, sections and wrapped bullets', () => {
		const releases = parseChangelog(SAMPLE);
		expect(releases.map((r) => [r.version, r.date])).toEqual([
			['1.1.0', '2026-11-12'],
			['1.0.0', '2026-09-27']
		]);
		expect(releases[0]!.sections.map((s) => s.title)).toEqual(['Added', 'Security']);
		expect(releases[0]!.sections[0]!.items).toEqual(['One thing, written over two lines.', '`code` here.']);
	});

	it('splits code spans out without markup', () => {
		expect(spans('set `A_B` now')).toEqual([
			{ code: false, text: 'set ' },
			{ code: true, text: 'A_B' },
			{ code: false, text: ' now' }
		]);
	});

	it('reads the real file, newest release first, with the two required releases', () => {
		const releases = parseChangelog(text);
		expect(releases[0]!.version).toBe('1.1.0');
		expect(releases.map((r) => r.version)).toContain('1.0.0');
		for (const release of releases) {
			expect(release.sections.length).toBeGreaterThan(0);
			expect(release.sections.every((s) => s.items.length > 0)).toBe(true);
		}
	});
});
