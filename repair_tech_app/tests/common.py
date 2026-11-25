# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import UTC, datetime

from odoo.tests import TransactionCase

# 1x1 transparent PNG: small enough to inline, real enough for image.mixin.
PNG_1PX = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

DAY = datetime(2026, 1, 5)


def at(hour, minute=0):
    """A naive UTC time on DAY, as Odoo stores it."""
    return DAY.replace(hour=hour, minute=minute)


def utc(value):
    """A naive UTC time as the app sends it: with its offset."""
    return value.replace(tzinfo=UTC)


class TechCase(TransactionCase):
    """A technician holding only the Technician group (and Internal User), so
    a missing access right fails here rather than in the shop.

    ``self.app`` is the facade model as that technician; facades return what
    call_kw would send, plain JSON-safe values.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.company
        cls.technician = cls._make_technician("Tina Technician", "tina.tech")
        cls.employee = cls.technician.employee_id
        cls.labor_project = cls.env["project.project"].create(
            {"name": "Shop Labor", "allow_timesheets": True}
        )
        cls.company.repair_timesheet_project_id = cls.labor_project
        brand = cls.env["fleet.vehicle.model.brand"].create({"name": "Acme"})
        cls.vehicle = cls.env["fleet.vehicle"].create(
            {
                "model_id": cls.env["fleet.vehicle.model"]
                .create({"name": "Hauler", "brand_id": brand.id})
                .id,
                "license_plate": "SHOP-001",
                "vin_sn": "1FTFW1ET5DFC10312",
                "odometer_unit": "miles",
            }
        )
        cls.customer = cls.env["res.partner"].create({"name": "Wile E. Coyote"})
        cls.part = cls._make_product("Brake Pad Set", "BP-100", "RTA-TEST-BP-100")
        cls.other_part = cls._make_product("Oil Filter", "OF-200", "RTA-TEST-OF-200")
        cls.labor = cls.env["product.product"].create(
            {"name": "Brake Job", "type": "service"}
        )
        cls.diag = cls.env["product.product"].create(
            {"name": "Diagnostics", "type": "service"}
        )
        cls.repair = cls._make_repair()
        cls.brakes, cls.diagnostics = cls.repair.repair_service_ids.sorted("id")
        cls.app = cls.env["repair.tech.app"].with_user(cls.technician)

    @classmethod
    def _make_technician(cls, name, login):
        user = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": name,
                    "login": login,
                    "password": login,
                    "email": f"{login}@example.com",
                    "tz": "UTC",
                    "groups_id": [
                        (
                            6,
                            0,
                            [
                                cls.env.ref("base.group_user").id,
                                cls.env.ref("repair_tech_app.group_shop_technician").id,
                            ],
                        )
                    ],
                }
            )
        )
        cls.env["hr.employee"].create({"name": name, "user_id": user.id})
        return user

    @classmethod
    def _make_product(cls, name, code, barcode, tracking="none"):
        return cls.env["product.product"].create(
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

    @classmethod
    def _make_repair(
        cls, technician=None, state="confirmed", parts=None, services=True
    ):
        repair = cls.env["repair.order"].create(
            {
                "partner_id": cls.customer.id,
                "vehicle_id": cls.vehicle.id,
                "odometer_in": 42000,
                "technician_id": (technician or cls.technician).id,
                "customer_concern": "<p>Squeals when <b>braking</b></p>",
            }
        )
        for product, qty in parts if parts is not None else [(cls.part, 2.0)]:
            cls.env["stock.move"].create(
                {
                    "repair_id": repair.id,
                    "repair_line_type": "add",
                    "product_id": product.id,
                    "product_uom_qty": qty,
                    "product_uom": product.uom_id.id,
                }
            )
        if services:
            for product in (cls.labor, cls.diag):
                cls.env["repair.service"].create(
                    {"repair_id": repair.id, "product_id": product.id, "accepted": True}
                )
        if state in ("confirmed", "under_repair"):
            repair._action_repair_confirm()
        if state == "under_repair":
            repair.action_repair_start()
        return repair

    def ids(self, records):
        return [record["id"] for record in records]

    def line(self, repair, start, end, service=None, employee=None):
        """A stopped timesheet entry on a job, start-end (naive UTC)."""
        return self.env["account.analytic.line"].create(
            {
                "name": "Work",
                "project_id": self.labor_project.id,
                "employee_id": (employee or self.employee).id,
                "repair_order_id": repair.id,
                "repair_service_id": service.id if service else False,
                "date": start.date(),
                "date_time": start,
                "unit_amount": (end - start).total_seconds() / 3600,
            }
        )

    def attendance(self, check_in, check_out):
        return self.env["hr.attendance"].create(
            {
                "employee_id": self.employee.id,
                "check_in": check_in,
                "check_out": check_out,
            }
        )
