# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""The technician app's page, over the build in ``static/dist/``. Its data
comes from the ``repair.tech.app`` facades (models/)."""

from odoo import http

from odoo.addons.repair_tech_api.controllers.pwa import PwaApp

APP = PwaApp(
    module="repair_tech_app",
    slug="app",
    name="Technician",
    short_name="Technician",
    description="Your jobs, timers, parts, inspections and timesheets.",
    theme_color="#1f1f1f",
    background_color="#f6f6f4",
    icon="tech",
    shortcuts=(
        {"name": "My Jobs", "url": "jobs"},
        {"name": "Scan", "url": "jobs?scan=1"},
        {"name": "Timesheets", "url": "timesheets"},
    ),
)


class RepairTechApp(http.Controller):
    # Every path under the scope is the app: it routes on the client, so a
    # reload or a shortcut deep into it lands on the same page.
    @http.route(
        ["/repair-tech/app/", "/repair-tech/app/<path:subpath>"],
        type="http",
        auth="user",
    )
    def index(self, subpath=None):
        return APP.render("repair_tech_app.index")

    @http.route("/repair-tech/app/manifest.webmanifest", type="http", auth="public")
    def manifest(self):
        return APP.manifest_response()

    @http.route("/repair-tech/app/sw.js", type="http", auth="public")
    def service_worker(self):
        return APP.service_worker_response()
