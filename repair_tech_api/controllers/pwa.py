# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""What every shop frontend needs to be an installable app.

A frontend is a Vite build in its addon's ``static/dist/`` (see
:func:`vite_entry`). It describes itself once with :class:`PwaApp` and routes
three URLs to it, all under the app's own path so the manifest scope and the
service worker scope are that path and nothing above it::

    /repair-tech/<slug>/                       the page (``auth="user"``)
    /repair-tech/<slug>/manifest.webmanifest
    /repair-tech/<slug>/sw.js

The service worker is served from inside the scope on purpose: a worker
under ``/<module>/static/`` could only ever control ``/<module>/static/``.
"""

import hashlib
import json
import os

from werkzeug.exceptions import InternalServerError

from odoo import release
from odoo.http import request
from odoo.tools.misc import file_path

# The worker makes the app open without a network. The build's files have
# content-hashed names, so they are fetched once at install and served from
# the cache forever; the page itself goes to the network first and falls back
# to the copy from its last good load, so an installed app opens in a
# basement bay and shows what it last knew. Everything else - the facade
# calls above all - goes to the network untouched: what an app does offline
# with its data is the app's business, not the worker's.
#
# BUILD changes with every build, so a new build is a new worker: the browser
# installs it beside the old one, and the page tells it to take over (the
# `skip-waiting` message) when it is ready to reload.
SERVICE_WORKER = """\
const BUILD = %(build)s;
const SCOPE = %(scope)s;
const PRECACHE = %(precache)s;
const IMMUTABLE = %(immutable)s;
const ASSETS = "assets-" + BUILD;
const PAGES = "pages";

self.addEventListener("install", (event) => {
    event.waitUntil(caches.open(ASSETS).then((cache) => cache.addAll(PRECACHE)));
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        (async () => {
            for (const name of await caches.keys()) {
                if (name.startsWith("assets-") && name !== ASSETS) {
                    await caches.delete(name);
                }
            }
            await self.clients.claim();
        })()
    );
});

self.addEventListener("message", (event) => {
    if (event.data === "skip-waiting") {
        self.skipWaiting();
    }
});

async function page(request) {
    const cache = await caches.open(PAGES);
    try {
        const response = await fetch(request);
        // Not a page that was redirected to /web/login: that is no shell.
        const own = new URL(response.url).pathname.startsWith(SCOPE);
        if (response.ok && own && !response.redirected) {
            await cache.put(SCOPE, response.clone());
        }
        return response;
    } catch (error) {
        const cached = await cache.match(SCOPE);
        if (cached) {
            return cached;
        }
        throw error;
    }
}

async function asset(request) {
    const cached = await caches.match(request);
    if (cached) {
        return cached;
    }
    const response = await fetch(request);
    if (response.ok) {
        const cache = await caches.open(ASSETS);
        await cache.put(request, response.clone());
    }
    return response;
}

self.addEventListener("fetch", (event) => {
    const request = event.request;
    if (request.method !== "GET") {
        return;
    }
    const url = new URL(request.url);
    if (url.origin !== self.location.origin) {
        return;
    }
    if (request.mode === "navigate" && url.pathname.startsWith(SCOPE)) {
        event.respondWith(page(request));
    } else if (IMMUTABLE.some((prefix) => url.pathname.startsWith(prefix))) {
        event.respondWith(asset(request));
    }
});
"""


class PwaApp:
    """One installable app living at ``/repair-tech/<slug>/``, built by Vite
    into ``<module>/static/dist/``."""

    def __init__(
        self,
        module,
        slug,
        name,
        short_name,
        theme_color,
        background_color="#ffffff",
        icon="icon",
        status_bar_style="default",
        description="",
        entry="frontend/main.tsx",
        orientation="any",
        shortcuts=(),
    ):
        self.module = module
        self.slug = slug
        self.name = name
        self.short_name = short_name
        self.description = description
        self.theme_color = theme_color
        self.background_color = background_color
        self.icon_name = icon
        # iOS's bar above an installed app: "default" (white), "black", or
        # "black-translucent" (the app draws under it).
        self.status_bar_style = status_bar_style
        self.entry = entry
        self.orientation = orientation
        # ({"name", "url" relative to the scope, "description"}, ...): what a
        # long press on the installed icon offers.
        self.shortcuts = shortcuts
        self.scope = f"/repair-tech/{slug}/"

    def icon(self, size):
        return f"/{self.module}/static/img/{self.icon_name}-{size}.png"

    @property
    def server_version(self):
        return server_version()

    @property
    def dist(self):
        return vite_dist(self.module)

    def manifest(self):
        manifest = {
            "id": self.scope,
            "name": self.name,
            "short_name": self.short_name,
            "scope": self.scope,
            "start_url": self.scope,
            "display": "standalone",
            "orientation": self.orientation,
            "theme_color": self.theme_color,
            "background_color": self.background_color,
            "icons": [
                {
                    "src": self.icon(size),
                    "sizes": f"{size}x{size}",
                    "type": "image/png",
                    "purpose": "any",
                }
                for size in (192, 512)
            ],
        }
        if self.description:
            manifest["description"] = self.description
        if self.shortcuts:
            manifest["shortcuts"] = [
                dict(shortcut, url=self.scope + shortcut["url"].lstrip("/"))
                for shortcut in self.shortcuts
            ]
        return manifest

    def page_values(self, **values):
        """What the page template gets: ``pwa`` (for ``repair_tech_api.pwa_head``)
        and ``vite``, the build's tags for the entry."""
        return {"pwa": self, "vite": vite_entry(self.module, self.entry), **values}

    def render(self, template, **values):
        return request.render(template, self.page_values(**values))

    def manifest_response(self):
        return request.make_json_response(
            self.manifest(), headers=[("Content-Type", "application/manifest+json")]
        )

    def service_worker_body(self):
        build = read_vite_manifest(self.module, required=False) or {}
        files = set()
        for chunk in build.values():
            files.add(chunk["file"])
            files.update(chunk.get("css", ()))
            files.update(chunk.get("assets", ()))
        digest = hashlib.sha256(json.dumps(build, sort_keys=True).encode()).hexdigest()
        return SERVICE_WORKER % {
            "build": json.dumps(digest[:16]),
            "scope": json.dumps(self.scope),
            "precache": json.dumps([self.dist + name for name in sorted(files)]),
            "immutable": json.dumps([f"{self.dist}assets/"]),
        }

    def service_worker_response(self):
        return request.make_response(
            self.service_worker_body(),
            headers=[
                ("Content-Type", "text/javascript"),
                # A stale worker would keep serving a stale build.
                ("Cache-Control", "no-cache"),
            ],
        )


def server_version():
    """The running Odoo's major version: which transport the client takes
    (JSON-RPC's call_kw up to 18, JSON-2 from 19)."""
    return release.version_info[0]


def vite_dist(module):
    """Where ``module``'s Vite build is served: ``base`` in its vite.config."""
    return f"/{module}/static/dist/"


def read_vite_manifest(module, required=True):
    try:
        path = file_path(f"{module}/static/dist/.vite/manifest.json")
    except FileNotFoundError:
        path = None
    if not path or not os.path.isfile(path):
        if not required:
            return None
        raise InternalServerError(
            f"{module}'s frontend is not built (no static/dist/.vite/manifest.json): "
            "run `odoo module build`, or `devenv up`, whose node-watch builds it"
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def vite_entry(module, entry):
    """What a page loads for ``entry`` of ``module``'s Vite build (a key of its
    manifest, such as ``frontend/main.tsx``): the module script, every
    stylesheet the entry and the chunks it imports carry, and those chunks, to
    preload.

    The build is ``vite build`` with ``base: "/<module>/static/dist/"`` and
    ``build.manifest``: odoo-nix runs it into builtOdoo, and ``devenv up``'s
    node-watch keeps it current. The manifest is read on each render, so a
    rebuild is picked up without a restart; it is a few kilobytes.
    """
    dist = vite_dist(module)
    manifest = read_vite_manifest(module)

    css, preload, seen = [], [], set()

    def visit(key):
        if key in seen:
            return
        seen.add(key)
        chunk = manifest[key]
        for name in chunk.get("imports", ()):
            visit(name)
            preload.append(dist + manifest[name]["file"])
        css.extend(dist + name for name in chunk.get("css", ()))

    visit(entry)
    return {
        "script": dist + manifest[entry]["file"],
        "css": list(dict.fromkeys(css)),
        "preload": list(dict.fromkeys(preload)),
    }
