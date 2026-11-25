# Repair Technician API

What the shop's own frontends are built on: typed model methods ("facades") they call,
the TypeScript generated from them, and the plumbing that makes a frontend an
installable app. It also holds the job board's data. Two frontends use it:
[`repair_tech_app`](repair_tech_app.md), the technician's app, and
[`repair_tech_board`](repair_tech_board.md), the shop's TV board.

## A facade is a typed model method

```python
@facade
def job(self, repair_id: int) -> JobDetail:
    """The job hub."""
```

`@facade`
([facade.py](https://github.com/Avunu/vertical-auto-repair-addons/blob/18.0/repair_tech_api/facade.py))
reads the signature once and then:

- validates the keyword arguments against a Pydantic model built from the parameters,
  `Annotated[..., Field(gt=0)]` constraints included: unknown or mistyped arguments
  never reach the body;
- validates the return value against the annotation and dumps it to JSON, so a facade
  can't leak a field its schema doesn't declare;
- makes the method `@api.model`, callable as `/web/dataset/call_kw/<model>/<method>` on
  18.0 and as `/json/2/<model>/<method>` on 19.0, whose body is exactly the keyword
  arguments.

Business errors are plain `UserError`s; call_kw and JSON-2 run a request in one
transaction and roll it back on any exception. Facades add no access rules: they run as
the signed-in user, and Odoo's ACLs and record rules decide.

Datetimes cross the wire with their offset (`AwareDatetime`); `naive_utc()` and
`aware()` convert to and from what Odoo stores.

## Python → JSON Schema → TypeScript

Each frontend generates its own typed API into its `frontend/api/`, so an addon builds
from its own folder (as odoo-nix builds it):

```
@facade signatures + Pydantic schemas
  └─ tools/export_api_schema.py        (imports the addons; no database)
       └─ <addon>/frontend/api/api.schema.json
            └─ tools/generate_api_types.mjs   (json-schema-to-typescript)
                 ├─ <addon>/frontend/api/api.d.ts   (the types, `Api`, `IsoDateTime`)
                 └─ <addon>/frontend/api/client.ts  (a copy of frontend/client.ts)
```

A frontend's `pnpm run generate` runs both; its `pnpm run check` fails when the
generated files are stale, and so does its Python test
(`common_pwa.assert_schema_current`).

The client
([frontend/client.ts](https://github.com/Avunu/vertical-auto-repair-addons/blob/18.0/repair_tech_api/frontend/client.ts))
is typed by `Api`:

```ts
const odoo = createClient({transport: transportFor(serverVersion)});
const job = await odoo.call("repair.tech.app", "job", {repair_id: 7}); // JobDetail
await odoo.call("repair.tech.app", "job", {}); // tsc error: repair_id
```

`transportFor()` picks call_kw's JSON-RPC up to 18.0 and JSON-2 from 19.0; the page says
which (`<meta name="odoo-server-version">`). Errors arrive as an `RpcError` whose `kind`
(`user`, `access`, `missing`, `session`, `network`, `server`) says how to react.
Datetimes are a branded `IsoDateTime`, so a bare or local string can't be sent.

## Installable apps

[`controllers/pwa.py`](https://github.com/Avunu/vertical-auto-repair-addons/blob/18.0/repair_tech_api/controllers/pwa.py):
a frontend is a Vite build in its addon's `static/dist/`, described once with `PwaApp`,
which serves under `/repair-tech/<slug>/` the page (from the build's manifest),
`manifest.webmanifest`, and `sw.js`.

The service worker precaches every file of the build (they are content-hashed), serves
the page network-first with the last good copy as fallback, and leaves facade calls to
the network. Each build is a new worker; the app decides when to switch.

## The job board's data

`repair.order.board_jobs` is the board's facade. A stage's **Job Board Status** and an
appointment type's **Job Board Icon** and **Label** (added here) decide what the board
shows; see [`repair_tech_board`](repair_tech_board.md).
