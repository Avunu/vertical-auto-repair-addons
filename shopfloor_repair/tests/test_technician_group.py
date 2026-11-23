# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTechnicianGroup(TransactionCase):
    def test_the_technician_group_alone_grants_what_the_app_reads(self):
        user = self.env["res.users"].create(
            {
                "name": "Group only",
                "login": "group.only",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("shopfloor_repair.group_shop_technician").id,
                        ],
                    )
                ],
            }
        )
        for xmlid in (
            "shopfloor_base.group_shopfloor_user",
            "stock.group_stock_user",
            "hr_timesheet.group_hr_timesheet_user",
            "fleet.fleet_group_user",
        ):
            self.assertTrue(user.has_group(xmlid), xmlid)
