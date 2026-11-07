# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from markupsafe import Markup, escape

from odoo import _, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        res = super().action_confirm()
        self._shop_explode_job_lines()
        return res

    def _shop_explode_job_lines(self):
        """Explode approved flat-rate jobs into their repair orders and log
        an approved/declined summary in the repair order chatter."""
        for order in self:
            job_lines = order.order_line.filtered(
                lambda line: line.shop_job_id and not line.shop_job_exploded
            )
            touched_repairs = self.env["repair.order"]
            for line in job_lines:
                repair = line.shop_repair_id or order.repair_order_ids[:1]
                if not repair or repair.state in ("done", "cancel"):
                    continue
                line._shop_explode_into_repair(repair)
                touched_repairs |= repair
            declined = order.sale_order_option_ids.filtered(
                lambda option: option.shop_job_id and not option.line_id
            )
            for repair in touched_repairs:
                repair.message_post(
                    body=self._shop_job_summary_body(order, repair, declined)
                )

    def _shop_job_summary_body(self, order, repair, declined):
        approved = order.order_line.filtered(
            lambda line: line.shop_job_id
            and line.shop_job_exploded
            and (line.shop_repair_id == repair or not line.shop_repair_id)
        )
        body = Markup("<p>%s</p>") % _("Estimate %(order)s approved.", order=order.name)
        if approved:
            items = Markup("").join(
                Markup("<li>%s</li>") % escape(line.shop_job_id.name)
                for line in approved
            )
            body += Markup("<p>%s</p><ul>%s</ul>") % (
                _("Approved jobs (parts and labor added):"),
                items,
            )
        if declined:
            items = Markup("").join(
                Markup("<li>%s</li>") % escape(option.shop_job_id.name)
                for option in declined
            )
            body += Markup("<p>%s</p><ul>%s</ul>") % (
                _("Declined by the customer:"),
                items,
            )
        return body
