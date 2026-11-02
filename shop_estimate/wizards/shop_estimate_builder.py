# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

# Findings offered for quoting (anything the customer should act on)
QUOTABLE_SEVERITIES = ("today", "future", "attention", "fail_state")
# Findings quoted as firm order lines instead of declinable options
MUST_DO_SEVERITIES = ("today", "fail_state")


class ShopEstimateBuilder(models.TransientModel):
    _name = "shop.estimate.builder"
    _description = "Estimate Builder"

    repair_id = fields.Many2one("repair.order", required=True)
    line_ids = fields.One2many(
        "shop.estimate.builder.line", "wizard_id", string="Findings"
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get("active_model") != "repair.order":
            return res
        repair = self.env["repair.order"].browse(
            self.env.context.get("active_id")
        )
        if not repair:
            return res
        if "repair_id" in fields_list:
            res["repair_id"] = repair.id
        if "line_ids" not in fields_list:
            return res
        findings = repair._shop_get_inspection_lines().filtered(
            lambda line: line.severity in QUOTABLE_SEVERITIES
            and not line.shop_quoted
        )
        commands = []
        for finding in findings:
            job = finding.recommended_action_ids.filtered("job_id")[:1].job_id
            commands.append(
                Command.create(
                    {
                        "finding_line_id": finding.id,
                        "job_id": job.id,
                        "include": bool(job),
                        "must_do": finding.severity in MUST_DO_SEVERITIES,
                        "quantity": 1.0,
                        "price_unit": job.price_total if job else 0.0,
                    }
                )
            )
        res["line_ids"] = commands
        return res

    def action_generate(self):
        self.ensure_one()
        repair = self.repair_id
        included = self.line_ids.filtered("include")
        if not included:
            raise UserError(
                _("Select at least one finding to put on the estimate.")
            )
        missing_job = included.filtered(lambda line: not line.job_id)
        if missing_job:
            raise UserError(
                _(
                    "Assign a service job to the selected findings first: "
                    "%(items)s",
                    items=", ".join(
                        missing_job.mapped("finding_line_id.inspection_item_id.name")
                    ),
                )
            )
        if not repair.sale_order_id:
            repair.action_create_sale_order()
        order = repair.sale_order_id
        if order.state not in ("draft", "sent"):
            raise UserError(
                _(
                    "Quotation %(order)s is already confirmed. Supplemental "
                    "findings need a follow-up quote.",
                    order=order.name,
                )
            )
        order.require_signature = True
        for wizard_line in included:
            wizard_line._create_estimate_entry(order)
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "res_id": order.id,
            "view_mode": "form",
        }


class ShopEstimateBuilderLine(models.TransientModel):
    _name = "shop.estimate.builder.line"
    _description = "Estimate Builder Finding"

    wizard_id = fields.Many2one(
        "shop.estimate.builder", required=True, ondelete="cascade"
    )
    finding_line_id = fields.Many2one(
        "fleet.vehicle.inspection.line", required=True
    )
    item_name = fields.Char(
        related="finding_line_id.inspection_item_id.name", string="Item"
    )
    severity = fields.Selection(related="finding_line_id.severity")
    condition_ids = fields.Many2many(
        related="finding_line_id.condition_ids", string="Conditions"
    )
    notes = fields.Char(
        related="finding_line_id.result_description", string="Notes"
    )
    include = fields.Boolean(default=True)
    must_do = fields.Boolean(
        help="Quoted as a firm order line. Unchecked findings become "
        "optional products the customer can add from the portal."
    )
    job_id = fields.Many2one("shop.service.job", string="Service Job")
    quantity = fields.Float(default=1.0, digits="Product Unit of Measure")
    price_unit = fields.Float(string="Price")

    @api.onchange("job_id")
    def _onchange_job_id(self):
        for line in self:
            if line.job_id:
                line.price_unit = line.job_id.price_total
                line.include = True

    def _estimate_description(self):
        self.ensure_one()
        finding = self.finding_line_id
        job = self.job_id
        parts = [job.customer_description or job.name]
        parts.append(
            _("Finding: %(item)s", item=finding.inspection_item_id.name)
        )
        if finding.condition_ids:
            parts.append(
                _(
                    "Condition: %(conditions)s",
                    conditions=", ".join(finding.condition_ids.mapped("name")),
                )
            )
        if finding.result_description:
            parts.append(finding.result_description)
        return "\n".join(parts)

    def _create_estimate_entry(self, order):
        self.ensure_one()
        product = self.job_id._ensure_product()
        common_vals = {
            "order_id": order.id,
            "product_id": product.id,
            "name": self._estimate_description(),
            "price_unit": self.price_unit,
            "shop_job_id": self.job_id.id,
            "shop_repair_id": self.wizard_id.repair_id.id,
            "shop_finding_line_id": self.finding_line_id.id,
        }
        if self.must_do:
            line = self.env["sale.order.line"].create(
                dict(
                    common_vals,
                    product_uom_qty=self.quantity,
                )
            )
            self.finding_line_id.sale_line_id = line
        else:
            option = self.env["sale.order.option"].create(
                dict(
                    common_vals,
                    quantity=self.quantity,
                    uom_id=product.uom_id.id,
                )
            )
            self.finding_line_id.sale_option_id = option
