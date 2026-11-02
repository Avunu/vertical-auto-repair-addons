# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import _, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    shop_job_id = fields.Many2one(
        "shop.service.job",
        string="Service Job",
        copy=False,
    )
    shop_repair_id = fields.Many2one(
        "repair.order",
        string="Job Repair Order",
        copy=False,
        help="Repair order the job explodes into when the order is confirmed.",
    )
    shop_finding_line_id = fields.Many2one(
        "fleet.vehicle.inspection.line",
        string="Inspection Finding",
        copy=False,
    )
    shop_job_exploded = fields.Boolean(copy=False)

    def _shop_explode_into_repair(self, repair):
        """Push the approved job's parts and labor onto the repair order.

        Parts become ``add`` stock moves and labor becomes ``repair.service``
        lines, both flagged with ``shop_job_sale_line_id`` so they are *not*
        synced back to the sale order — the customer pays the flat-rate job
        line, while parts and time are tracked at cost on the repair order.
        """
        self.ensure_one()
        job = self.shop_job_id
        qty = self.product_uom_qty or 1.0
        move_vals = []
        for part in job.part_line_ids:
            move_vals.append(
                {
                    "repair_id": repair.id,
                    "repair_line_type": "add",
                    "product_id": part.product_id.id,
                    "product_uom": part.product_id.uom_id.id,
                    "product_uom_qty": part.quantity * qty,
                    "company_id": repair.company_id.id,
                    "shop_job_sale_line_id": self.id,
                }
            )
        if move_vals:
            self.env["stock.move"].create(move_vals)
        if job.labor_product_id and job.labor_hours:
            self.env["repair.service"].create(
                {
                    "repair_id": repair.id,
                    "product_id": job.labor_product_id.id,
                    "product_uom": job.labor_product_id.uom_id.id,
                    "product_uom_qty": job.labor_hours * qty,
                    "display_name": _(
                        "%(job)s (approved job)", job=job.name
                    ),
                    "shop_job_sale_line_id": self.id,
                }
            )
        self.shop_job_exploded = True
        if self.shop_finding_line_id and not self.shop_finding_line_id.sale_line_id:
            self.shop_finding_line_id.sale_line_id = self
