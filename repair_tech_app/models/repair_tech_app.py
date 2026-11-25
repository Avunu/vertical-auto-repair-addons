# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from lxml import etree
from lxml import html as lxml_html

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools import str2bool

from odoo.addons.repair_tech_api.facade import aware
from odoo.addons.repair_tech_api.schemas import Ref

from ..schemas import JobSummary, RunningTimer, Vehicle

# States in which the technician may still change parts.
EDITABLE_REPAIR_STATES = ("draft", "confirmed", "under_repair")

# ir.config_parameter keys behind Settings > Inventory > Technician App.
PARAM = "repair_tech_app.{}"


class RepairTechApp(models.AbstractModel):
    """The technician app's facades: one model, so the app calls
    ``repair.tech.app/<method>`` over call_kw today and JSON-2 tomorrow.

    The facades are split by screen across this folder (jobs, parts,
    inspections, timesheets), all on this model. They run as the signed-in
    technician, without ``sudo`` unless a comment says why, so Odoo's ACLs and
    record rules decide what they can touch: the Shop Floor Technician group
    (security/) is what grants it.

    Errors are plain ``UserError``s. call_kw (and JSON-2) run each request in
    one transaction and roll all of it back on an exception, so a facade that
    raises half way leaves nothing behind.
    """

    _name = "repair.tech.app"
    _description = "Technician App"

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _option(self, name, default=False):
        value = self.env["ir.config_parameter"].sudo().get_param(PARAM.format(name))
        # Settings delete a boolean parameter turned off; data/ sets the
        # defaults that are on, so a missing one means off.
        return False if value is None else str2bool(value, default)

    def _option_int(self, name, default):
        value = self.env["ir.config_parameter"].sudo().get_param(PARAM.format(name))
        try:
            return max(int(value), 1) if value else default
        except ValueError:
            return default

    # ------------------------------------------------------------------
    # Jobs
    # ------------------------------------------------------------------

    def _job_domain(self):
        """Jobs on "My Jobs".

        Confirmed and under-repair jobs show up whatever their services'
        acceptance. A *draft* job shows once it has an accepted service: the
        office can accept just "Diagnostics" and send the job out before
        confirming the repair, so the technician can diagnose it and report
        what else it needs. Without an accepted service there is nothing for
        them to do yet.

        Besides their own jobs, a technician sees every job of an appointment
        type they are bookable for (the type is the pool of people who can do
        that work, and any of them may pick it up), and, unless the shop turns
        it off, the jobs nobody has yet.
        """
        uid = self.env.uid
        assignment = [
            [("technician_id", "=", uid)],
            [("booking_type_user_ids", "in", uid)],
        ]
        if self._option("include_responsible"):
            assignment.append([("user_id", "=", uid)])
        if self._option("show_unassigned", True):
            assignment.append([("technician_id", "=", False)])
        state = expression.OR(
            [
                [("state", "in", ("confirmed", "under_repair"))],
                [("state", "=", "draft"), ("repair_service_ids.accepted", "=", True)],
            ]
        )
        return expression.AND(
            [
                state,
                expression.OR(assignment),
                [("company_id", "in", self.env.companies.ids)],
            ]
        )

    def _job_search(self):
        return self.env["repair.order"].search(
            self._job_domain(), order="priority desc, schedule_date asc, id asc"
        )

    def _get_job(self, repair_id):
        """One job. Not filtered by the list's domain: a job just finished
        drops off the list, but the screen showing it still needs it."""
        repair = self.env["repair.order"].browse(repair_id).exists()
        if not repair:
            raise UserError(_("That job no longer exists."))
        return repair

    def _get_service(self, repair, service_id):
        """An accepted service of the job. Only accepted ones: the customer
        hasn't agreed to pay for the rest, so they get no timer."""
        service = self.env["repair.service"].browse(service_id).exists()
        if not service or service.repair_id != repair or not service.accepted:
            raise UserError(_("That service isn't an accepted service on this job."))
        return service

    def _job_parts(self, repair):
        """The parts the technician installs: ``add`` moves. Parts coming off
        the vehicle (remove, recycle) are not the app's business."""
        return repair.move_ids.filtered(
            lambda move: move.repair_line_type == "add" and move.state != "cancel"
        )

    def _check_parts_editable(self, repair):
        if repair.state not in EDITABLE_REPAIR_STATES:
            raise UserError(_("%s is closed; its parts can't change.", repair.name))

    # ------------------------------------------------------------------
    # Timers
    # ------------------------------------------------------------------

    def _running_lines(self, repair=None, service=None):
        """The current user's running timer lines, optionally narrowed.

        ``_running_domain`` is user-global by design (a start time, no
        duration yet), so without a narrowing this is the timer on *any* job:
        what "one running timer per person" needs.
        """
        AAL = self.env["account.analytic.line"]
        domain = AAL._running_domain()
        if repair is not None:
            domain = expression.AND([domain, [("repair_order_id", "=", repair.id)]])
        if service is not None:
            domain = expression.AND([domain, [("repair_service_id", "=", service.id)]])
        return AAL.search(domain)

    def _running_timer(self, line):
        line = line[:1]
        if not line or not line.repair_service_id:
            return None
        return RunningTimer(
            repair_id=line.repair_order_id.id,
            service_id=line.repair_service_id.id,
            job_label=_job_label(line.repair_order_id),
            service_name=_service_name(line.repair_service_id),
            started_at=aware(line.date_time),
        )

    # ------------------------------------------------------------------
    # Record -> schema
    # ------------------------------------------------------------------

    def _job_summary_values(self, repair, running=None):
        if running is None:
            running = self._running_lines(repair)
        parts = self._job_parts(repair)
        lines = repair._shop_get_inspection_lines()
        vehicle = repair.vehicle_id
        return {
            "id": repair.id,
            "name": repair.name,
            "label": _job_label(repair),
            "state": repair.state,
            "state_label": _selection_label(repair, "state"),
            "stage": _ref(repair.stage_id),
            "priority": repair.priority == "1",
            "schedule_date": aware(repair.schedule_date),
            "partner": _ref(repair.partner_id),
            "vehicle": Vehicle(
                id=vehicle.id,
                description=vehicle_description(vehicle),
                license_plate=vehicle.license_plate or None,
                vin=vehicle.vin_sn or None,
                model_year=vehicle.model_year or None,
                unit_number=vehicle.unit_number or None,
            )
            if vehicle
            else None,
            "technician": _ref(repair.technician_id),
            "is_mine": repair.technician_id == self.env.user,
            "customer_concern": plaintext(repair.customer_concern),
            "timer_running": bool(
                running.filtered(lambda line: line.repair_order_id == repair)
            ),
            "parts_done": len(parts.filtered("picked")),
            "parts_total": len(parts),
            "inspection_graded": len(lines.filtered("severity")),
            "inspection_total": len(lines),
        }

    def _job_summary(self, repair, running=None):
        return JobSummary(**self._job_summary_values(repair, running))

    def _now(self):
        return fields.Datetime.now()


def vehicle_description(vehicle):
    """Colour/Year/Brand/Model/Plate/Unit, e.g. "Silver/2005/Acme/Hauler/
    SHOP-001/T-104": slash-separated like fleet's own name, but leading with
    what a technician sees walking up to the car. Missing parts are skipped."""
    if not vehicle:
        return ""
    parts = (
        vehicle.color,
        vehicle.model_year,
        vehicle.model_id.brand_id.name,
        vehicle.model_id.name,
        vehicle.license_plate,
        vehicle.unit_number,
    )
    return "/".join(part.strip() for part in parts if part and part.strip())


def _job_label(repair):
    """What the app calls a job wherever it has room for one name."""
    return (
        vehicle_description(repair.vehicle_id) or repair.partner_id.name or repair.name
    )


def _service_name(service):
    """What the technician knows a service by: its product, not the line's
    computed description."""
    return service.product_id.name or service.display_name


def _ref(record):
    return Ref(id=record.id, name=record.display_name) if record else None


def _selection_label(record, field):
    value = record[field]
    if not value:
        return ""
    return dict(record._fields[field]._description_selection(record.env))[value]


BLOCKS = ("p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote")


def plaintext(value):
    """Html field -> plain text, keeping its line and paragraph breaks and
    nothing else (html2plaintext would add markdown: *bold*). The app never
    renders markup it was sent."""
    if not value:
        return ""
    try:
        root = lxml_html.fragment_fromstring(str(value), create_parent="div")
    except etree.ParserError:
        return ""
    for br in root.iter("br"):
        br.tail = "\n" + (br.tail or "")
    for block in root.iter(*BLOCKS):
        block.tail = "\n" + (block.tail or "")
    lines = [" ".join(line.split()) for line in root.text_content().splitlines()]
    text = "\n".join(lines)
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.strip()
