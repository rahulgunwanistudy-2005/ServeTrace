/**
 * Reading a MapLibre canvas back as a PNG for a PDF: the evidence packet (bible §15) and
 * the advocate batch report (build prompt §6.4). Both maps are created with
 * `preserveDrawingBuffer: true`, which is what makes the pixels readable after a paint.
 */

import type maplibregl from 'maplibre-gl';

/**
 * How wide the capture is, in pixels, before it goes into the packet.
 *
 * The packet is Letter with about six and a half inches of content, so this is a bit
 * over 200 dpi — past what the paper can show. The raw canvas is the viewport times
 * the device pixel ratio, which on this machine was 2048px for a 1024px map and about
 * 1.5 MB of PNG. The server refuses anything over 3 MB (bible §15), so on a 2560px
 * display the untouched capture would have crossed the limit and the download would
 * have failed with a size error on exactly the screens most likely to be showing this
 * to a courtroom. Downscaling is not an optimisation here, it is the thing that keeps
 * the feature working.
 */
export const CAPTURE_WIDTH = 1400;

/**
 * The canvas as a PNG data URI, read at the moment somebody asks for it.
 *
 * Returns null rather than throwing on a tainted canvas or a context the browser will
 * not read back. The packet prints its text alternative in that case, which is why
 * this is a fallback and not an error.
 */
export function captureMap(created: maplibregl.Map): string | null {
	try {
		const source = created.getCanvas();
		if (source.width <= CAPTURE_WIDTH) return source.toDataURL('image/png');

		const scaled = document.createElement('canvas');
		scaled.width = CAPTURE_WIDTH;
		scaled.height = Math.round((source.height / source.width) * CAPTURE_WIDTH);
		const context = scaled.getContext('2d');
		if (!context) return source.toDataURL('image/png');
		context.drawImage(source, 0, 0, scaled.width, scaled.height);
		return scaled.toDataURL('image/png');
	} catch {
		return null;
	}
}
