/**
 * Hand a generated file to the browser to save.
 *
 * The object URL is released after a pause rather than straight after `click()`. Chrome
 * copes with an immediate revoke; Firefox and Safari on iOS start the download
 * asynchronously and can find the URL already gone, which fails silently — on the phone
 * a defendant is most likely to be holding.
 */
export function saveBlob(blob: Blob, filename: string): void {
	const url = URL.createObjectURL(blob);
	const link = document.createElement('a');
	link.href = url;
	link.download = filename;
	link.click();
	setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
