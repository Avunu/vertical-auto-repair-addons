# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import Command, _, models
from odoo.exceptions import UserError
from odoo.osv import expression

from odoo.addons.repair_tech_api.facade import facade
from odoo.addons.repair_tech_api.schemas import Ref

from ..schemas import (
    CatalogPage,
    CatalogProduct,
    Code,
    Page,
    Part,
    PartList,
    PartScan,
    PositiveQuantity,
    Product,
    Quantity,
)
from .repair_tech_app import EDITABLE_REPAIR_STATES, _selection_label


# One facade model, split by screen across files on purpose.
class RepairTechApp(models.AbstractModel):
    _inherit = "repair.tech.app"  # pylint: disable=consider-merging-classes-inherited

    # ------------------------------------------------------------------
    # Parts on the job
    # ------------------------------------------------------------------

    @facade
    def parts(self, repair_id: int) -> PartList:
        """The parts the job expects, and what has been used so far."""
        return self._part_list(self._get_job(repair_id))

    @facade
    def scan_part(self, repair_id: int, code: Code) -> PartScan:
        """What a scanned barcode is: one of the job's parts, or a product the
        job doesn't have yet (to offer adding it). Matches the barcode, then
        the internal reference, then a lot or serial number."""
        repair = self._get_job(repair_id)
        code = code.strip()
        products = self._products_from_code(code)
        if not products:
            products = self._lots_from_code(code).product_id
        if not products:
            raise UserError(_("No part matches %s.", code))
        # An internal reference or a lot number needn't be unique: the job's
        # own part wins over a namesake from the catalogue.
        move = self._job_parts(repair).filtered(lambda m: m.product_id in products)[:1]
        if move:
            return PartScan(move_id=move.id, product=None)
        return PartScan(move_id=None, product=self._catalog_product(products[:1]))

    @facade
    def set_part_quantity(
        self,
        move_id: int,
        quantity: Quantity,
        lot_id: int | None = None,
        lot_name: str | None = None,
    ) -> PartList:
        """Record how much of a part was used, with its lot or serial when it
        is tracked: ``lot_id`` from a picker, ``lot_name`` from a scanner.

        Writes ``stock.move.quantity`` only: changing the demand
        (``product_uom_qty``) would make core rewrite the customer's approved
        quote line.
        """
        move = self._get_part(move_id)
        self._check_parts_editable(move.repair_id)
        lot = None
        if lot_id:
            lot = self.env["stock.lot"].browse(lot_id).exists()
            if not lot or lot.product_id != move.product_id:
                raise UserError(_("That lot isn't one of %s.", move.product_id.name))
        elif lot_name:
            lot = self._lot_from_code(lot_name.strip(), move.product_id)
            if not lot:
                raise UserError(
                    _("No lot or serial %(lot)s for %(product)s.")
                    % {"lot": lot_name, "product": move.product_id.name}
                )
        self._set_move_quantity(move, quantity, lot)
        return self._part_list(move.repair_id)

    @facade
    def use_all(self, move_id: int) -> PartList:
        """Mark the whole expected quantity as used. Not for tracked parts:
        their lots or serials have to be scanned."""
        move = self._get_part(move_id)
        self._check_parts_editable(move.repair_id)
        if move.product_id.tracking != "none":
            raise UserError(
                _("%s is tracked: scan its lot or serial.", move.product_id.name)
            )
        self._set_move_quantity(move, move.product_uom_qty)
        return self._part_list(move.repair_id)

    @facade
    def reset_part(self, move_id: int) -> PartList:
        """Undo the part's usage: back to nothing used."""
        move = self._get_part(move_id)
        self._check_parts_editable(move.repair_id)
        self._set_move_quantity(move, 0.0)
        return self._part_list(move.repair_id)

    def _get_part(self, move_id):
        move = self.env["stock.move"].browse(move_id).exists()
        if not move or not move.repair_id or move.repair_line_type != "add":
            raise UserError(_("That part is no longer on the job."))
        return move

    def _set_move_quantity(self, move, quantity, lot=None):
        tracking = move.product_id.tracking
        if (
            tracking != "none"
            and quantity
            and not lot
            and not move.move_line_ids.lot_id
        ):
            raise UserError(
                _("%s is tracked: scan its lot or serial.", move.product_id.name)
            )
        if tracking == "serial" and lot:
            # One unit per serial; core's inverse spreads them over move lines.
            move.lot_ids = [Command.link(lot.id)]
        else:
            move.quantity = quantity
            if lot:
                lines = move.move_line_ids.filtered(lambda line: not line.lot_id)
                (lines or move.move_line_ids).write({"lot_id": lot.id})
        move.picked = bool(move.quantity)

    def _products_from_code(self, code):
        """Products a code names: by barcode (unique), else by internal
        reference (not necessarily)."""
        Product = self.env["product.product"]
        for domain in ([("barcode", "=", code)], [("default_code", "=ilike", code)]):
            products = Product.search(domain, limit=50)
            if products:
                return products
        return Product

    def _lots_from_code(self, code):
        return self.env["stock.lot"].search([("name", "=", code)], limit=50)

    def _lot_from_code(self, code, product=None):
        domain = [("name", "=", code)]
        if product:
            domain.append(("product_id", "=", product.id))
        return self.env["stock.lot"].search(domain, limit=1)

    # ------------------------------------------------------------------
    # Catalog
    # ------------------------------------------------------------------

    @facade
    def catalog_categories(self) -> list[Ref]:
        """Product categories, for the catalog's filter."""
        return [
            Ref(id=categ.id, name=categ.display_name)
            for categ in self.env["product.category"].search([], limit=200)
        ]

    @facade
    def catalog(
        self,
        search: str | None = None,
        category_id: int | None = None,
        page: Page = 1,
    ) -> CatalogPage:
        """Browse the parts catalog: goods that can be purchased, by name,
        internal reference or barcode."""
        size = self._option_int("catalog_page_size", 30)
        domain = [
            # 18.0: goods are type 'consu'; is_storable only tells stocked ones
            # from the rest, and the shop fits both.
            ("type", "=", "consu"),
            ("purchase_ok", "=", True),
        ]
        if category_id:
            domain.append(("categ_id", "child_of", category_id))
        search = (search or "").strip()
        if search:
            domain = expression.AND(
                [
                    domain,
                    [
                        "|",
                        "|",
                        ("name", "ilike", search),
                        ("default_code", "ilike", search),
                        ("barcode", "=", search),
                    ],
                ]
            )
        Product = self.env["product.product"]
        products = Product.search(
            domain, limit=size, offset=(page - 1) * size, order="default_code, name"
        )
        return CatalogPage(
            records=[self._catalog_product(product) for product in products],
            total=Product.search_count(domain),
            page=page,
            page_size=size,
        )

    @facade
    def add_part(
        self,
        repair_id: int,
        product_id: int,
        quantity: PositiveQuantity = 1.0,
        used: bool = False,
    ) -> PartList:
        """Add a part from the catalog to the job; ``used`` records it as
        installed straight away (untracked parts only).

        The part reaches the customer's quote, as core does for any part added
        to a repair - on purpose. It is flagged as added by the technician and
        a note on the order says so, so the service advisor sees what was added
        on top of what the customer approved and decides what to bill.
        """
        repair = self._get_job(repair_id)
        if repair.state not in EDITABLE_REPAIR_STATES:
            raise UserError(_("%s is closed; its parts can't change.", repair.name))
        product = self.env["product.product"].browse(product_id).exists()
        if not product:
            raise UserError(_("That part no longer exists."))
        move = self.env["stock.move"].create(
            {
                "repair_id": repair.id,
                "repair_line_type": "add",
                "product_id": product.id,
                "product_uom_qty": quantity,
                "product_uom": product.uom_id.id,
                "company_id": repair.company_id.id,
                "tech_added_uid": self.env.uid,
            }
        )
        body = _(
            "%(user)s added %(qty)s x %(product)s from the technician app.",
            user=self.env.user.display_name,
            qty=f"{quantity:g}",
            product=product.display_name,
        )
        if repair.sale_order_id:
            body += " " + _(
                "It was added to quotation %(order)s: review it before invoicing.",
                order=repair.sale_order_id.name,
            )
        # _message_log, not message_post: the latter wants the author's email
        # address, and a technician without one must still be able to add the
        # part they installed. Nothing is emailed; it is a log note.
        repair._message_log(body=body)
        if used and product.tracking == "none":
            self._set_move_quantity(move, quantity)
        return self._part_list(repair)

    # ------------------------------------------------------------------
    # Record -> schema
    # ------------------------------------------------------------------

    def _part_list(self, repair):
        return PartList(
            job=self._job_summary(repair),
            parts=[self._part(move) for move in self._job_parts(repair)],
            can_edit=repair.state in EDITABLE_REPAIR_STATES,
        )

    def _part(self, move):
        return Part(
            id=move.id,
            product=self._product(move.product_id),
            quantity_demand=move.product_uom_qty,
            quantity_done=move.quantity,
            picked=move.picked,
            state=move.state,
            state_label=_selection_label(move, "state"),
            available=move.state == "assigned",
            added_by_technician=bool(move.tech_added_uid),
            lots=[Ref(id=lot.id, name=lot.name) for lot in move.move_line_ids.lot_id],
        )

    def _product(self, product):
        return Product(**self._product_values(product))

    def _catalog_product(self, product):
        return CatalogProduct(
            **self._product_values(product), qty_available=product.qty_available
        )

    def _product_values(self, product):
        return {
            "id": product.id,
            # The variant's name without "[code]": the code has its own field.
            "name": product.with_context(display_default_code=False).display_name,
            "default_code": product.default_code or None,
            "barcode": product.barcode or None,
            "tracking": product.tracking,
            "uom": Ref(id=product.uom_id.id, name=product.uom_id.name),
        }
