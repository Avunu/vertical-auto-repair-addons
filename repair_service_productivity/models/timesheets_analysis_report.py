# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class TimesheetsAnalysisReport(models.Model):
    """Attributes Services-tab time to employees in the stock Timesheets app.

    Three things layer on top of `sale_timesheet`'s existing per-line
    `billable_time`/`non_billable_time` columns (see that module's own
    `timesheets_analysis_report.py` for the baseline this extends):

    1. `billable_time`, for a repair-service-linked line, becomes that
       service's Invoiced quantity (`repair.service.product_uom_qty`)
       *attributed* to this line by its share of the service's logged
       Actual Time -- a service can have more than one technician's
       timesheet against it, and Invoiced is a single total on the
       service, not per line. A line contributing 2 of a service's 3
       logged hours gets 2/3 of that service's Invoiced quantity.
       Gated on the repair order having at least one invoice (`sale.
       order.line.qty_invoiced > 0` on any line of it) -- unconfirmed/
       unbilled work isn't "billable" yet.
    2. `non_billable_time` for repair-linked lines becomes the gap between
       the technician's actual clocked attendance that day and the
       billable time above, spread evenly across that day's repair
       lines. Attendance the base per-line formula (`unit_amount -
       billable_time`) cannot see at all -- a day where a technician
       clocked in but logged no repair time whatsoever has no
       `account.analytic.line` row for this SQL view to attach that gap
       to -- is unioned in as a synthetic row per employee/day instead
       (see `idle_rows` below), so it isn't silently missing from the
       "Non-billable Time" measure.
    3. `estimated_vs_actual_time` is new: the same per-line attribution as
       Invoiced, but for `estimated_time - actual_time` on the service --
       positive when the job came in under estimate, negative when it
       ran over (e.g. "-25:38"; `float_time`-family widgets already
       format negative floats this way, confirmed by reading
       formatFloatTime in web's own formatters.js, so no extra handling
       is needed here). Also gated on the order being invoiced, same as
       Invoiced time.

    A fourth thing (`manual_repair_service` below) handles a case that
    isn't a timesheet line at all: Estimated/Actual/Invoiced can be typed
    directly into the Services tab with no technician ever starting a
    timer against it, leaving `repair.service.analytic_line_ids` empty.
    There is then no real per-employee split to attribute Invoiced time
    by, so the whole amount is credited to the repair order's assigned
    Technician instead of nobody -- confirmed live that this is a real
    scenario, not hypothetical: several test orders had Actual Time set
    this way. Deliberately NOT netted against that employee's attendance
    for the day (unlike the real-timesheet case above): there is no
    record of when the manually-entered work actually happened, so
    guessing a specific day to dock from their Non-billable Time would
    be pure invention. It only adds to Billable Time and Estimated vs
    Actual, both gated on the order being invoiced same as everywhere
    else.

    Non-repair timesheet lines (no `repair_service_id`) are completely
    unaffected -- they keep whatever `sale_timesheet` already computed for
    them.
    """

    _inherit = "timesheets.analysis.report"

    estimated_vs_actual_time = fields.Float(
        "Estimated vs Actual Time",
        readonly=True,
        help="Estimated Time minus Actual Time, attributed per employee "
        "the same way Invoiced time is. Negative when the job ran over "
        "its estimate. Only counted for services on an invoiced repair "
        "order.",
    )

    @property
    def _table_query(self):
        # `super()._table_query` is sale_timesheet's fully-formed
        # "SELECT A.*, margin, non_billable_time FROM (...) A" -- wrapped
        # here as a CTE rather than reconstructed via `_select`/`_from`/
        # `_where`, so every field every other installed module has
        # layered onto this report (via those same extension points)
        # keeps working unmodified; only billable_time/non_billable_time
        # get overridden, and only for repair-linked rows.
        return """
            WITH base AS (
                %(base)s
            ),
            repair_invoiced AS (
                -- Repair orders with at least one invoiced sale order
                -- line -- "invoiced" at the order level, not per service,
                -- per how this was scoped: a partially-invoiced order
                -- already counts, not just fully-invoiced ones.
                SELECT DISTINCT ro.id AS repair_id
                FROM repair_order ro
                JOIN sale_order_line sol ON sol.order_id = ro.sale_order_id
                WHERE sol.qty_invoiced > 0
            ),
            repair_line AS (
                SELECT
                    a.id,
                    a.employee_id,
                    a.date,
                    CASE
                        WHEN ri.repair_id IS NOT NULL AND rs.actual_time > 0
                        THEN a.unit_amount / rs.actual_time * rs.product_uom_qty
                        ELSE 0
                    END AS repair_billable_time,
                    CASE
                        WHEN ri.repair_id IS NOT NULL AND rs.actual_time > 0
                        THEN a.unit_amount / rs.actual_time
                            * (rs.estimated_time - rs.actual_time)
                        ELSE 0
                    END AS repair_estimated_vs_actual
                FROM account_analytic_line a
                JOIN repair_service rs ON rs.id = a.repair_service_id
                LEFT JOIN repair_invoiced ri ON ri.repair_id = rs.repair_id
                WHERE a.repair_service_id IS NOT NULL
            ),
            daily_repair AS (
                -- Per employee/day: total attributed billable time and
                -- how many repair lines exist, to spread that day's
                -- attendance-minus-billable gap evenly across them.
                SELECT
                    employee_id, date,
                    SUM(repair_billable_time) AS daily_billable,
                    COUNT(*) AS line_count
                FROM repair_line
                GROUP BY employee_id, date
            ),
            repair_employees AS (
                -- Scopes attendance to actual shop technicians only --
                -- office staff clocking in/out have nothing to do with
                -- this report and shouldn't show up as "all non-billable".
                SELECT DISTINCT employee_id
                FROM account_analytic_line
                WHERE repair_service_id IS NOT NULL AND employee_id IS NOT NULL
            ),
            daily_attendance AS (
                SELECT
                    ha.employee_id,
                    ha.check_in::date AS date,
                    SUM(ha.worked_hours) AS attendance_hours
                FROM hr_attendance ha
                WHERE ha.employee_id IN (SELECT employee_id FROM repair_employees)
                GROUP BY ha.employee_id, ha.check_in::date
            ),
            daily_leftover AS (
                -- GREATEST(..., 0): billable time exceeding attendance
                -- would mean more was invoiced than the technician was
                -- even clocked in for -- a data problem elsewhere, not a
                -- real "negative non-billable time" to report here.
                SELECT
                    dr.employee_id, dr.date, dr.line_count,
                    GREATEST(
                        COALESCE(da.attendance_hours, 0) - dr.daily_billable, 0
                    ) AS leftover
                FROM daily_repair dr
                LEFT JOIN daily_attendance da
                    ON da.employee_id = dr.employee_id AND da.date = dr.date
            ),
            idle_rows AS (
                -- Employee/day combos with attendance but zero repair
                -- timesheet lines at all: the whole day's attendance is
                -- non-billable, and there is no existing row in `base`
                -- for it to attach to.
                SELECT
                    da.employee_id, da.date, da.attendance_hours AS non_billable_time
                FROM daily_attendance da
                LEFT JOIN daily_repair dr
                    ON dr.employee_id = da.employee_id AND dr.date = da.date
                WHERE dr.employee_id IS NULL
            ),
            manual_repair_service AS (
                -- Accepted services on an invoiced order with a manually
                -- typed Actual Time (readonly=False lets the office
                -- override it) but no real timesheet behind it at all --
                -- credited in full to the repair order's Technician.
                -- rs.write_date is used as the row's "date" only for the
                -- pivot's date grouping to have something to show; it is
                -- not claimed to be when the work happened.
                SELECT
                    rs.id AS service_id,
                    he.id AS employee_id,
                    rs.write_date::date AS date,
                    rs.product_uom_qty AS billable_time,
                    (rs.estimated_time - rs.actual_time) AS estimated_vs_actual
                FROM repair_service rs
                JOIN repair_order ro ON ro.id = rs.repair_id
                JOIN repair_invoiced ri ON ri.repair_id = ro.id
                JOIN hr_employee he ON he.user_id = ro.technician_id
                WHERE rs.accepted = true
                    AND rs.actual_time > 0
                    AND NOT EXISTS (
                        SELECT 1 FROM account_analytic_line a2
                        WHERE a2.repair_service_id = rs.id
                    )
            )
            SELECT
                base.id,
                base.name,
                base.user_id,
                base.project_id,
                base.task_id,
                base.parent_task_id,
                base.employee_id,
                base.manager_id,
                base.company_id,
                base.department_id,
                base.currency_id,
                base.date,
                base.amount,
                base.unit_amount,
                base.partner_id,
                base.order_id,
                base.so_line,
                base.timesheet_invoice_type,
                base.timesheet_invoice_id,
                base.timesheet_revenues,
                base.sheet_id,
                base.margin,
                COALESCE(rl.repair_billable_time, base.billable_time) AS billable_time,
                CASE
                    WHEN rl.id IS NOT NULL
                    THEN COALESCE(dl.leftover, 0) / NULLIF(dl.line_count, 0)
                    ELSE base.non_billable_time
                END AS non_billable_time,
                COALESCE(rl.repair_estimated_vs_actual, 0) AS estimated_vs_actual_time
            FROM base
            LEFT JOIN repair_line rl ON rl.id = base.id
            LEFT JOIN daily_leftover dl
                ON dl.employee_id = rl.employee_id AND dl.date = rl.date

            UNION ALL

            SELECT
                -(ROW_NUMBER() OVER (ORDER BY ir.employee_id, ir.date) + 1000000) AS id,
                NULL AS name,
                he.user_id AS user_id,
                -- The stock "Timesheets by Employee" action
                -- (hr_timesheet.act_hr_timesheet_report) hardcodes the
                -- domain [('project_id', '!=', False)] - without a
                -- project_id here, every synthetic row in this whole
                -- query would be invisible in that report no matter what
                -- it computes, confirmed live (rows existed and were
                -- readable by ORM search, but the actual Timesheets app
                -- screen showed nothing for them). The repair timesheet
                -- project is where this time nominally belongs anyway.
                (SELECT repair_timesheet_project_id FROM res_company
                 WHERE id = he.company_id) AS project_id,
                NULL AS task_id,
                NULL AS parent_task_id,
                ir.employee_id AS employee_id,
                NULL AS manager_id,
                he.company_id AS company_id,
                he.department_id AS department_id,
                NULL AS currency_id,
                ir.date AS date,
                0 AS amount,
                0 AS unit_amount,
                NULL AS partner_id,
                NULL AS order_id,
                NULL AS so_line,
                'non_billable' AS timesheet_invoice_type,
                NULL AS timesheet_invoice_id,
                0 AS timesheet_revenues,
                NULL AS sheet_id,
                0 AS margin,
                0 AS billable_time,
                ir.non_billable_time AS non_billable_time,
                0 AS estimated_vs_actual_time
            FROM idle_rows ir
            LEFT JOIN hr_employee he ON he.id = ir.employee_id

            UNION ALL

            SELECT
                -(ROW_NUMBER() OVER (ORDER BY mrs.service_id) + 2000000) AS id,
                NULL AS name,
                he2.user_id AS user_id,
                (SELECT repair_timesheet_project_id FROM res_company
                 WHERE id = he2.company_id) AS project_id,
                NULL AS task_id,
                NULL AS parent_task_id,
                mrs.employee_id AS employee_id,
                NULL AS manager_id,
                he2.company_id AS company_id,
                he2.department_id AS department_id,
                NULL AS currency_id,
                mrs.date AS date,
                0 AS amount,
                0 AS unit_amount,
                NULL AS partner_id,
                NULL AS order_id,
                NULL AS so_line,
                'billable_manual' AS timesheet_invoice_type,
                NULL AS timesheet_invoice_id,
                0 AS timesheet_revenues,
                NULL AS sheet_id,
                0 AS margin,
                mrs.billable_time AS billable_time,
                0 AS non_billable_time,
                mrs.estimated_vs_actual AS estimated_vs_actual_time
            FROM manual_repair_service mrs
            LEFT JOIN hr_employee he2 ON he2.id = mrs.employee_id
        """ % {"base": super()._table_query}
