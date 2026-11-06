# Shop Estimate Builder

Turns digital-inspection findings into a customer quote where the customer dynamically
approves or declines individual jobs from the portal, and approved jobs populate the
repair order.

## Flow

1. **Service jobs** (`shop.service.job`, Repairs ▸ Configuration ▸ Service Jobs): canned
   jobs with customer description, labor product + book hours, parts, and a price (fixed
   menu price or computed labor + parts). Each job can be linked from inspection
   _recommended actions_ so findings price themselves.
2. **Build Estimate** button on the repair order opens a wizard listing all unquoted
   findings with severity Today / Future / Attention / Failed State. The office manager
   picks which to quote, adjusts job/qty/price, and flags _must-do_ items (defaulted for
   Today + Failed State findings).
3. Generating the estimate creates/updates the visit's sale order (created through the
   core RO → quotation path, so existing parts/labor such as the diagnostic fee are on
   it too):
   - must-do findings → **firm order lines** (flat-rate job product);
   - everything else → **optional products** (`sale.order.option`), declined by default
     — the customer adds the ones they want from the portal quote page (core
     `add_option` route), then signs (`require_signature` is enabled) and pays per your
     sale portal settings.
4. **On order confirmation**, each approved job explodes into the repair order: parts as
   `add` stock moves, labor as `repair.service` lines — both flagged
   `shop_job_sale_line_id` so they are **not** synced back to the sale order (the
   customer pays the flat-rate line; parts and hours are tracked at cost). A chatter
   summary of approved and declined jobs is posted on the repair order (liability
   trail).

## Design notes

- Flat-rate billing: the invoice comes from the job lines on the sale order; parts/labor
  cost tracking stays on the repair order. This mirrors the usual flat-rate shop
  practice (invoice = approved estimate, "ordered" policy).
- The visit repair order is the master; job products are plain service products with
  `create_repair` unset, so confirming the quote never spawns duplicate repair orders.
- Re-running the builder only offers findings not yet quoted. Once the quote is
  confirmed, supplemental findings need a follow-up quote (the wizard tells you so).
- The option → line handoff propagates the job metadata via
  `sale.order.option._get_values_to_add_to_order`, so portal opt-ins explode exactly
  like back-office ones.
