/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * One entry under static/dist/ with content-hashed names, and Vite's manifest
 * (static/dist/.vite/manifest.json), which repair_tech_api's PwaApp reads for
 * the page's tags and the service worker's precache. The fonts are bundled,
 * so the TV needs Odoo alone. The React Compiler runs in Rust
 * (oxc-transform-react), so components memoize themselves.
 */
import react from "@vitejs/plugin-react";
import {defineConfig} from "vite";

export default defineConfig({
  plugins: [react({compiler: true})],
  base: "/repair_tech_board/static/dist/",
  build: {
    outDir: "static/dist",
    emptyOutDir: true,
    manifest: true,
    rolldownOptions: {input: "frontend/main.tsx"},
  },
});
