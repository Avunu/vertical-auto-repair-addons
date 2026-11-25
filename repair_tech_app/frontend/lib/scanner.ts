/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Reading barcodes, two ways:
 *
 * - the camera, through the Barcode Detection API: the browser's own where it
 *   has one (Chrome on Android, macOS), else the barcode-detector ponyfill,
 *   which runs ZXing-C++ as WebAssembly (iPad Safari). The .wasm is part of
 *   our build, not fetched from a CDN, so scanning works offline;
 * - a hardware scanner that types the code and Enter (a Bluetooth or USB
 *   "keyboard wedge"), recognized by how fast the keys come.
 */
import type {BarcodeFormat} from "barcode-detector/ponyfill";
import zxingWasm from "zxing-wasm/reader/zxing_reader.wasm?url";

/** What a shop scans: work orders and parts (1D), VINs (Code 39), QR labels. */
export const FORMATS: BarcodeFormat[] = [
  "code_128",
  "code_39",
  "code_93",
  "codabar",
  "ean_13",
  "ean_8",
  "upc_a",
  "upc_e",
  "itf",
  "qr_code",
  "data_matrix",
  "pdf417",
];

export interface Detector {
  detect(source: ImageBitmapSource): Promise<Array<{rawValue: string}>>;
}

let detector: Promise<Detector> | null = null;

/** The detector, created once: native if the browser reads these formats, else ZXing. */
export function getDetector(): Promise<Detector> {
  detector ??= (async () => {
    const native = (
      globalThis as {
        BarcodeDetector?: typeof import("barcode-detector/ponyfill").BarcodeDetector;
      }
    ).BarcodeDetector;
    if (native) {
      const supported = await native.getSupportedFormats();
      if (FORMATS.every((format) => supported.includes(format))) {
        return new native({formats: FORMATS});
      }
    }
    const {BarcodeDetector, prepareZXingModule} = await import(
      "barcode-detector/ponyfill"
    );
    prepareZXingModule({
      overrides: {
        locateFile: (path: string, prefix: string) =>
          path.endsWith(".wasm") ? zxingWasm : prefix + path,
      },
      fireImmediately: false,
    });
    return new BarcodeDetector({formats: FORMATS});
  })();
  return detector;
}

/** Codes that differ only by a scanner's trailing whitespace are the same code. */
export function cleanCode(raw: string): string {
  return raw.replace(/[\r\n\t]+/g, "").trim();
}

/**
 * A keyboard-wedge reader: feed it every keydown; it calls `onScan` with the
 * code when a burst of keys typed faster than a person can ends in Enter.
 * Pure (no DOM), so its timing is testable.
 */
export function wedgeReader(
  onScan: (code: string) => void,
  {maxGapMs = 35, minLength = 4} = {}
) {
  let buffer = "";
  let last = 0;
  return (key: string, time: number): boolean => {
    if (time - last > maxGapMs) {
      buffer = "";
    }
    last = time;
    if (key === "Enter") {
      const code = cleanCode(buffer);
      buffer = "";
      if (code.length >= minLength) {
        onScan(code);
        return true;
      }
      return false;
    }
    if (key.length === 1) {
      buffer += key;
    }
    return false;
  };
}
