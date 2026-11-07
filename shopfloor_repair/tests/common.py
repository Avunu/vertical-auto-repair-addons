# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.addons.shopfloor_base.tests.common import CommonCase


class RepairJobCase(CommonCase):
    """Base case for the repair_job scenario.

    Everything runs as a real technician (not a manager) so that missing
    access rights show up here rather than on the shop floor.
    """

    @classmethod
    def _shopfloor_user_values(cls):
        values = super()._shopfloor_user_values()
        values["name"] = "Tina Technician"
        values["login"] = "tina.technician"
        values["email"] = "tina@example.com"
        values["groups_id"] = [
            (
                6,
                0,
                [
                    cls.env.ref("shopfloor_base.group_shopfloor_user").id,
                    cls.env.ref("stock.group_stock_user").id,
                    cls.env.ref("hr_timesheet.group_hr_timesheet_user").id,
                    cls.env.ref("fleet.fleet_group_user").id,
                    cls.env.ref("shopfloor_repair.group_shop_technician").id,
                ],
            )
        ]
        return values

    @classmethod
    def setUpClassVars(cls):
        res = super().setUpClassVars()
        cls.company = cls.env.company
        cls.technician = cls.shopfloor_user
        cls.profile = cls.env.ref("shopfloor_repair.shopfloor_profile_technician")
        cls.menu = cls.env.ref("shopfloor_repair.shopfloor_menu_my_jobs")
        return res

    @classmethod
    def setUpClassBaseData(cls):
        res = super().setUpClassBaseData()
        cls.employee = (
            cls.env["hr.employee"]
            .sudo()
            .create(
                {
                    "name": "Tina Technician",
                    "user_id": cls.technician.id,
                    "company_id": cls.company.id,
                }
            )
        )
        cls.labor_project = (
            cls.env["project.project"]
            .sudo()
            .create(
                {
                    "name": "Shop Labor",
                    "allow_timesheets": True,
                    "company_id": cls.company.id,
                }
            )
        )
        cls.company.sudo().repair_timesheet_project_id = cls.labor_project

        cls.brand = cls.env["fleet.vehicle.model.brand"].sudo().create({"name": "Acme"})
        cls.vehicle_model = (
            cls.env["fleet.vehicle.model"]
            .sudo()
            .create({"name": "Hauler", "brand_id": cls.brand.id})
        )
        cls.customer = cls.env["res.partner"].sudo().create({"name": "Wile E. Coyote"})
        cls.vehicle = (
            cls.env["fleet.vehicle"]
            .sudo()
            .create(
                {
                    "model_id": cls.vehicle_model.id,
                    "license_plate": "SHOP-001",
                    "vin_sn": "1FTFW1ET5DFC10312",
                    "odometer_unit": "miles",
                    "company_id": cls.company.id,
                }
            )
        )

        cls.part = cls._make_product("Brake Pad Set", "BP-100", "SFR-TEST-BP-100")
        cls.other_part = cls._make_product("Oil Filter", "OF-200", "SFR-TEST-OF-200")

        cls.repair = cls._make_repair()
        return res

    @classmethod
    def _make_product(cls, name, code, barcode, tracking="none"):
        return (
            cls.env["product.product"]
            .sudo()
            .create(
                {
                    "name": name,
                    "type": "consu",
                    "is_storable": True,
                    "default_code": code,
                    "barcode": barcode,
                    "tracking": tracking,
                    "purchase_ok": True,
                }
            )
        )

    @classmethod
    def _make_repair(cls, technician=None, state="confirmed", parts=None):
        repair = (
            cls.env["repair.order"]
            .sudo()
            .create(
                {
                    "partner_id": cls.customer.id,
                    "vehicle_id": cls.vehicle.id,
                    "odometer_in": 42000,
                    "technician_id": (technician or cls.technician).id,
                    "company_id": cls.company.id,
                }
            )
        )
        for product, qty in parts if parts is not None else [(cls.part, 2.0)]:
            cls.env["stock.move"].sudo().create(
                {
                    "repair_id": repair.id,
                    "repair_line_type": "add",
                    "product_id": product.id,
                    "product_uom_qty": qty,
                    "product_uom": product.uom_id.id,
                    "company_id": repair.company_id.id,
                }
            )
        if state == "confirmed":
            repair.sudo()._action_repair_confirm()
        elif state == "under_repair":
            repair.sudo().action_repair_start()
        return repair

    # -- service helpers --------------------------------------------------

    def service_for(self, **kw):
        """Build the service with menu AND profile in the work context.

        ``CommonCase.get_service`` assigns the menu *after* construction,
        which is too late for ``BaseShopfloorService.__init__`` to pick it up
        -- and without it ``self.options`` never sees the scenario options.
        """
        params = {"profile": self.profile, "menu": self.menu}
        params.update(kw)
        with self.work_on_services(**params) as work:
            service = work.component(usage="repair_job")
            self.env["shopfloor.app"]._prepare_non_decorated_endpoints(service)
            return service

    def _dispatch(self, method_name, service=None, **params):
        service = service or self.service_for()
        return service.dispatch(method_name, params=params)

    # -- assertions -------------------------------------------------------

    def assert_next_state(self, response, expected):
        self.assertEqual(
            response.get("next_state"),
            expected,
            f"message={response.get('message')}",
        )

    def assert_no_error(self, response):
        message = response.get("message") or {}
        self.assertNotEqual(
            message.get("message_type"),
            "error",
            f"unexpected error: {message.get('body')}",
        )

    def assert_error(self, response):
        message = response.get("message") or {}
        self.assertEqual(message.get("message_type"), "error", str(response))

    def state_data(self, response):
        return response["data"][response["next_state"]]
