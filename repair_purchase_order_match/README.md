# Repair Purchase Order Match

Links an EDI/email-imported purchase order to its repair order. When the PO number is a
repair order number, it links them automatically; otherwise it asks
[TypeSafe AI](https://typesafe.ai) which open repair order the purchase order most
likely belongs to, and posts a "Confirm Match" button to both records' chatter - one
click links them the same way the **Match Repair** button does by hand.

## Why

`edi_purchase_order_import` auto-confirms a purchase order the moment an inbound vendor
email/EDI document creates it, but a purchase order confirmed that way still has to be
linked to a repair order by hand (`repair_purchase_order_parts`' "Add to Repair" picker,
which this module replaces with its Match buttons). This module suggests which one,
using the same kind of context a service writer would recognize a job by - vehicle info
and the customer's own description of the problem - rather than requiring the purchase
order's part numbers to exactly match what the repair order's parts list already has
entered.

## What it does

- **PO number = repair order number.** The shop sends repair order numbers (e.g.
  `WH/RO/00004`) to vendors as the PO number. When an imported purchase order's **Source
  Document** holds the number of an existing repair order of the same company, the
  purchase order is linked to it automatically, with no confirmation: its parts are
  added to the repair order, and the same users `edi_purchase_order_import` notifies are
  told in the purchase order's inbox (see _Notices_). Only the number counts, not the letters or
  separators around it (`RO00004`, `RO-4` and `WH/RO/00004` all name `WH/RO/00004`): the
  last run of digits in each is compared. If two repair orders share a number the match
  is ambiguous and nothing is linked automatically. The vendor's import template needs a
  line that puts the vendor's "PO number" into Source Document (the vendor's own order
  number belongs in Vendor Reference and is not used for matching). If the number names
  a repair order that is already done or cancelled, nothing is added and the chatter
  says so.
- **Choosing a different repair order.** Every link message in the chatter (automatic or
  confirmed) ends with _Not the right repair order? Choose a different one._ That opens
  the list of open repair orders; clicking one links the purchase order to it and
  returns to the purchase order. A purchase order belongs to one repair order, so the
  parts it had added to the previous open repair order are taken back off it (parts
  already consumed on a finished move stay).
- **Match Order (on the repair order).** The repair order form header has a **Match
  Order** button (open repair orders; shown to who has the rights, see _Access_) in
  front of the status bar. It opens a dialog of the confirmed purchase orders of the
  same company that are not linked to any repair order yet, newest first. Each card
  shows the purchase order, its vendor, vendor reference, date and total, and its parts
  list (quantity and unit, part number, description - the lines that are added to the
  repair order), with a **Match** button: it adds the parts to the repair order, posts
  to both chatters, and closes the dialog while reloading the repair order underneath.
  The dialog can be searched by purchase order number, vendor, vendor reference or part,
  and filtered to the ones **Imported from email**.
- **Unmatched** means: a purchase order in the _purchase_ or _done_ state none of whose
  lines is a part on a repair order that is not cancelled. A purchase order with only
  some lines linked counts as matched. One linked only to a cancelled repair order is
  unmatched again. A line also counts as linked through its receipt moves (what a
  confirmed Buy-route purchase order has instead). Orders without a part (only sections
  and notes) are left out. The test is one SQL sub-select (`repair_match_unmatched`, a
  searchable, non-stored field), read with sudo so it does not depend on the user's
  stock access.
- **Match Repair (on the purchase order).** The purchase order form has a **Match
  Repair** button (confirmed orders; shown to who has the rights, see _Access_). It
  opens a dialog of the open repair orders of the same company; clicking one links the
  purchase order the same way, posts to both chatters and reloads the purchase order. A
  validated receipt has the same **Match Repair** button, for the purchase order it
  belongs to.
- **One button per place.** `repair_purchase_order_parts` adds its own "Add to Repair"
  (purchase order and receipt) and "Purchase Orders" (Parts tab of the repair order)
  buttons. This module replaces them with the match flow, so that there is exactly one
  button in each place, and every one of them links the same way: a purchase order
  belongs to one repair order, so the parts leave the one it was matched to before. The
  old entry points are overridden, so nothing else reaches the old behaviour:
  `action_add_to_repair` and `action_add_parts_from_purchase_order` open the match
  dialogs; the pickers' row clicks and multi-select button (`action_select_for_repair`,
  `action_add_selected_to_repair`, `action_select_po_for_repair`) and creating a repair
  order with `po_id` in the context link the way the match flow does (same rights,
  validation, notes and clearing); a user who can't match is refused (`AccessError`)
  whichever way they call.
- **Confirm Repair wizard.** `repair_service_workflow`'s confirm wizard has its own
  "Add from Purchase Order" button, which calls `action_add_parts_from_purchase_order`: it
  therefore opens the **Match Order** dialog too (the wizard is replaced by the dialog,
  and matching reloads the repair order, so confirm the repair again afterwards). This
  module does not depend on `repair_service_workflow`, so it does not relabel that button.
- After an EDI-imported purchase order is confirmed, a background job (`queue_job`)
  describes the purchase order (vendor, order date, lines) and every open,
  vehicle-linked repair order (repair date, vehicle manufacturer/model/year, customer
  concern) to TypeSafe's [Choice primitive](https://docs.typesafe.ai/primitives/choice),
  asking which repair order the purchase order belongs to.
- TypeSafe's best guess, with its confidence, is posted with a **Confirm Match** button
  on _both_ the purchase order and the repair order, as an outstanding notice (see
  _Notices_).
- Clicking Confirm Match (a signed, one-time-pair link - it only works for that specific
  purchase order/repair order combination) adds every product line on the purchase order
  to the repair order's parts list, exactly like the Match buttons (it needs the same
  access rights: see _Access_).
- **TypeSafe's guess is never linked automatically.** It always waits for a human to
  click Confirm - there is no confidence threshold above which this module acts on its
  own. Only an exact repair order number in the PO number does.
- The matching and linking steps are each also exposed as `muk_mcp` tools
  (`find_repair_order_matches`, `link_purchase_order_to_repair`), so the same capability
  is usable directly from the MuK AI chat, not just from the automated import flow.

## Notices

Every notice about a purchase order goes through the shared path of
`edi_purchase_order_import` (`purchase.order._edi_post_notice()`, see its README), and
nothing is posted with `message_post(partner_ids=...)` any more, which emailed followers
(the vendor, among them) and the notify group by preference. On the **purchase order**:

| Notice                                                                | Kind                               | Inbox of the notify group | Email                                                           |
| --------------------------------------------------------------------- | ---------------------------------- | ------------------------- | --------------------------------------------------------------- |
| Confirmed automatically (`edi_purchase_order_import`)                 | outstanding                        | yes, until matched        | one, to the shop mailbox that forwarded the vendor's email only |
| TypeSafe's suggestion, with **Confirm Match**                         | outstanding                        | yes, until matched        | the same                                                        |
| TypeSafe could not suggest a repair order                             | outstanding                        | yes, until matched        | the same                                                        |
| The PO number names a repair order that is closed                     | outstanding                        | yes, until matched        | the same                                                        |
| "Linked to repair order ..." (a user matched it)                      | plain internal note, informational | no                        | no                                                              |
| "... so it was linked automatically" (PO number; nobody confirmed it) | informational                      | yes (stays unread)        | no                                                              |

- **Who gets the email.** Only the address(es) the vendor's email was addressed to or
  forwarded from - the shop mailbox whose Gmail rule forwards into the alias, and only if
  it is an allowed one (Settings > Purchase > **Allowed Reply Addresses**, or a user's or
  company's email: the addresses come from headers whoever can write to the alias
  controls) - as a reply
  in the thread of the original email (`Re: <subject>`, `In-Reply-To`/`References` of the
  inbound `Message-Id`). Never the vendor, the repair order's customer, other followers or
  the notify group (they get the inbox notification, never an email). An order with no
  such address (e.g. a PDF upload, or a vendor writing straight to the alias) sends no
  email at all. The reply of the shop lands on the purchase order, as an internal note
  (the vendor is not mailed it). The record links in the emailed copy are absolute.
- **The Confirm Match button in the email** is the same link as in the chatter: it is
  login-protected (a recipient who is not logged in is sent to the login page first), tied
  to its purchase order/repair order pair by a signed token, and runs with the _rights of
  whoever clicks it_ (see _Access_). A shop mailbox owner without those rights gets a 403
  page and nothing happens; so does a malformed token (also a non-ASCII one). See also _Stale buttons_ below.
- **On the repair order** the suggestion and link messages are **internal notes**
  (`mail.mt_note`), never discussion messages: the customer follows the repair order, and
  a discussion message would be emailed to them. An internal note is only ever sent to
  followers who are internal users (and only the ones that subscribed to notes). Nobody
  is notified explicitly. The suggestion note is tied to the purchase order it concerns
  (`mail.message.repair_match_purchase_order_id`, a field only the Settings group can
  write: it decides whose notifications get cleared) and flagged outstanding, so that it can
  be cleared for exactly that purchase order, on whichever repair orders it was suggested
  to.

### Clearing

The moment a purchase order is linked to a repair order - inside `_link_to_repair_order`,
so whichever way it happens: the Match Order card, the Match Repair dialog, the Confirm
Match link, the automatic PO-number match, the queue job, the MCP tool - its outstanding
notices are cleared with `_edi_clear_notices()`: their inbox notifications are marked read
for **all** users (and the inbox counters refreshed), on the purchase order and on every
repair order the suggestion went to. Clearing is quiet: no email, no new notification, the
notices stay in the chatter as history, and the informational messages (never outstanding)
are untouched. It is a technical operation and uses sudo narrowly, only to flip `is_read`
on those notifications, so any user who may match can clear.

If an order is **already matched when a notice is posted** (the PO-number match ran before
the held-back confirmation notice was released under `quick_exec`, say),
`_edi_notice_still_needed()` is false: the notice is posted for the record without an inbox
notification and not flagged outstanding (the email, if asked, still goes: it is the reply
in the vendor's thread). The suggestion job also does nothing at all for an order somebody
matched in the meantime.

### Stale buttons

Old chatter messages keep their **Confirm Match** button. The link re-matches (moves
parts), so for an order matched since it is guarded: if the order is already matched to the
repair order of the link, nothing is done and the user lands on the order; if it is matched
to a different one, the user gets a 400 page naming it and pointing to **Match Repair** on
the purchase order, the deliberate way to move it. A cancelled repair order does not count
as a match (the order is up for matching again).

## Access

Matching is not a purchasing privilege: it edits a **repair order** and its parts. The
Match Order / Match Repair buttons are therefore shown to whoever really can match (a
non-stored flag, `repair_match_can_link`, computed from the user's own access rights and
record rules), not to a fixed group, and every action re-checks the same rights on the
server (an `AccessError` naming what is missing), so hiding a button is never the only
protection. Nothing is run with sudo on behalf of a user. What a match needs:

| Operation                                                                                       | Needs                                                                                             | Default group that has it                                                                                          |
| ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Read the purchase order and its lines                                                           | `purchase.order(.line)` read                                                                      | Purchase user, or Inventory user (`purchase_stock`)                                                                |
| Post the link on the purchase order's chatter                                                   | `purchase.order` write (posting on a document takes write access)                                 | Purchase user; an Inventory user only reads purchase orders                                                        |
| Read and edit the repair order (parts, chatter)                                                 | `repair.order` read + write                                                                       | Inventory user (`stock.group_stock_user`); Purchase alone has **no** access to repair orders                       |
| Add the parts to the repair order                                                               | `stock.move` create                                                                               | Inventory user or Purchase user                                                                                    |
| ... if the repair order has a quotation                                                         | `sale.order.line` create, and write on the quotation (a salesman edits their own quotations only) | Sales: User (an Inventory user can only edit sale lines)                                                           |
| ... if the purchase order's parts are on another open repair order (they are taken back off it) | `stock.move` unlink (and `sale.order.line` unlink when the parts are quoted)                      | Inventory Administrator (Purchase Administrator also unlinks moves, but needs Inventory user for the repair order) |
| Another company's records                                                                       | the multi-company record rules of purchase and repair orders                                      | the user must have the company enabled                                                                             |

So at a glance: **Purchase user + Inventory user** can match a purchase order to a
repair order that has no quotation yet; add **Sales: User** for repair orders with a
quotation, and **Inventory Administrator** to re-match a purchase order that is already
on another open repair order. **Purchase user alone cannot** (no access to repair
orders), **Inventory user alone cannot** (it can't post on the purchase order), and
neither can an internal user without those groups or a user of another company: the
buttons are hidden and the methods refuse with an `AccessError`.

- **Match Order** (repair order header, dialog and card button): the repair order must
  be editable by the user and the purchase orders readable. The dialog only offers what
  the user can read (record rules apply), and its search view's name is read with sudo,
  a purely technical read.
- **Match Repair** (purchase order and receipt headers, dialog and row click): the same
  rights; the receipt button follows its purchase order.
- **Unmatched filter** (`repair_match_unmatched`): the link between purchase lines and
  repair parts is read with sudo, as a sub-select that only filters the purchase orders
  the user can already read (a Purchase user can't read stock moves). It reveals one bit
  per readable purchase order - whether it is linked - and no repair or stock data.
- **Confirm Match** (chatter link): the signed token proves the link is genuine, not
  that the user may follow it. A logged-in user without the rights above gets a 403
  page, a stale suggestion (closed repair order, ...) a 400 page with the reason; never
  a traceback.
- **MCP tools**: `find_repair_order_matches` needs to read the purchase order and repair
  orders (only repair orders the user can read are offered to TypeSafe);
  `link_purchase_order_to_repair` needs the same rights and checks as the buttons.
- **Notices** are posted through `_edi_post_notice()`, which uses sudo for exactly that
  (a gateway user cannot post on purchase orders or create notifications): fixed content
  and recipients, nothing exposed to the caller. A user's own link note is posted with
  the user's own rights, as before.
- **Automatic matching** (PO number is a repair order number, TypeSafe suggestion): the
  queue job runs as whoever triggered the import - the mail alias' user or the mail
  gateway's, usually with no right on repair orders - so it runs with sudo
  (`_repair_auto_match_job`, `_link_to_repair_order(automatic=True)`). What it does is
  fixed by the module, not chosen by a user, and it widens no manual right: a manual
  link by the same user is still refused.

## Configuration

Settings > Purchase > **TypeSafe API Key**. Matching silently does nothing (no
suggestion posted, nothing logged as an error) until this is set - so this feature is
opt-in per install.

## What it does not do

- It doesn't consider repair orders with no vehicle on file, since there'd be no useful
  criteria to describe them by - vehicleless repairs still need to be linked by hand
  with the Match buttons.
- It doesn't retry or fall back to a deterministic match when TypeSafe is unreachable or
  returns nothing - it simply skips posting a suggestion for that purchase order, same
  as if no API key were configured.
