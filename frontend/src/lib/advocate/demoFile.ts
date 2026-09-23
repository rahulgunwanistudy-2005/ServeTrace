/**
 * The committed demo spreadsheet, loaded as a `File` the upload path can take.
 *
 * Bible §3 asks for a demo with zero network dependency, so the fixture is bundled as a
 * build asset rather than fetched from anywhere: `?url` makes Vite emit the same
 * committed XLSX that `tests/advocate/test_demo_fixture.py` asserts against, so the file
 * a judge clicks and the file the suite checks are one file.
 *
 * It then goes through exactly the upload path a real file goes through — same route,
 * same parser, same engine. A demo that takes a shortcut past the code proves nothing
 * about the code.
 */

import demoUrl from '../../../../fixtures/demo_cases/advocate_servers.xlsx?url';

export const DEMO_FILENAME = 'advocate_servers.xlsx';

const XLSX_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

export async function loadDemoFile(): Promise<File> {
	const response = await fetch(demoUrl);
	if (!response.ok) throw new Error(`demo file unavailable: ${response.status}`);
	return new File([await response.blob()], DEMO_FILENAME, { type: XLSX_TYPE });
}
