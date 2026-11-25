# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.repair_tech_api.tests import common_pwa

from ..controllers.main import APP


@tagged("post_install", "-at_install")
class TestBoardPwa(common_pwa.BuiltPwaAppCase):
    slug = "board"
    module = "repair_tech_board"
    root = ".board"
    app = APP

    def test_ipad_bar_is_dark(self):
        """The installed app's status bar belongs to the dark board."""
        self.assertEqual(APP.status_bar_style, "black")

    def test_app_says_when_the_user_lacks_access(self):
        """A user without Inventory access is told so, not that the server is
        down. Odoo logs the refused call as a warning, which is expected here."""
        self.require_build()
        reader = self.env["res.users"].create(
            {
                "name": "Pwa Outsider",
                "login": "pwa.outsider.board",
                "password": "pwa.outsider.board",
                "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        with mute_logger("odoo.http"):
            self.browser_js(
                self.scope,
                "console.log('test successful')",
                ready="document.querySelector('.loading')"
                '?.textContent.includes("not allowed to see the board")',
                login=reader.login,
            )

    def test_api_schema_is_current(self):
        """frontend/api/ is generated from the board's facade; keep it fresh."""
        common_pwa.assert_schema_current(
            self, "repair_tech_api", "RepairTechBoardApi", "repair_tech_board"
        )
