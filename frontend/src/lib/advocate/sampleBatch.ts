/**
 * The bundled sample batch: sixty synthetic affidavits as the reader would hand them back.
 *
 * Written by `fixtures/generator/advocate_batch.py` from the same seed as the answer key
 * the backend tests score against, so the batch a judge loads and the batch the suite
 * checks are one batch. Imported lazily: it is a few hundred kilobytes that nobody who
 * never presses the button should download. No network either way (bible §3).
 */

import type { DocumentExtraction } from '$lib/api/client';

export type SampleFile = { name: string; extraction: DocumentExtraction };

/**
 * Through `import.meta.glob` rather than a plain `import()`, so the type checker does not
 * infer a type for a 350 KB literal; the shape is the API's own `DocumentExtraction`.
 */
const LOADERS = import.meta.glob('../../../../fixtures/advocate_batch/sample_extractions.json', {
	import: 'default'
}) as Record<string, () => Promise<unknown>>;

export async function loadSampleBatch(): Promise<SampleFile[]> {
	const load = Object.values(LOADERS)[0];
	if (!load) throw new Error('sample batch not bundled');
	return (await load()) as SampleFile[];
}
