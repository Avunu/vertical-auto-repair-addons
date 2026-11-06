# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import models

# Report section order: today's concerns first, then the
# compact good list, then the attention bands by increasing urgency.
REPORT_SEVERITY_ORDER = ("today", "good", "future", "attention", "fail_state")


class RepairOrder(models.Model):
    _name = "repair.order"
    _inherit = ["repair.order", "portal.mixin"]

    def _compute_access_url(self):
        res = super()._compute_access_url()
        for repair in self:
            repair.access_url = f"/my/inspections/{repair.id}"
        return res

    def _shop_report_inspections(self):
        """Inspections shown on the customer report."""
        self.ensure_one()
        return self.inspection_ids.filtered(
            lambda inspection: inspection.state != "cancel"
        )

    def _shop_report_sections(self):
        """Severity-ordered sections, each grouped by checklist category.

        Returns a list of dicts:
        ``{"severity", "label", "count", "lines", "categories":
        [{"category", "lines"}]}`` — only severities that have lines.
        """
        self.ensure_one()
        lines = self._shop_report_inspections().inspection_line_ids
        severity_field = lines._fields["severity"]
        labels = dict(severity_field._description_selection(self.env))
        sections = []
        for severity in REPORT_SEVERITY_ORDER:
            severity_lines = lines.filtered(
                lambda line, severity=severity: line.severity == severity
            ).sorted(lambda line: (line.category_id.sequence, line.sequence))
            if not severity_lines:
                continue
            categories = []
            for line in severity_lines:
                if categories and categories[-1]["category"] == line.category_id:
                    categories[-1]["lines"] |= line
                else:
                    categories.append({"category": line.category_id, "lines": line})
            sections.append(
                {
                    "severity": severity,
                    "label": labels.get(severity, severity),
                    "count": len(severity_lines),
                    "lines": severity_lines,
                    "categories": categories,
                }
            )
        return sections

    def _shop_report_images(self):
        """All finding photos of the visit, for the photo appendix."""
        self.ensure_one()
        return self._shop_report_inspections().inspection_line_ids.mapped(
            "inspection_line_image_ids"
        )

    def action_send_inspection_report(self):
        self.ensure_one()
        self._portal_ensure_token()
        template = self.env.ref(
            "shop_inspection_report.mail_template_inspection_report",
            raise_if_not_found=False,
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "mail.compose.message",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_model": "repair.order",
                "default_res_ids": self.ids,
                "default_template_id": template.id if template else False,
                "default_composition_mode": "comment",
                "force_email": True,
            },
        }
