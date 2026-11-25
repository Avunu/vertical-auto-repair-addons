/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * The technician app: Astryx's styles and theme, the persisted query cache,
 * the router, and app-wide scanning.
 */
import "@astryxdesign/core/reset.css";
import "@astryxdesign/core/astryx.css";
import "./app.css";
import {LinkProvider} from "@astryxdesign/core/Link";
import {Theme} from "@astryxdesign/core/theme";
import {PersistQueryClientProvider} from "@tanstack/react-query-persist-client";
import {RouterProvider} from "@tanstack/react-router";
import {StrictMode} from "react";
import {createRoot} from "react-dom/client";
import {defaultThemeSlug, themes} from "../astryx-themes.js";
import {RouterAnchor} from "./components/links";
import {ScanProvider} from "./components/scan";
import {CACHE_BUSTER, persister, queryClient} from "./data/queries";
import {persistStorage} from "./lib/device";
import {makeRouter} from "./router";

const router = makeRouter(queryClient);
const root = document.getElementById("app");
if (!root) {
    throw new Error("The page has no #app element");
}

createRoot(root).render(
    <StrictMode>
        <Theme theme={themes[defaultThemeSlug]}>
            <PersistQueryClientProvider
                client={queryClient}
                persistOptions={{persister, maxAge: 7 * 24 * 3_600_000, buster: CACHE_BUSTER}}
                onSuccess={() => void queryClient.resumePausedMutations()}
            >
                <LinkProvider component={RouterAnchor}>
                    <ScanProvider>
                        <RouterProvider router={router} />
                    </ScanProvider>
                </LinkProvider>
            </PersistQueryClientProvider>
        </Theme>
    </StrictMode>
);

void persistStorage();
