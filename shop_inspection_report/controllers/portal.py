# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager


class ShopInspectionPortal(CustomerPortal):
    def _shop_inspection_domain(self):
        return [("inspection_ids", "!=", False)]

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "inspection_count" in counters:
            repair_model = request.env["repair.order"]
            values["inspection_count"] = (
                repair_model.search_count(self._shop_inspection_domain())
                if repair_model.has_access("read")
                else 0
            )
        return values

    @http.route(
        ["/my/inspections", "/my/inspections/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_inspections(self, page=1, **kw):
        repair_model = request.env["repair.order"]
        domain = self._shop_inspection_domain()
        inspections_count = repair_model.search_count(domain)
        pager = portal_pager(
            url="/my/inspections",
            total=inspections_count,
            page=page,
            step=self._items_per_page,
        )
        repairs = repair_model.search(
            domain,
            order="create_date desc",
            limit=self._items_per_page,
            offset=pager["offset"],
        )
        return request.render(
            "shop_inspection_report.portal_my_inspections",
            {
                "repairs": repairs,
                "page_name": "inspection",
                "pager": pager,
                "default_url": "/my/inspections",
            },
        )

    @http.route(
        ["/my/inspections/<int:repair_id>"],
        type="http",
        auth="public",
        website=True,
    )
    def portal_inspection_page(
        self, repair_id, access_token=None, report_type=None, download=False, **kw
    ):
        try:
            repair_sudo = self._document_check_access(
                "repair.order", repair_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return request.redirect("/my")

        if report_type in ("html", "pdf", "text"):
            return self._show_report(
                model=repair_sudo,
                report_type=report_type,
                report_ref="shop_inspection_report.action_report_shop_inspection",
                download=download,
            )

        return request.render(
            "shop_inspection_report.portal_inspection_page",
            {
                "repair": repair_sudo,
                "page_name": "inspection",
                "report_type": "html",
            },
        )
