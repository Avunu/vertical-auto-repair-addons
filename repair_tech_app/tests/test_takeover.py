# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.tests import TransactionCase, tagged

from ..hooks import ADOPTED, post_init_hook, pre_init_hook


@tagged("post_install", "-at_install")
class TestTakeover(TransactionCase):
    """Installing the app over shopfloor_repair keeps what the shop set up."""

    def test_records_are_adopted_under_the_same_ids(self):
        group = self.env.ref("repair_tech_app.group_shop_technician")
        # As a database that has shopfloor_repair installed would have them.
        self.env.cr.execute(
            "UPDATE ir_model_data SET module = 'shopfloor_repair' "
            "WHERE module = 'repair_tech_app' AND name IN %s",
            (ADOPTED,),
        )
        self.env.registry.clear_cache()
        pre_init_hook(self.env)
        self.env.registry.clear_cache()
        self.assertEqual(self.env.ref("repair_tech_app.group_shop_technician"), group)
        self.env.cr.execute(
            "SELECT count(*) FROM ir_model_data "
            "WHERE module = 'shopfloor_repair' AND name IN %s",
            (ADOPTED,),
        )
        self.assertEqual(self.env.cr.fetchone()[0], 0)

    def test_shopfloor_technician_modules_are_removed(self):
        modules = self.env["ir.module.module"].search(
            [("name", "in", ("shopfloor_repair", "shopfloor_repair_mobile"))]
        )
        if not modules:
            self.skipTest("shopfloor_repair is not on the addons path")
        modules.write({"state": "installed"})
        post_init_hook(self.env)
        self.assertEqual(set(modules.mapped("state")), {"to remove"})


@tagged("post_install", "-at_install")
class TestTechnicianGroup(TransactionCase):
    def test_the_group_alone_grants_what_the_app_reads(self):
        group = self.env.ref("repair_tech_app.group_shop_technician")
        implied = group.trans_implied_ids
        for xmlid in (
            "stock.group_stock_user",
            "hr_timesheet.group_hr_timesheet_user",
            "fleet.fleet_group_user",
        ):
            self.assertIn(self.env.ref(xmlid), implied, xmlid)

    def test_a_user_without_it_is_refused(self):
        from odoo.exceptions import AccessError

        outsider = self.env["res.users"].create(
            {
                "name": "Olive Outsider",
                "login": "olive.outsider.tech",
                "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        with self.assertRaises(AccessError):
            self.env["repair.tech.app"].with_user(outsider).jobs()
