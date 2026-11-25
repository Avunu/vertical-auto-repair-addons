/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Prepended to every browser test script (test_browser.py): wait for
 * something, find a control by its label or accessible name, tap it, and type
 * into a React-controlled field the way a keyboard would.
 */
// eslint-disable-next-line no-unused-vars
const ui = (function () {
    "use strict";
    const until = async (probe, what, ms = 15000) => {
        const start = Date.now();
        while (Date.now() - start < ms) {
            const value = probe();
            if (value) return value;
            await new Promise((resolve) => setTimeout(resolve, 50));
        }
        throw new Error("Timed out waiting for " + what);
    };
    const named = (el) => (el.getAttribute("aria-label") || el.innerText || "").trim();
    const control = (label, root = document) =>
        [
            ...root.querySelectorAll(
                "button, a, [role=button], [role=radio], input[type=checkbox]"
            ),
        ].find((el) => named(el) === label && !el.closest("[inert]"));
    const tap = async (label, root) => {
        const el = await until(
            () => control(label, root),
            "control " + JSON.stringify(label)
        );
        el.click();
        return el;
    };
    const row = (text) =>
        [...document.querySelectorAll("li")].find((li) => li.innerText.includes(text));
    const type = async (label, text) => {
        const field = await until(
            () =>
                [...document.querySelectorAll("input, textarea")].find(
                    (el) =>
                        el.labels &&
                        [...el.labels].some((l) => l.innerText.trim().startsWith(label))
                ),
            "field " + JSON.stringify(label)
        );
        const proto =
            field.tagName === "TEXTAREA"
                ? HTMLTextAreaElement.prototype
                : HTMLInputElement.prototype;
        Object.getOwnPropertyDescriptor(proto, "value").set.call(field, text);
        field.dispatchEvent(new Event("input", {bubbles: true}));
    };
    const seen = (text) => document.body.innerText.includes(text);
    return {until, control, tap, row, type, seen};
})();
