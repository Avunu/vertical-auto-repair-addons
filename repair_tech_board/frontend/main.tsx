/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * The shop's job board. Barlow (the license-plate face) is bundled, so the
 * TV loads from Odoo alone.
 */
import "@fontsource/barlow-condensed/600.css";
import "@fontsource/barlow-condensed/700.css";
import "@fontsource/barlow-semi-condensed/500.css";
import "@fontsource/barlow-semi-condensed/600.css";
import "@fontsource/barlow-semi-condensed/700.css";
import "./app.css";
import {StrictMode} from "react";
import {createRoot} from "react-dom/client";
import {App} from "./App";

createRoot(document.getElementById("app")!).render(
    <StrictMode>
        <App />
    </StrictMode>
);
