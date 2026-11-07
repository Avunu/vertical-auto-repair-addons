# Repair Service Workflow

Adds a customer-acceptance workflow, estimated/actual time tracking, and
Confirm/Finalize review wizards to the repair order Services tab.

- `repair.service` gains `accepted`, `estimated_time`, and `actual_time` (summed from
  linked `account.analytic.line` time logs).
- `product_uom_qty` on the Services tab is relabeled "Invoiced".
- Clicking "Confirm Repair" opens a wizard to review/adjust service acceptance, see the
  assigned technician, and add parts from the catalog or a purchase order before the
  order is actually confirmed.
- Clicking "End Repair" opens a wizard confirming the final billable parts and accepted
  services before the order is actually finalized.
- Unaccepted services are archived (not billed) once a quotation is created from the
  repair order.

Depends on `repair_service_so_sync`, `repair_timesheet_time_control`,
`repair_purchase_order_parts`, and `shop_scheduling`.
