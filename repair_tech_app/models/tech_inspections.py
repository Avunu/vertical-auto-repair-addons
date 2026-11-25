# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import base64
import binascii
from typing import Annotated

from pydantic import Field

from odoo import Command, _, models
from odoo.exceptions import UserError

from odoo.addons.repair_tech_api.facade import aware, facade
from odoo.addons.repair_tech_api.schemas import Ref

from ..schemas import (
    InspectionDetail,
    InspectionLine,
    InspectionLineDetail,
    InspectionList,
    InspectionSummary,
    Measurement,
    Note,
    Photo,
    Severity,
    SeverityChoice,
    SeverityCounts,
)
from .repair_tech_app import _ref, _selection_label

# Grades that mean "the customer has a problem here": the ones that need a
# photo when the shop asks for one.
PROBLEM_SEVERITIES = ("today", "attention", "fail_state")

Odometer = Annotated[float, Field(gt=0)]
ImageData = Annotated[str, Field(min_length=1, max_length=20_000_000)]


# One facade model, split by screen across files on purpose.
class RepairTechApp(models.AbstractModel):
    _inherit = "repair.tech.app"  # pylint: disable=consider-merging-classes-inherited

    # ------------------------------------------------------------------
    # The job's inspections
    # ------------------------------------------------------------------

    @facade
    def inspections(self, repair_id: int) -> InspectionList:
        """The job's inspections, and the checklists one can start from."""
        return self._inspection_list(self._get_job(repair_id))

    @facade
    def create_inspection(
        self, repair_id: int, template_id: int, odometer: Odometer
    ) -> InspectionDetail:
        """Start an inspection of the job's vehicle from a checklist template,
        at the odometer reading the technician reads off the dash.

        The odometer is required: fleet_vehicle_inspection's inverse raises on
        an empty one.
        """
        repair = self._get_job(repair_id)
        vehicle = repair.vehicle_id
        if not vehicle:
            raise UserError(_("%s has no vehicle to inspect.", repair.name))
        template = (
            self.env["fleet.vehicle.inspection.template"].browse(template_id).exists()
        )
        if not template:
            raise UserError(_("That checklist no longer exists."))
        Inspection = self.env["fleet.vehicle.inspection"]
        inspection = Inspection.create(
            {
                "name": template.name or _("Inspection"),
                "repair_id": repair.id,
                "vehicle_id": vehicle.id,
                "direction": "in",
                "odometer_unit": vehicle.odometer_unit or "miles",
                "odometer": odometer,
                "inspection_template_id": template.id,
                "technician_id": self.env.uid,
                "service_advisor_id": repair.service_advisor_id.id,
            }
        )
        # What the template onchange would do, as OCA offers no method for it.
        # The values carry `state`, a stored related on the line: harmless in
        # an onchange, pointless in a write. Measurements are prefilled by
        # shop_inspection's create override.
        commands = [Command.clear()]
        for template_line in template.inspection_template_line_ids.sorted("sequence"):
            vals = Inspection._compute_line_data_for_template_change(template_line)
            vals.pop("state", None)
            commands.append(Command.create(vals))
        inspection.write({"inspection_line_ids": commands})
        return self._inspection_detail(inspection)

    @facade
    def inspection(self, inspection_id: int) -> InspectionDetail:
        """An inspection's checklist, by category."""
        return self._inspection_detail(self._get_inspection(inspection_id))

    @facade
    def inspection_line(self, line_id: int) -> InspectionLineDetail:
        """One checklist item, with its photos and grading choices."""
        return self._line_detail(self._get_line(line_id))

    @facade
    def grade(
        self,
        line_id: int,
        severity: Severity,
        condition_ids: list[int] | None = None,
        action_ids: list[int] | None = None,
        note: Note | None = None,
    ) -> InspectionDetail:
        """Grade a checklist item. ``None`` leaves conditions, actions or the
        note as they are. The severity is enough for the pass/fail result:
        shop_inspection maps it."""
        line = self._get_line(line_id)
        self._check_editable(line.inspection_id)
        if (
            self._option("require_photo_on_fail")
            and severity in PROBLEM_SEVERITIES
            and not line.inspection_line_image_ids
        ):
            raise UserError(
                _(
                    "Take a photo of %s before grading it as a problem.",
                    line.inspection_item_id.name,
                )
            )
        vals = {"severity": severity}
        if condition_ids is not None:
            vals["condition_ids"] = [Command.set(condition_ids)]
        if action_ids is not None:
            vals["recommended_action_ids"] = [Command.set(action_ids)]
        if note is not None:
            vals["result_description"] = note.strip()
        line.write(vals)
        return self._inspection_detail(line.inspection_id)

    @facade
    def set_measurement(
        self, measurement_id: int, value: float
    ) -> InspectionLineDetail:
        """Record a measured value; 0 means not measured."""
        measurement = (
            self.env["shop.inspection.measurement"].browse(measurement_id).exists()
        )
        if not measurement:
            raise UserError(_("That measurement no longer exists."))
        self._check_editable(measurement.line_id.inspection_id)
        measurement.value = value
        return self._line_detail(measurement.line_id)

    @facade
    def add_photo(
        self, line_id: int, image: ImageData, filename: str | None = None
    ) -> InspectionLineDetail:
        """Attach a photo to a checklist item: base64, bare or as a ``data:``
        URL. The app downscales it first (a tablet shot is 4-8 MB)."""
        line = self._get_line(line_id)
        self._check_editable(line.inspection_id)
        payload = image.partition(",")[2] if image.startswith("data:") else image
        try:
            base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError) as err:
            raise UserError(
                _("That photo didn't arrive whole. Take it again.")
            ) from err
        self.env["fleet.vehicle.inspection.line.image"].create(
            {
                "name": filename or line.inspection_item_id.name,
                "image_1920": payload,
                "inspection_line_id": line.id,
            }
        )
        return self._line_detail(line)

    @facade
    def remove_photo(self, photo_id: int) -> InspectionLineDetail:
        """Delete a photo taken by mistake."""
        photo = (
            self.env["fleet.vehicle.inspection.line.image"].browse(photo_id).exists()
        )
        if not photo:
            raise UserError(_("That photo no longer exists."))
        line = photo.inspection_line_id
        self._check_editable(line.inspection_id)
        photo.unlink()
        return self._line_detail(line)

    @facade
    def confirm_inspection(self, inspection_id: int) -> InspectionList:
        """Complete the inspection (OCA's ``button_confirm``). Every item needs
        a grade first; Not Applicable is the deliberate skip."""
        inspection = self._get_inspection(inspection_id)
        self._check_editable(inspection)
        ungraded = inspection.inspection_line_ids.filtered(
            lambda line: not line.severity
        )
        if ungraded:
            # button_confirm would refuse too; how many are left is more use
            # than its message.
            raise UserError(
                _(
                    "%s items still need a grade. Grade them, or mark them Not "
                    "Applicable.",
                    len(ungraded),
                )
            )
        inspection.button_confirm()
        return self._inspection_list(inspection.repair_id)

    def _get_inspection(self, inspection_id):
        inspection = self.env["fleet.vehicle.inspection"].browse(inspection_id).exists()
        if not inspection:
            raise UserError(_("That inspection no longer exists."))
        return inspection

    def _get_line(self, line_id):
        line = self.env["fleet.vehicle.inspection.line"].browse(line_id).exists()
        if not line:
            raise UserError(_("That checklist item no longer exists."))
        return line

    def _check_editable(self, inspection):
        if inspection.state != "draft":
            raise UserError(
                _("%s is completed; it can't change.", inspection.display_name)
            )

    # ------------------------------------------------------------------
    # Record -> schema
    # ------------------------------------------------------------------

    def _inspection_list(self, repair):
        vehicle = repair.vehicle_id
        return InspectionList(
            job=self._job_summary(repair),
            records=[
                self._inspection_summary(inspection)
                for inspection in repair.inspection_ids
                if inspection.state != "cancel"
            ],
            templates=[
                Ref(id=template.id, name=template.display_name)
                for template in self.env["fleet.vehicle.inspection.template"].search([])
            ],
            has_vehicle=bool(vehicle),
            default_odometer=repair.odometer_in or vehicle.odometer or 0.0,
            odometer_unit=repair.vehicle_odometer_unit or "",
        )

    def _inspection_summary(self, inspection):
        lines = inspection.inspection_line_ids
        return InspectionSummary(
            id=inspection.id,
            name=inspection.name or "",
            state=inspection.state,
            state_label=_selection_label(inspection, "state"),
            result=inspection.result,
            odometer=inspection.odometer,
            odometer_unit=inspection.odometer_unit or "",
            date_inspected=aware(inspection.date_inspected),
            template=_ref(inspection.inspection_template_id),
            graded_count=len(lines.filtered("severity")),
            line_count=len(lines),
            counts=SeverityCounts(
                today=inspection.count_today,
                good=inspection.count_good,
                future=inspection.count_future,
                attention=inspection.count_attention,
                fail_state=inspection.count_fail_state,
            ),
        )

    def _inspection_detail(self, inspection):
        lines = inspection.inspection_line_ids.sorted(
            lambda line: (
                line.category_id.sequence,
                line.category_id.id,
                line.sequence,
                line.id,
            )
        )
        return InspectionDetail(
            inspection=self._inspection_summary(inspection),
            job=self._job_summary(inspection.repair_id),
            lines=[self._inspection_line(line) for line in lines],
            editable=inspection.state == "draft",
        )

    def _inspection_line(self, line):
        return InspectionLine(
            id=line.id,
            name=line.inspection_item_id.name or "",
            category=_ref(line.category_id),
            severity=line.severity or None,
            note=line.result_description or "",
            instruction=line.inspection_item_instruction or "",
            measurement_summary=line.measurement_summary or "",
            measurement_alert=line.measurement_alert,
            conditions=[Ref(id=rec.id, name=rec.name) for rec in line.condition_ids],
            actions=[
                Ref(id=rec.id, name=rec.name) for rec in line.recommended_action_ids
            ],
            measurements=[
                Measurement(
                    id=rec.id,
                    name=rec.name,
                    position=rec.position,
                    position_label=_selection_label(rec, "position"),
                    uom_label=_selection_label(rec, "uom"),
                    value=rec.value,
                    spec_min=rec.spec_min,
                    spec_max=rec.spec_max,
                    out_of_spec=rec.out_of_spec,
                )
                for rec in line.measurement_ids
            ],
            photo_count=len(line.inspection_line_image_ids),
        )

    def _line_detail(self, line):
        """Conditions and actions: the item's usual ones first, then the rest
        of the catalogue - grading brake pads, "worn" belongs at the top, not
        among sixty in alphabetical order."""
        item = line.inspection_item_id
        conditions = item.condition_ids | self.env["shop.inspection.condition"].search(
            []
        )
        actions = item.recommended_action_ids | self.env[
            "shop.inspection.action"
        ].search([])
        model = "fleet.vehicle.inspection.line.image"
        return InspectionLineDetail(
            line=self._inspection_line(line),
            inspection=self._inspection_summary(line.inspection_id),
            photos=[
                Photo(
                    id=photo.id,
                    name=photo.name or "",
                    url=f"/web/image/{model}/{photo.id}/image_512",
                    full_url=f"/web/image/{model}/{photo.id}/image_1920",
                )
                for photo in line.inspection_line_image_ids
            ],
            severities=[
                SeverityChoice(value=value, label=label)
                for value, label in line._fields["severity"]._description_selection(
                    self.env
                )
            ],
            conditions=[Ref(id=rec.id, name=rec.name) for rec in conditions],
            actions=[Ref(id=rec.id, name=rec.name) for rec in actions],
            editable=line.inspection_id.state == "draft",
        )
