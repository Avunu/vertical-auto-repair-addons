/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * A tablet camera shot is 4-8 MB and a technician takes a dozen per
 * inspection. Downscale to 1600px JPEG before it leaves the device: off the
 * main thread where the browser can (createImageBitmap + OffscreenCanvas),
 * honoring the photo's EXIF orientation.
 */
export const MAX_EDGE = 1600;
export const QUALITY = 0.75;

/** The size that fits `max` on the long edge, never enlarging. */
export function fitWithin(
  width: number,
  height: number,
  max = MAX_EDGE
): {width: number; height: number} {
  const scale = Math.min(1, max / Math.max(width, height));
  return {width: Math.round(width * scale), height: Math.round(height * scale)};
}

/** A photo, downscaled, as base64 JPEG (no `data:` prefix: what add_photo takes). */
export async function downscalePhoto(file: Blob): Promise<string> {
  const bitmap = await createImageBitmap(file, {imageOrientation: "from-image"});
  const {width, height} = fitWithin(bitmap.width, bitmap.height);
  const canvas = new OffscreenCanvas(width, height);
  const context = canvas.getContext("2d");
  if (!context) {
    bitmap.close();
    throw new Error("This device can't process photos.");
  }
  context.drawImage(bitmap, 0, 0, width, height);
  bitmap.close();
  const jpeg = await canvas.convertToBlob({type: "image/jpeg", quality: QUALITY});
  return base64(await jpeg.arrayBuffer());
}

function base64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  // Uint8Array.prototype.toBase64 where the browser has it (Safari 18.2+).
  const native = (bytes as Uint8Array & {toBase64?: () => string}).toBase64;
  if (native) {
    return native.call(bytes);
  }
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(binary);
}
