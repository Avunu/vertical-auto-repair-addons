# Repair Purchase Order Match

Links an EDI/email-imported purchase order to its repair order. When the PO number is a repair order number, it links them automatically; otherwise it asks [TypeSafe AI](https://typesafe.ai) which open repair order the purchase order most likely belongs to, and posts a "Confirm Match" button to both records' chatter - one click links them the same way the "Add to Repair" button does by hand.

## Why

`edi_purchase_order_import` auto-confirms a purchase order the moment an inbound vendor email/EDI document creates it, but a purchase order confirmed that way still has to be linked to a repair order by hand via `repair_purchase_order_parts`'s "Add to Repair" picker. This module suggests which one, using the same kind of context a service writer would recognize a job by - vehicle info and the customer's own description of the problem - rather than requiring the purchase order's part numbers to exactly match what the repair order's parts list already has entered.

## What it does

- **PO number = repair order number.** The shop sends repair order numbers (e.g. `WH/RO/00004`) to vendors as the PO number. When an imported purchase order's **Source Document** holds the number of an existing repair order of the same company, the purchase order is linked to it automatically, with no confirmation: its parts are added to the repair order, and the same users `edi_purchase_order_import` notifies are told in the purchase order's chatter. Only the number counts, not the letters or separators around it (`RO00004`, `RO-4` and `WH/RO/00004` all name `WH/RO/00004`): the last run of digits in each is compared. If two repair orders share a number the match is ambiguous and nothing is linked automatically. The vendor's import template needs a line that puts the vendor's "PO number" into Source Document (the vendor's own order number belongs in Vendor Reference and is not used for matching). If the number names a repair order that is already done or cancelled, nothing is added and the chatter says so.
- **Choosing a different repair order.** Every link message in the chatter (automatic or confirmed) ends with *Not the right repair order? Choose a different one.* That opens the list of open repair orders; clicking one links the purchase order to it and returns to the purchase order. A purchase order belongs to one repair order, so the parts it had added to the previous open repair order are taken back off it (parts already consumed on a finished move stay).
- After an EDI-imported purchase order is confirmed, a background job (`queue_job`) describes the purchase order (vendor, order date, lines) and every open, vehicle-linked repair order (repair date, vehicle manufacturer/model/year, customer concern) to TypeSafe's [Choice primitive](https://docs.typesafe.ai/primitives/choice), asking which repair order the purchase order belongs to.
- TypeSafe's best guess, with its confidence, is posted as a chatter message with a **Confirm Match** button on *both* the purchase order and the repair order, and needaction-notifies the same group `edi_purchase_order_import` already notifies (Settings > Purchase).
- Clicking Confirm Match (a signed, one-time-pair link - it only works for that specific purchase order/repair order combination) adds every product line on the purchase order to the repair order's parts list, exactly like the manual "Add to Repair" button.
- **TypeSafe's guess is never linked automatically.** It always waits for a human to click Confirm - there is no confidence threshold above which this module acts on its own. Only an exact repair order number in the PO number does.
- The matching and linking steps are each also exposed as `muk_mcp` tools (`find_repair_order_matches`, `link_purchase_order_to_repair`), so the same capability is usable directly from the MuK AI chat, not just from the automated import flow.

## Configuration

Settings > Purchase > **TypeSafe API Key**. Matching silently does nothing (no suggestion posted, nothing logged as an error) until this is set - so this feature is opt-in per install.

## What it does not do

- It doesn't consider repair orders with no vehicle on file, since there'd be no useful criteria to describe them by - vehicleless repairs still need to be linked by hand via "Add to Repair".
- It doesn't retry or fall back to a deterministic match when TypeSafe is unreachable or returns nothing - it simply skips posting a suggestion for that purchase order, same as if no API key were configured.
