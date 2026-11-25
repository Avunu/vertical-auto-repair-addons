/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Keeps the screen on while the board is showing, so an iPad on a stand
 * doesn't lock itself. The browser drops the lock whenever the page is
 * hidden, so it is asked for again when the page comes back. Where there is no
 * Wake Lock API, or the request is refused, nothing happens: the device's
 * auto-lock setting rules.
 */
import {useEffect} from "react";

export function useWakeLock() {
  useEffect(() => {
    if (!("wakeLock" in navigator)) {
      return undefined;
    }
    let lock: WakeLockSentinel | null = null;
    let active = true;
    const acquire = async () => {
      if (document.visibilityState !== "visible") {
        return;
      }
      try {
        const next = await navigator.wakeLock.request("screen");
        if (active) {
          lock = next;
        } else {
          void next.release();
        }
      } catch {
        // refused (low battery, no permission): the screen may lock
      }
    };
    void acquire();
    document.addEventListener("visibilitychange", acquire);
    return () => {
      active = false;
      document.removeEventListener("visibilitychange", acquire);
      void lock?.release();
    };
  }, []);
}
