import text from '../../../../CHANGELOG.md?raw';
import { parseChangelog } from './parse';

/** Every release, newest first, as the repository's CHANGELOG.md has them at build time. */
export const releases = parseChangelog(text);

/**
 * The app version the footer shows: the newest release in the changelog. The backend's
 * `APP_VERSION` is held to the same number by `tests/test_version.py`, so the footer, the
 * API and the PDFs cannot disagree without a test failing.
 */
export const appVersion = releases[0]?.version ?? '0.0.0';
