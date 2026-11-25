/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * The facade client. The page says which Odoo it came from
 * (<meta name="odoo-server-version">): call_kw up to 18.0, JSON-2 from 19.0.
 */
import {
  createClient,
  transportFor,
  type Method,
  type Params,
  type Result,
} from "../api/client";

/** The model every technician facade lives on. */
export const MODEL = "repair.tech.app";
export type Facade = Method<typeof MODEL>;
export type FacadeParams<F extends Facade> = Params<typeof MODEL, F>;
export type FacadeResult<F extends Facade> = Result<typeof MODEL, F>;

function serverVersion(): number {
  const meta = document.querySelector<HTMLMetaElement>(
    'meta[name="odoo-server-version"]'
  );
  const version = Number(meta?.content);
  return Number.isFinite(version) && version > 0 ? version : 18;
}

export function signIn(): void {
  window.location.assign(
    `/web/login?redirect=${encodeURIComponent(window.location.pathname + window.location.search)}`
  );
}

export const odoo = createClient({
  transport: transportFor(serverVersion()),
  onSessionExpired: signIn,
});
