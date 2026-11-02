# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class ShopServiceJob(models.Model):
    _name = "shop.service.job"
    _description = "Canned Service Job"
    _order = "name"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company
    )
    customer_description = fields.Text(
        help="Customer-facing wording used on the quote line."
    )
    product_id = fields.Many2one(
        "product.product",
        string="Job Product",
        domain=[("type", "=", "service")],
        check_company=True,
        copy=False,
        help="Flat-rate service product placed on the quote for this job. "
        "Auto-created on first use if empty.",
    )
    pricing = fields.Selection(
        [("fixed", "Fixed menu price"), ("computed", "Labor + parts")],
        default="fixed",
        required=True,
    )
    price_fixed = fields.Float(string="Menu Price")
    labor_product_id = fields.Many2one(
        "product.product",
        string="Labor Product",
        domain=[("type", "=", "service")],
        check_company=True,
        help="Labor line added to the repair order when the job is approved. "
        "Also prices the job when using computed pricing.",
    )
    labor_hours = fields.Float(string="Labor Hours")
    part_line_ids = fields.One2many(
        "shop.service.job.part",
        "job_id",
        string="Parts",
    )
    price_total = fields.Float(
        string="Price",
        compute="_compute_price_total",
        help="What the customer is quoted for this job.",
    )
    action_ids = fields.One2many(
        "shop.inspection.action",
        "job_id",
        string="Triggering Recommended Actions",
        help="Inspection recommended actions that price themselves with "
        "this job in the estimate builder.",
    )

    @api.depends(
        "pricing",
        "price_fixed",
        "labor_product_id.lst_price",
        "labor_hours",
        "part_line_ids.product_id.lst_price",
        "part_line_ids.quantity",
    )
    def _compute_price_total(self):
        for job in self:
            if job.pricing == "fixed":
                job.price_total = job.price_fixed
            else:
                job.price_total = (
                    job.labor_product_id.lst_price * job.labor_hours
                    + sum(
                        part.product_id.lst_price * part.quantity
                        for part in job.part_line_ids
                    )
                )

    def _ensure_product(self):
        """Return the job's service product, creating it on first use."""
        self.ensure_one()
        if not self.product_id:
            # sudo: service writers build estimates without product-creation
            # rights; the product is fully determined by the job.
            self.sudo().product_id = self.env["product.product"].sudo().create(
                {
                    "name": self.name,
                    "type": "service",
                    "invoice_policy": "order",
                    "sale_ok": True,
                    "purchase_ok": False,
                    "list_price": self.price_total,
                    "description_sale": self.customer_description or False,
                    "company_id": self.company_id.id,
                }
            )
        return self.product_id


class ShopServiceJobPart(models.Model):
    _name = "shop.service.job.part"
    _description = "Canned Service Job Part"
    _check_company_auto = True

    job_id = fields.Many2one(
        "shop.service.job",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(related="job_id.company_id", store=True)
    product_id = fields.Many2one(
        "product.product",
        string="Part",
        domain=[("type", "=", "consu")],
        check_company=True,
        required=True,
    )
    quantity = fields.Float(
        digits="Product Unit of Measure", required=True, default=1.0
    )
