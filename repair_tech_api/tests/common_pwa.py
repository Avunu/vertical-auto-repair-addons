# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import pathlib
import re

from odoo.tests import HttpCase
from odoo.tools.misc import file_path

from ..facade import api_schema
from ..tools.export_api_schema import render


def assert_schema_current(case, modules, title, addon):
    """The frontend's types are generated from the facades: fail when the
    committed ``frontend/api/api.schema.json`` no longer matches them."""
    output = pathlib.Path(file_path(addon)) / "frontend/api/api.schema.json"
    case.assertTrue(output.exists(), f"{output} is missing: run `pnpm run generate`")
    case.assertEqual(
        output.read_text(),
        render(api_schema(modules, title)),
        f"{output} is stale: run `pnpm run generate` in {addon}",
    )


# What the shop's screens sign in as: the app's own call_kw requests run as
# this user, so these are the groups the facades need (Inventory/User reads
# repair orders and their stages, Fleet/User their vehicles). Anything less is
# refused by the ACLs, not by the app. The technician app's tests use its own
# Shop Floor Technician group, which implies these.
TECHNICIAN_GROUPS = (
    "base.group_user",
    "stock.group_stock_user",
    "fleet.fleet_group_user",
)


class PwaAppCase(HttpCase):
    """What every technician frontend must serve. Subclass with ``slug``.

    The tests sign in as a technician (``TECHNICIAN_GROUPS``), not a bare
    internal user: the browser tests mount the real app, whose API calls run as
    that user, and a user the ACLs refuse is a different thing to test.
    """

    # Odoo 18's loader only collects a class's own test methods otherwise.
    allow_inherited_tests_method = True
    slug = None
    app = None  # the controller's PwaApp, to check the head without the page
    groups = TECHNICIAN_GROUPS  # xmlids of the groups the signed-in user gets

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.scope = f"/repair-tech/{cls.slug}/"
        cls.user = cls.env["res.users"].create(
            {
                "name": "Pwa Tester",
                "login": f"pwa.tester.{cls.slug}",
                "password": f"pwa.tester.{cls.slug}",
                "groups_id": [(6, 0, [cls.env.ref(group).id for group in cls.groups])],
            }
        )

    def open_page(self):
        self.authenticate(self.user.login, self.user.login)
        response = self.url_open(self.scope)
        self.assertEqual(response.status_code, 200)
        return response.text

    def test_page_needs_login(self):
        response = self.url_open(self.scope, allow_redirects=False)
        self.assertIn(response.status_code, (302, 303))
        self.assertIn("/web/login", response.headers["Location"])

    def test_head_makes_it_installable(self):
        """The tags, from the shared head template alone: a compiled app's page
        can't render until it is built, but its head can."""
        if self.app is None:
            self.skipTest("the test case names no PwaApp")
        head = self.env["ir.ui.view"]._render_template(
            "repair_tech_api.pwa_head", {"pwa": self.app}
        )
        if isinstance(head, bytes):
            head = head.decode()
        self.assertIn(f'href="{self.scope}manifest.webmanifest"', head)
        self.assertIn(f'"{self.scope}sw.js"', head)
        self.assertIn('rel="apple-touch-icon"', head)
        self.assertIn('name="apple-mobile-web-app-capable"', head)
        bar = re.search(
            r'<meta[^>]*name="apple-mobile-web-app-status-bar-style"[^>]*>', head
        )
        self.assertTrue(bar, "iOS's status bar style should be set")
        self.assertIn(f'content="{self.app.status_bar_style}"', bar.group(0))

    def test_page_is_installable(self):
        page = self.open_page()
        self.assertIn(f'href="{self.scope}manifest.webmanifest"', page)
        self.assertIn(f'"{self.scope}sw.js"', page)
        # iOS ignores the manifest's icons and wants these to install.
        self.assertIn('rel="apple-touch-icon"', page)
        self.assertIn('name="apple-mobile-web-app-capable"', page)

    def test_manifest(self):
        manifest = self.url_open(f"{self.scope}manifest.webmanifest").json()
        self.assertEqual(manifest["scope"], self.scope)
        self.assertEqual(manifest["start_url"], self.scope)
        self.assertEqual(manifest["display"], "standalone")
        for icon in manifest["icons"]:
            self.assertEqual(self.url_open(icon["src"]).status_code, 200, icon["src"])

    def test_service_worker(self):
        response = self.url_open(f"{self.scope}sw.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response.headers["Content-Type"])
        self.assertIn("no-cache", response.headers["Cache-Control"])
        self.assertIn("addEventListener", response.text)
        self.assertIn(f"const SCOPE = {self.scope!r};".replace("'", '"'), response.text)

    def test_page_says_which_transport(self):
        page = self.open_page()
        self.assertRegex(page, r'name="odoo-server-version"\s+content="\d+"')


class BuiltPwaAppCase(PwaAppCase):
    """For compiled frontends (Vite, ``vite_entry``): the page loads the build,
    Odoo serves it, the app mounts in Chrome, and nothing comes from a CDN.
    Subclass with ``module`` and ``root``, a selector the mounted app renders."""

    module = None
    root = None

    def require_build(self):
        """Skip unless ``static/dist/`` is built. It isn't committed, and the
        CI test gate runs on the source tree, which has no build step: the
        page answers 500 there (``vite_entry``). ``odoo module build custom``
        builds it, and then these run. Rebuild after changing a frontend: a
        stale ``dist`` fails the tests that check the new text."""
        try:
            file_path(f"{self.module}/static/dist/.vite/manifest.json")
        except FileNotFoundError:
            self.skipTest(f"{self.module} is not built: run `odoo module build custom`")

    def open_page(self):
        self.require_build()
        return super().open_page()

    def test_page_loads_the_build(self):
        dist = f"/{self.module}/static/dist/assets/"
        page = self.open_page()
        script = re.search(rf'src="({re.escape(dist)}[^"]+\.js)"', page)
        self.assertTrue(script, "the page should load the built entry from static/dist")
        styles = re.findall(rf'href="({re.escape(dist)}[^"]+\.css)"', page)
        for url in (script.group(1), *styles):
            self.assertEqual(self.url_open(url).status_code, 200, url)
        self.assertIn(
            "javascript", self.url_open(script.group(1)).headers["Content-Type"]
        )

    def test_app_mounts(self):
        # In Chrome: the bundle runs, mounts, and renders the app's root.
        self.require_build()
        self.browser_js(
            self.scope,
            "console.log('test successful')",
            ready=f"Boolean(document.querySelector({self.root!r}))",
            login=self.user.login,
        )

    def test_nothing_from_a_cdn(self):
        page = self.open_page()
        self.assertNotIn("esm.run", page)
        self.assertNotIn("cdn.jsdelivr.net", page)
        sw = self.url_open(f"{self.scope}sw.js").text
        self.assertIn(f'"/{self.module}/static/dist/assets/"', sw)

    def test_worker_precaches_the_build(self):
        """Every hashed file of the build is in the worker's install list, so
        an installed app opens with no network."""
        self.require_build()
        sw = self.url_open(f"{self.scope}sw.js").text
        page = self.open_page()
        script = re.search(r'<script type="module" src="([^"]+)"', page).group(1)
        self.assertIn(f'"{script}"', sw)
