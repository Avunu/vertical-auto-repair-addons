/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * What the device offers an installed web app, each as a hook that does
 * nothing where the API is missing:
 *
 * - online/offline, so the app says it is offline instead of failing calls;
 * - the Screen Wake Lock, so a bay iPad stays on while a timer runs;
 * - the app badge (iOS 16.4+ home-screen apps), lit while a timer runs, so
 *   the icon itself says a clock is ticking;
 * - persistent storage, so iOS doesn't evict the offline cache;
 * - service worker updates: a new build waits until the technician says so,
 *   never reloading under their hands.
 */
import {useEffect, useState, useSyncExternalStore} from "react";

function subscribeOnline(callback: () => void): () => void {
  window.addEventListener("online", callback);
  window.addEventListener("offline", callback);
  return () => {
    window.removeEventListener("online", callback);
    window.removeEventListener("offline", callback);
  };
}

export function useOnline(): boolean {
  return useSyncExternalStore(subscribeOnline, () => navigator.onLine);
}

/** Keep the screen on while `active`; re-acquired when the page comes back. */
export function useWakeLock(active: boolean): void {
  useEffect(() => {
    if (!active || !("wakeLock" in navigator)) {
      return undefined;
    }
    let lock: WakeLockSentinel | null = null;
    let alive = true;
    const acquire = async (): Promise<void> => {
      if (document.visibilityState !== "visible") {
        return;
      }
      try {
        const next = await navigator.wakeLock.request("screen");
        if (alive) {
          lock = next;
        } else {
          await next.release();
        }
      } catch {
        // refused (low battery, no permission): the screen may lock
      }
    };
    void acquire();
    document.addEventListener("visibilitychange", acquire);
    return () => {
      alive = false;
      document.removeEventListener("visibilitychange", acquire);
      void lock?.release();
    };
  }, [active]);
}

/** Light the home-screen icon's badge while `active`. */
export function useAppBadge(active: boolean): void {
  useEffect(() => {
    if (!("setAppBadge" in navigator)) {
      return;
    }
    const done = active ? navigator.setAppBadge() : navigator.clearAppBadge();
    done.catch(() => undefined);
  }, [active]);
}

/** Ask once to keep the offline cache through storage pressure. */
export async function persistStorage(): Promise<void> {
  if (navigator.storage?.persist && !(await navigator.storage.persisted())) {
    await navigator.storage.persist();
  }
}

let updating = false;

/** A newer build is installed and waiting; `apply()` switches to it and reloads. */
export function useUpdateAvailable(): {available: boolean; apply: () => void} {
  const [waiting, setWaiting] = useState<ServiceWorker | null>(null);
  useEffect(() => {
    if (!("serviceWorker" in navigator)) {
      return undefined;
    }
    let alive = true;
    const watch = (registration: ServiceWorkerRegistration): void => {
      if (registration.waiting && navigator.serviceWorker.controller) {
        setWaiting(registration.waiting);
      }
      registration.addEventListener("updatefound", () => {
        const worker = registration.installing;
        worker?.addEventListener("statechange", () => {
          if (
            alive &&
            worker.state === "installed" &&
            navigator.serviceWorker.controller
          ) {
            setWaiting(worker);
          }
        });
      });
    };
    void navigator.serviceWorker
      .getRegistration()
      .then((registration) => registration && watch(registration));
    // Only the switch the technician asked for reloads: a first install
    // also changes the controller (clients.claim()), and must not.
    const onControllerChange = (): void => {
      if (updating) {
        window.location.reload();
      }
    };
    navigator.serviceWorker.addEventListener("controllerchange", onControllerChange);
    // A long-lived tablet app checks for a new build when it comes back.
    const check = (): void => {
      if (document.visibilityState === "visible") {
        void navigator.serviceWorker
          .getRegistration()
          .then((registration) => registration?.update());
      }
    };
    document.addEventListener("visibilitychange", check);
    return () => {
      alive = false;
      navigator.serviceWorker.removeEventListener(
        "controllerchange",
        onControllerChange
      );
      document.removeEventListener("visibilitychange", check);
    };
  }, []);
  const apply = (): void => {
    updating = true;
    // A ServiceWorker's postMessage has no targetOrigin: it is same-origin by construction.
    // oxlint-disable-next-line unicorn/require-post-message-target-origin
    waiting?.postMessage("skip-waiting");
  };
  return {available: waiting !== null, apply};
}

/** Light haptics where there are any (not iOS Safari): a scan landed. */
export function buzz(): void {
  navigator.vibrate?.(30);
}
