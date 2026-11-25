/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * A frontend's typed API, from the JSON Schema export_api_schema.py wrote:
 *
 *   <dir>/api.schema.json  ->  <dir>/api.d.ts   (the facades' types, and `Api`)
 *   frontend/client.ts     ->  <dir>/client.ts  (the client, typed by `Api`)
 *
 * Run from the frontend's addon, whose own node_modules has
 * json-schema-to-typescript (resolved from the working directory, so each
 * addon keeps its own lockfile):
 *
 *   node ../repair_tech_api/tools/generate_api_types.mjs frontend/api [--check]
 */
import fs from "node:fs";
import {createRequire} from "node:module";
import path from "node:path";
import {pathToFileURL} from "node:url";

const here = path.dirname(new URL(import.meta.url).pathname);
const args = process.argv.slice(2);
const check = args.includes("--check");
const dir = path.resolve(args.find((arg) => !arg.startsWith("--")) ?? "frontend/api");

const require = createRequire(path.join(process.cwd(), "package.json"));
const {compile} = await import(pathToFileURL(require.resolve("json-schema-to-typescript")).href);

const schema = JSON.parse(fs.readFileSync(path.join(dir, "api.schema.json"), "utf8"));

/**
 * Pydantic titles every field ("Parts Done"), and json-schema-to-typescript
 * turns every title into a named type - `type PartsDone1 = number` and so
 * on. Only models (the $defs) should be named; drop the field titles.
 *
 * @param {Record<string, any>} node
 */
function dropFieldTitles(node) {
    for (const prop of Object.values(node.properties || {})) {
        delete prop.title;
    }
    for (const value of Object.values(node)) {
        if (value && typeof value === "object") {
            dropFieldTitles(value);
        }
    }
}
dropFieldTitles(schema);

/**
 * Datetimes are a brand, not a bare string: the facades take and give them
 * with an offset (Pydantic's AwareDatetime), so the app builds them with its
 * own helper rather than passing whatever string is at hand.
 *
 * @param {Record<string, any>} node
 */
function brandDatetimes(node) {
    if (node.type === "string" && node.format === "date-time") {
        node.tsType = "IsoDateTime";
    }
    for (const value of Object.values(node)) {
        if (value && typeof value === "object") {
            brandDatetimes(value);
        }
    }
}
brandDatetimes(schema);

const generated = (source) =>
    [
        "/* eslint-disable */",
        "/**",
        ` * GENERATED - do not edit. Source: ${source},`,
        " * via repair_tech_api/tools/generate_api_types.mjs. Regenerate with",
        " * `pnpm run generate`.",
        " */",
    ].join("\n");

const types =
    (await compile(schema, schema.title, {
        bannerComment: generated("the @facade methods in api.schema.json"),
        additionalProperties: false,
        format: true,
        strictIndexSignatures: true,
        unreachableDefinitions: true,
    })) +
    `\n/** Every facade, by model and method: what client.ts types calls with. */\nexport type Api = ${schema.title};\n` +
    `\n/** An ISO 8601 datetime with its offset, e.g. \`2026-01-05T09:00:00Z\`. */\nexport type IsoDateTime = string & {readonly __brand: "IsoDateTime"};\n`;

const client = fs
    .readFileSync(path.join(here, "../frontend/client.ts"), "utf8")
    .replace(/^\/\*\*\n \* Copyright[^\n]*\n \* License[^\n]*\n \*\n/, `${generated("repair_tech_api/frontend/client.ts")}\n/**\n`);

const outputs = {"api.d.ts": types, "client.ts": client};
let stale = false;
for (const [name, text] of Object.entries(outputs)) {
    const target = path.join(dir, name);
    if (check) {
        if (!fs.existsSync(target) || fs.readFileSync(target, "utf8") !== text) {
            console.error(`${target} is out of date: run \`pnpm run generate\``);
            stale = true;
        }
    } else {
        fs.writeFileSync(target, text);
        console.log(`wrote ${target}`);
    }
}
process.exit(stale ? 1 : 0);
