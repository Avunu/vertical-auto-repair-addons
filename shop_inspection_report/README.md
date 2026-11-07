# Shop Inspection Report

Customer-facing digital vehicle inspection report for a repair-shop visit, built on
`shop_inspection`.

## What it adds

- **PDF report** on the repair order (Print menu) aggregating all non-cancelled
  inspections of the visit into one document, in the usual DVI report's order: _Today's
  Services / Concerns_ → _Good_ (compact list) → _Future Attention_ → _Currently Needs
  Attention_ → _Failed State Inspection_. Each finding shows condition / recommended
  action / notes, measurement tables with out-of-spec values highlighted red, inline
  photo thumbnails, and a full-size photo appendix (4 per page).
- **Email**: a _Send Inspection Report_ button on the repair order opens the composer
  pre-loaded with a template that attaches the PDF and links to the portal page.
- **Portal**: `/my/inspections` (list) and `/my/inspections/<repair_id>` (HTML report
  with photos and a Download PDF button). Access works both for logged-in portal
  customers (record rules restrict to their own repair orders) and via the signed
  `access_token` link in the email.

## Design notes

- `repair.order` gains `portal.mixin`; the portal URL is the inspection page.
- The report body template (`inspection_report_content`) is shared verbatim between the
  PDF and the portal page.
- Section labels come from the severity selection, and category headers from
  `shop.inspection.category` — wording is data/translations, not code.
