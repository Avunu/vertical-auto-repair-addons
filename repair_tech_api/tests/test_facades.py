# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import json
from datetime import UTC, datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

import pytz
from pydantic import AwareDatetime, Field
from pydantic import ValidationError as PydanticValidationError

from odoo import api, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged

from ..facade import FacadeSpec, api_schema, aware, facade, naive_utc
from ..schemas import Ref, Schema
from .common_pwa import TECHNICIAN_GROUPS


@tagged("post_install", "-at_install")
class TestBoardFacade(TransactionCase):
    """Runs as a technician, as the shop's TV does, so missing access rights
    show up here rather than on the wall."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.technician = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Tina Technician",
                    "login": "tina.tech.api",
                    "groups_id": [
                        (6, 0, [cls.env.ref(group).id for group in TECHNICIAN_GROUPS])
                    ],
                }
            )
        )
        brand = cls.env["fleet.vehicle.model.brand"].create({"name": "Acme"})
        cls.vehicle = cls.env["fleet.vehicle"].create(
            {
                "model_id": cls.env["fleet.vehicle.model"]
                .create({"name": "Hauler", "brand_id": brand.id})
                .id,
                "license_plate": "API-001",
                "vin_sn": "1FTFW1ET5DFC10312",
            }
        )
        cls.customer = cls.env["res.partner"].create({"name": "Wile E. Coyote"})
        cls.part = cls.env["product.product"].create(
            {"name": "Brake Pad Set", "type": "consu", "is_storable": True}
        )
        cls.repair = cls._make_repair()
        cls.env = cls.env(user=cls.technician)
        cls.Repair = cls.env["repair.order"]

    @classmethod
    def _make_repair(cls):
        repair = cls.env["repair.order"].create(
            {
                "partner_id": cls.customer.id,
                "vehicle_id": cls.vehicle.id,
                "technician_id": cls.technician.id,
                "customer_concern": "<p>Squeals when <b>braking</b></p>",
            }
        )
        cls.env["stock.move"].create(
            {
                "repair_id": repair.id,
                "repair_line_type": "add",
                "product_id": cls.part.id,
                "product_uom_qty": 2.0,
                "product_uom": cls.part.uom_id.id,
            }
        )
        repair._action_repair_confirm()
        return repair

    def test_board_needs_inventory_access(self):
        """The ACLs decide who sees the board, and say so with an AccessError
        (which the board's page shows as a message). A bare internal user is
        refused; a technician, above, is not."""
        outsider = (
            self.env["res.users"]
            .sudo()
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Olive Outsider",
                    "login": "olive.outsider.api",
                    "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
                }
            )
        )
        with self.assertRaises(AccessError):
            self.env["repair.order"].with_user(outsider).board_jobs()

    def test_board_jobs(self):
        """The board shows every open job with a board status - not just the
        current user's - and marks each with its appointment type's icon."""
        sudo = self.env["repair.order"].sudo()
        ready = self.env.ref("repair_tech_api.stage_ready_for_repair")
        Type = self.env["resource.booking.type"].sudo()
        truck = Type.create(
            {
                "name": "Truck Repair",
                "board_icon": "truck",
                "board_label": "Heavy truck",
            }
        )
        car = Type.create({"name": "Auto Repair", "board_icon": "car"})
        plain = Type.create({"name": "Inspection"})
        self.vehicle.sudo().write({"model_year": "2019"})
        self.vehicle.sudo().model_id.name = "Cascadia"
        other = self._make_repair().sudo()
        other.write(
            {"technician_id": False, "stage_id": ready.id, "booking_type_id": truck.id}
        )
        under_repair = self._make_repair().sudo()
        under_repair.booking_type_id = plain
        under_repair.action_repair_start()

        board = self.Repair.board_jobs()
        by_id = {job["id"]: job for job in board["jobs"]}
        self.assertEqual(by_id[other.id]["status"], "ready")
        self.assertIsNone(by_id[other.id]["technician_id"])
        self.assertEqual(by_id[other.id]["vehicle"], "2019 Cascadia")
        self.assertEqual(
            by_id[other.id]["job_type"],
            {"id": truck.id, "label": "Heavy truck", "icon": "truck"},
        )
        # A type without an icon leaves the card unmarked.
        self.assertIsNone(by_id[under_repair.id]["job_type"])
        # The key lists the types with an icon; the label defaults to the name.
        self.assertIn(
            {"id": car.id, "label": "Auto Repair", "icon": "car"}, board["job_types"]
        )
        self.assertNotIn(plain.id, [t["id"] for t in board["job_types"]])
        self.assertEqual(by_id[other.id]["number"], str(int(other.name[-5:])))
        self.assertEqual(by_id[other.id]["customer"], "Wile E. Coyote")
        self.assertEqual(by_id[under_repair.id]["status"], "repair")
        # Confirmed has no board status, so it stays off the board.
        self.assertNotIn(self.repair.id, by_id)
        self.assertIn(
            {"id": self.technician.id, "name": "Tina Technician"},
            board["technicians"],
        )
        waiting = self.env.ref("repair_stage.stage_waiting_parts")
        sudo.browse(self.repair.id).write({"stage_id": waiting.id})
        self.assertEqual(
            {job["id"]: job["status"] for job in self.Repair.board_jobs()["jobs"]}[
                self.repair.id
            ],
            "parts",
        )

    def test_board_jobs_follow_the_schedule(self):
        """Today and earlier days show, and so does a job with no date yet;
        a job booked for a later day waits."""
        ready = self.env.ref("repair_tech_api.stage_ready_for_repair")
        now = fields.Datetime.now()

        def job(schedule_date):
            repair = self._make_repair().sudo()
            repair.stage_id = ready
            # Straight to the column: writing the date would book an
            # appointment (shop_scheduling), which is not what's tested.
            self.env.cr.execute(
                "UPDATE repair_order SET schedule_date = %s WHERE id = %s",
                (schedule_date, repair.id),
            )
            repair.invalidate_recordset(["schedule_date"])
            return repair.id

        today = job(now)
        overdue = job(now - timedelta(days=3))
        unscheduled = job(None)
        tomorrow = job(now + timedelta(days=1))
        next_week = job(now + timedelta(days=7))

        shown = {job["id"] for job in self.Repair.board_jobs()["jobs"]}
        self.assertLessEqual({today, overdue, unscheduled}, shown)
        self.assertFalse({tomorrow, next_week} & shown)

    def test_board_day_ends_at_the_users_midnight(self):
        """Tomorrow starts at midnight where the user is, not in UTC."""
        user = self.technician.sudo()
        user.tz = "Pacific/Auckland"  # a day ahead of UTC for half of each day
        cutoff = self.Repair.with_user(user)._board_cutoff()
        local = pytz.utc.localize(cutoff).astimezone(pytz.timezone("Pacific/Auckland"))
        self.assertEqual((local.hour, local.minute), (0, 0))
        self.assertGreater(cutoff, fields.Datetime.now())
        self.assertLessEqual(cutoff - fields.Datetime.now(), timedelta(days=1))

    def test_board_over_call_kw(self):
        """The path the board takes: /web/dataset/call_kw -> api.call_kw, and
        JSON-safe all the way down."""
        board = api.call_kw(self.Repair, "board_jobs", [], {})
        json.dumps(board)
        self.assertEqual(set(board), {"jobs", "technicians", "job_types"})


class Payload(Schema):
    ref: Ref
    when: AwareDatetime | None = None


@tagged("post_install", "-at_install")
class TestFacadeMechanics(TransactionCase):
    """``@facade`` itself, on a plain function: no model needed."""

    def setUp(self):
        super().setUp()

        def echo(
            self, count: int, payload: Payload, note: str | None = None
        ) -> Payload:
            """Echo the payload back."""
            return Payload(ref=Ref(id=payload.ref.id + count, name=note or "x"))

        self.echo = facade(echo)
        self.spec = FacadeSpec(echo)

    def test_params_are_validated(self):
        payload = {"ref": {"id": 1, "name": "a"}}
        with self.assertRaisesRegex(ValidationError, "count"):
            self.echo(None, payload=payload)
        with self.assertRaisesRegex(ValidationError, "count"):
            self.echo(None, count="two", payload=payload)
        with self.assertRaisesRegex(ValidationError, "Extra inputs|unexpected"):
            self.echo(None, count=1, payload=payload, sudo=True)
        with self.assertRaisesRegex(ValidationError, "payload.ref.name"):
            self.echo(None, count=1, payload={"ref": {"id": 1}})

    def test_constraints_hold(self):
        """Annotated[..., Field(...)] limits are part of the contract."""

        def positive(self, count: Annotated[int, Field(gt=0)]) -> int:
            return count

        with self.assertRaisesRegex(ValidationError, "greater than 0"):
            facade(positive)(None, count=0)
        self.assertEqual(facade(positive)(None, count=1), 1)

    def test_result_is_dumped_to_json(self):
        result = self.echo(None, count=2, payload={"ref": {"id": 1, "name": "a"}})
        self.assertEqual(result, {"ref": {"id": 3, "name": "x"}, "when": None})

    def test_result_is_checked(self):
        """A body that builds the wrong shape fails here, not in the app."""

        def wrong(self) -> Ref:
            return {"id": "not a number", "name": "x"}

        with self.assertRaises(PydanticValidationError):
            facade(wrong)(None)

    def test_needs_annotations(self):
        def bare(self, x):
            return x

        with self.assertRaises(TypeError):
            FacadeSpec(bare)

    def test_datetimes(self):
        """What a browser sends (with an offset) -> what Odoo stores (naive
        UTC) -> what goes back (with the offset again)."""
        sent = datetime(2026, 3, 1, 9, 30, tzinfo=ZoneInfo("America/New_York"))
        stored = naive_utc(sent)
        self.assertIsNone(stored.tzinfo)
        self.assertEqual(aware(stored), sent)
        self.assertEqual(aware(stored).tzinfo, UTC)
        self.assertIsNone(naive_utc(None))
        self.assertIsNone(aware(False))

    def test_schema(self):
        schema = api_schema("repair_tech_api", "RepairTechApi")
        board = schema["$defs"]["RepairOrderMethods"]["properties"]
        self.assertIn("board_jobs", board)
        self.assertIn("Board", schema["$defs"])
