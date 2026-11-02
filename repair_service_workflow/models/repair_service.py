# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class RepairService(models.Model):
    _inherit = "repair.service"

    accepted = fields.Boolean(
        default=False,
        help="Kept on the repair order through confirmation and repair. "
        "Unaccepted lines stay visible until a quotation is created from "
        "the order, at which point they are archived instead of billed.",
    )
    active = fields.Boolean(default=True)
    estimated_time = fields.Float(
        "Estimated Time", digits="Product Unit of Measure"
    )
    analytic_line_ids = fields.One2many(
        "account.analytic.line", "repair_service_id", string="Time Logs"
    )
    actual_time = fields.Float(
        compute="_compute_actual_time",
        store=True,
        readonly=False,
        digits="Product Unit of Measure",
        help="Sum of the time logged against this service from the shop "
        "floor app. Directly editable; a later timer stop recomputes and "
        "overwrites a manual edit.",
    )
    # Overrides the plain `default=1.0` float defined upstream
    # (OCA/repair's `repair_service`) with a compute so the invoiced
    # quantity tracks logged time instead of always starting at a flat 1 --
    # `actual_time` is already stored as decimal hours (the "01:07" shown
    # via its `float_time` widget is purely a display format; the
    # underlying float is 1.1167), so no HH:MM parsing is needed here, just
    # reading the same number. Same store=True/readonly=False pattern as
    # `actual_time` itself: auto-fills, stays directly editable, and a
    # later timer stop recomputes and overwrites a manual edit.
    product_uom_qty = fields.Float(
        compute="_compute_product_uom_qty",
        store=True,
        readonly=False,
        digits="Product Unit of Measure",
        help="Defaults to the logged Actual Time, in decimal hours. "
        "Directly editable; a later timer stop recomputes and overwrites "
        "a manual edit.",
    )
    has_running_timer = fields.Boolean(
        compute="_compute_has_running_timer",
        help="A technician currently has a timer running on this service "
        "in the shop floor app.",
    )

    @api.depends("analytic_line_ids.unit_amount")
    def _compute_actual_time(self):
        for service in self:
            service.actual_time = sum(
                service.analytic_line_ids.mapped("unit_amount")
            )

    @api.depends("actual_time")
    def _compute_product_uom_qty(self):
        for service in self:
            service.product_uom_qty = service.actual_time or 1.0

    @api.depends("analytic_line_ids.unit_amount")
    def _compute_has_running_timer(self):
        # A zero duration is what marks a line as still running -- the same
        # convention `shopfloor_repair`'s timer endpoints and `data.py`'s
        # payloads rely on (the running line carries `unit_amount = 0`
        # until it is stopped). Deliberately not scoped to a particular
        # employee/user: the office reviewing this checkbox is not the
        # technician whose timer it is.
        for service in self:
            service.has_running_timer = bool(
                service.analytic_line_ids.filtered(lambda line: not line.unit_amount)
            )

    def _create_repair_sale_order_line(self):
        # Only accepted services are ever billed. Unaccepted rows never get
        # a sale_line_id in the first place; they are archived instead once
        # a quotation is created (see RepairOrder.action_create_sale_order).
        return super(
            RepairService, self.filtered("accepted")
        )._create_repair_sale_order_line()
