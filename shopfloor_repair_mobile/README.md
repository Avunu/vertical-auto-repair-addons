# Shopfloor Repair Technician (Mobile)

The iPad-first technician app: assigned jobs, a work timer, parts consumption with
camera scanning, and digital vehicle inspections with severity grading, measurements and
photos.

The REST services live in [`shopfloor_repair`](https://github.com/Avunu/vertical-auto-repair-addons/blob/18.0/shopfloor_repair_mobile/../shopfloor_repair/); this module is the
Vue frontend plus the `shopfloor.app` record that publishes it.

Once installed the app is at **`/shopfloor/app/repair_shop`** and its API at
`/shopfloor/api/repair_shop/…`.

## Screens

| State                               | What the technician sees                                          |
| ----------------------------------- | ----------------------------------------------------------------- |
| `job_list`                          | assigned jobs, plate first, sorted by schedule                    |
| `job_detail`                        | **hub** — vehicle card, concern, timer, counters, actions         |
| `parts`                             | planned parts, one-tap "Used all", undo on the used ones          |
| `part_detail`                       | decimal quantity, lot/serial scan                                 |
| `catalog_search` / `catalog_detail` | browse or scan a part, add it to the job                          |
| `inspection_list`                   | this job's inspections + start one from a checklist               |
| `inspection_lines`                  | checklist grouped by category, ungraded counter                   |
| `inspection_line_detail`            | measurements, conditions, actions, note, photo, six grade buttons |

## Camera scanning

Nothing here does scanning. `shopfloor_mobile_camera_scan` overrides the _global_
`searchbar` component, so every state that renders `<searchbar>` gets a camera button
for free. Requirements it inherits:

- **Serve the app over HTTPS.** Safari silently blocks `getUserMedia` on plain HTTP, so
  the camera button appears and does nothing.
- html5-qrcode is vendored, so no CDN and no CSP exception is needed.

## Setup: one API key per technician

`shopfloor_mobile_base_auth_user` is not migrated to 18.0, so API keys are the only auth
flavour available. **`auth.api.key.user_id` is the Odoo user every request runs as**,
which means:

> A shared key collapses every technician into one identity. "My jobs" would show the
> wrong list and every timesheet would be booked to the wrong person.

So, per technician:

1. Settings → Technical → API Keys → new key, **User** = that technician.
2. Add it to the **Repair Shop Technicians** key group (created empty by this module —
   keys carry identities and must never ship as data).
3. On the iPad, open the app URL, enter the key, then pick the **Technician** profile
   once (Settings → Profile). The choice is remembered on the Odoo user (_Default
   Shopfloor Profile_, visible to shopfloor managers on the user form), so later
   logins - on any device - select it automatically.
4. Add to Home Screen for a full-screen, chrome-less PWA.

Printing each key as a QR badge is worth the ten minutes: the camera scanner is already
there, and nobody types a 40-character secret twice.

## Routes are registered at install

`endpoint.route.sync.mixin` creates app records out of sync by design, and
`shopfloor.app._get_services()` returns nothing while Odoo is still building its
registry — which is exactly when a post-init hook runs. Between them, a fresh install
would answer 404 on every endpoint until somebody found the "Sync registry" button.
[`hooks.py`](https://github.com/Avunu/vertical-auto-repair-addons/blob/18.0/shopfloor_repair_mobile/hooks.py) handles both.

If routes ever go missing (after restoring a database, say), open the app record and
press **Sync registry**.

**Restart the Odoo server after installing this module.** A server process that was
already running when the module was installed will serve the REST API fine but return
404 for `/shopfloor_repair_mobile/static/…`, because its list of addon static
directories was built at boot. The symptom is an app page that loads and then does
nothing.

## One app exposes every shopfloor service

`shopfloor.app` publishes _all_ services registered in the `shopfloor.app` collection,
so on a database that also has the WMS `shopfloor` module the repair app's route table
includes cluster-picking, reception and the rest. That is how the framework works — what
a technician can _reach_ is governed by the profile and its menus, and everything
underneath is still bound by normal Odoo access rights. Worth knowing before the route
count surprises you.

## Frontend conventions

Vue 2 + Vuetify 2, **no build step**: plain ES modules loaded by
[`templates/assets.xml`](https://github.com/Avunu/vertical-auto-repair-addons/blob/18.0/shopfloor_repair_mobile/templates/assets.xml) at the `new_scenario_hook` marker, with
`Vue` and `_` (lodash) as globals. No SFCs, no JSX: each component is a
`Vue.component()` options object whose `template` is a string, compiled in the browser
by the full Vue build `shopfloor_mobile_base` loads.
[`static/src/index.esm.js`](https://github.com/Avunu/vertical-auto-repair-addons/blob/18.0/shopfloor_repair_mobile/static/src/index.esm.js) is the one entry point; it imports
components before the scenario so its template can reference them.

Templates are written as html`...` tagged literals
([`static/src/services/html.esm.js`](https://github.com/Avunu/vertical-auto-repair-addons/blob/18.0/shopfloor_repair_mobile/static/src/services/html.esm.js), which returns the
text unchanged). The tag is for tooling: VS Code's `bierner.lit-html` extension gives
HTML highlighting, tag and attribute completion, hovers and auto-closing tags inside any
html`...` literal. It knows HTML, not Vue: directive values and `{{ }}` are not
type-checked in the editor.

Types are JSDoc comments, checked (never compiled) by TypeScript, and every template is
compiled by Vue's own 2.6.12 template compiler — the version the browser runs — which
reports bad expressions, unclosed tags, a stray `v-else` and so on as `file:line:col`:
`npm install && npm run typecheck` in `static/`
([`static/check_templates.mjs`](https://github.com/Avunu/vertical-auto-repair-addons/blob/18.0/shopfloor_repair_mobile/static/check_templates.mjs)). That is a development
check only — nothing in `static/` is generated, and production needs no Node.
`defineComponent()`
([`static/src/services/define_component.esm.js`](https://github.com/Avunu/vertical-auto-repair-addons/blob/18.0/shopfloor_repair_mobile/static/src/services/define_component.esm.js))
wraps each options object purely so the checker can see `this`; it returns its argument
unchanged.

Severity colours live in
[`static/src/components/severity.esm.js`](https://github.com/Avunu/vertical-auto-repair-addons/blob/18.0/shopfloor_repair_mobile/static/src/components/severity.esm.js) and
deliberately match the customer-facing PDF that `shop_inspection_report` renders — red
on the tablet and red on the report the customer is holding mean the same thing.

Two small things that are easy to get wrong again:

- The stock `input-number-spinner` `parseInt()`s its value. Parts are sold in litres and
  metres too, so quantity entry uses a plain decimal field with its own +/- buttons.
- Photos are downscaled to 1600px/JPEG-75 in a canvas before upload. A modern tablet
  camera produces 4–8 MB a shot and a technician takes a dozen per inspection.
