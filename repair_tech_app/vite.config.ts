/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * The technician app's build, Rust end to end: Rolldown bundles, Oxc parses
 * and transforms, the React Compiler (oxc-transform-react) memoizes every
 * component, and StyleX compiles in SWC (@stylexswc).
 *
 * One entry under static/dist/ with content-hashed names and Vite's manifest,
 * which repair_tech_api's PwaApp reads for the page's tags and the service
 * worker's precache. Astryx ships its own CSS; only this app's stylex.create()
 * calls go through the StyleX compiler.
 */
import StylexRsPlugin from "@stylexswc/unplugin/vite";
import react from "@vitejs/plugin-react";
import {defineConfig} from "vitest/config";

export default defineConfig({
  plugins: [
    StylexRsPlugin({
      rsOptions: {
        include: ["frontend/**/*.{ts,tsx}"],
        dev: process.env["NODE_ENV"] !== "production",
        // Resolves the Astryx token modules our styles import.
        unstable_moduleResolution: {type: "commonJS"},
      },
      // Into frontend/app.css's marker: hashed and in the manifest.
      useCssPlaceholder: true,
    }),
    react({compiler: true}),
  ],
  base: "/repair_tech_app/static/dist/",
  build: {
    outDir: "static/dist",
    emptyOutDir: true,
    manifest: true,
    target: "es2023",
    rolldownOptions: {input: "frontend/main.tsx"},
  },
  test: {
    environment: "happy-dom",
    include: ["frontend/**/*.test.{ts,tsx}"],
    setupFiles: ["frontend/test/setup.ts"],
    restoreMocks: true,
  },
});
