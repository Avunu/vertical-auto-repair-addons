# Fleet Vehicle Simplify

Strips the Fleet app down to what an auto repair shop needs. A shop's vehicles belong to
its customers, so the European tax fields, employee driver assignment and the
lease-vehicle workflow don't apply to them.

- **Vehicle form**: removes the tax page and the status bar, and hides the driver groups
  and the vehicle details that don't apply. The fields stay on the model, because other
  `invisible` conditions and core code use them.
- **List, pivot and search views**: drop the status, and the list also drops the
  acquisition date and tags. The contract columns are hidden from the list but stay in
  it, because its row decorations depend on them.
- **Search bar**: the default "Vehicle" search covers the vehicle's text, selection and
  many2one fields (VIN, owner, driver and so on), with a separate search field for each
  of them.
- **Menus**: hides Reporting, lease contracts, odometer logs, the OCA inspection menus
  and the vehicle configuration tied to the removed workflow. Inspections have their own
  flow under Repairs.

The module only changes views and menus: it adds no models or fields.
