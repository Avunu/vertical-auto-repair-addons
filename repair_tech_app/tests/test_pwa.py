# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.tests import tagged

from odoo.addons.repair_tech_api.tests import common_pwa

from ..controllers.main import APP


@tagged("post_install", "-at_install")
class TestTechAppPwa(common_pwa.BuiltPwaAppCase):
    slug = "app"
    module = "repair_tech_app"
    root = "html[data-app-ready]"
    app = APP
    groups = ("base.group_user", "repair_tech_app.group_shop_technician")

    def test_api_schema_is_current(self):
        """frontend/api/ is generated from the facades; keep it fresh."""
        common_pwa.assert_schema_current(
            self, "repair_tech_app", "RepairTechApp", "repair_tech_app"
        )

    def test_deep_links_are_the_app(self):
        """The app routes on the client: a reload deep inside it is the page."""
        self.require_build()
        self.authenticate(self.user.login, self.user.login)
        response = self.url_open(f"{self.scope}jobs/42/parts")
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="app"', response.text)

    def test_manifest_shortcuts(self):
        manifest = self.url_open(f"{self.scope}manifest.webmanifest").json()
        urls = [shortcut["url"] for shortcut in manifest["shortcuts"]]
        self.assertIn(f"{self.scope}timesheets", urls)
