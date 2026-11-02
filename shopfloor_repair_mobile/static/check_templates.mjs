/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Compile every html`...` component template under src/ with Vue's own
 * template compiler - the same version (2.6.12) shopfloor_mobile_base loads
 * in the browser - and report its errors and tips as file:line:col. Catches
 * what the browser would only report at render time: unclosed or
 * mismatched tags, invalid directive/interpolation expressions, a v-else
 * with no v-if, more than one root element, ...
 *
 * Templates are located with the TypeScript parser (already a dev
 * dependency for `tsc`), not a regex, so positions are exact.
 *
 * Usage: node check_templates.mjs   (part of `npm run typecheck`)
 */
import fs from "node:fs";
import path from "node:path";
import {createRequire} from "node:module";

const require = createRequire(import.meta.url);
const ts = require("typescript");
const compiler = require("vue-template-compiler");

const root = path.dirname(new URL(import.meta.url).pathname);

/** @param {string} dir @returns {string[]} */
function walk(dir) {
    return fs.readdirSync(dir, {withFileTypes: true}).flatMap((e) =>
        e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)]
    );
}

let templates = 0;
let problems = 0;
for (const file of walk(path.join(root, "src")).filter((f) => f.endsWith(".esm.js"))) {
    const text = fs.readFileSync(file, "utf8");
    const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.JS);
    /** @param {import("typescript").Node} node */
    const visit = (node) => {
        if (
            ts.isTaggedTemplateExpression(node) &&
            node.tag.getText(sf) === "html" &&
            ts.isNoSubstitutionTemplateLiteral(node.template)
        ) {
            templates += 1;
            // +1: skip the opening backtick. `text` is the cooked value -
            // exactly what the tag hands Vue at runtime.
            const body_start = node.template.getStart(sf) + 1;
            const {errors, tips} = compiler.compile(node.template.text, {outputSourceRange: true});
            for (const [level, list] of [["error", errors], ["tip", tips]]) {
                for (const item of list) {
                    const msg = typeof item === "string" ? item : item.msg;
                    const offset = typeof item === "string" || item.start == null ? 0 : item.start;
                    const pos = sf.getLineAndCharacterOfPosition(body_start + offset);
                    const where = `${path.relative(root, file)}:${pos.line + 1}:${pos.character + 1}`;
                    console.log(`${where} - ${level}: ${msg.trim().split("\n")[0]}`);
                    if (level === "error") problems += 1;
                }
            }
        } else if (ts.isTaggedTemplateExpression(node) && node.tag.getText(sf) === "html") {
            const pos = sf.getLineAndCharacterOfPosition(node.getStart(sf));
            console.log(
                `${path.relative(root, file)}:${pos.line + 1}:${pos.character + 1} - error: ` +
                    "component templates must not contain ${...} substitutions"
            );
            problems += 1;
        }
        ts.forEachChild(node, visit);
    };
    visit(sf);
}
console.log(`${templates} templates checked, ${problems} error(s).`);
process.exit(problems ? 1 : 0);
