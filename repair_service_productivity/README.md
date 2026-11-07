# Repair Service Productivity Reporting

Attributes repair order Services-tab time to employees in the Timesheets app's Billable
Time report, and compares it with their attendance. Timesheet lines not linked to a
repair service keep what `sale_timesheet` computes for them.

- **Billable Time**: for a line linked to a repair service, the service's Invoiced
  quantity, split by the line's share of the service's Actual Time. It only counts once
  the repair order has at least one invoiced line.
- **Non-billable Time**: for those lines, the gap between the technician's attendance
  that day and their billable time, spread evenly across that day's repair lines. A day
  with attendance and no repair time gets its own row in the report. Only employees who
  have logged repair time are included, so office staff don't appear as non-billable.
- **Estimated vs Actual Time** (new measure): Estimated Time minus Actual Time, split
  the same way as Invoiced and also only for invoiced orders. It's negative when a job
  ran over its estimate.
- **Services with a typed Actual Time and no timesheet**: the whole Invoiced quantity
  goes to the repair order's technician. It adds to Billable Time and Estimated vs
  Actual, but isn't set against their attendance, since nothing records which day the
  work happened.

The pivot opens with these measures selected, and the graph views offer the new one. The
module also removes a duplicate pair of fields that core's
`sale_timesheet.timesheets_analysis_report_graph_inherit` adds to the pivot.
