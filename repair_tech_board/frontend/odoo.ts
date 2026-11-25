/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * The board's facade client. The page's <meta name="odoo-server-version">
 * picks the transport: call_kw up to 18.0, JSON-2 from 19.0.
 */
import {createClient, transportFor} from "./api/client";

const version = Number(
  document.querySelector<HTMLMetaElement>('meta[name="odoo-server-version"]')
    ?.content ?? 18
);

export const odoo = createClient({
  transport: transportFor(version),
  onSessionExpired: () =>
    window.location.assign(
      `/web/login?redirect=${encodeURIComponent(window.location.pathname)}`
    ),
});
