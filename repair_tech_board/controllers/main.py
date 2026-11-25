# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""The board's page, over the build in ``static/dist/`` (repair_tech_api's
``PwaApp``). The data comes from ``repair.order.board_jobs``."""

from odoo import http

from odoo.addons.repair_tech_api.controllers.pwa import PwaApp

APP = PwaApp(
    module="repair_tech_board",
    slug="board",
    name="Repair Job Board",
    short_name="Job Board",
    description="The shop's open jobs, one column per technician.",
    theme_color="#0c1118",
    background_color="#0c1118",
    icon="board",
    # A dark bar over the dark board, on an iPad's installed app.
    status_bar_style="black",
    orientation="landscape",
)


class RepairTechBoard(http.Controller):
    @http.route("/repair-tech/board/", type="http", auth="user")
    def index(self):
        return APP.render("repair_tech_board.index")

    @http.route("/repair-tech/board/manifest.webmanifest", type="http", auth="public")
    def manifest(self):
        return APP.manifest_response()

    @http.route("/repair-tech/board/sw.js", type="http", auth="public")
    def service_worker(self):
        return APP.service_worker_response()
