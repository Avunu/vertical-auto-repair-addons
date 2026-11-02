/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Tag for component `template` strings: html`<div>...</div>`.
 *
 * Returns the template text unchanged - Vue's runtime compiler does all the
 * real work. The tag exists for tooling: editors key HTML language support
 * on it (VS Code's `bierner.lit-html` extension
 * gives highlighting, tag/attribute completion, hovers and
 * auto-closing inside any html`...` literal), and `check_templates.mjs`
 * uses it to find every template to compile-check.
 *
 * @param {TemplateStringsArray} strings
 * @param {...unknown} values
 * @returns {string}
 */
export function html(strings, ...values) {
    return String.raw({raw: strings}, ...values);
}
