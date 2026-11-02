# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.addons.component.core import Component


class SearchAction(Component):
    """Turn a scanned string into a record.

    Kept in one place so a barcode resolves identically no matter which state
    the technician scanned from.
    """

    _inherit = "shopfloor.search.action"

    def repair_from_scan(self, barcode):
        """Find a job from an RO reference, a quote number, a VIN, a plate or a
        unit number.

        Ordered cheapest-and-most-specific first: the repair order's own name
        is what the shop prints on the work order, so it wins over a plate
        that a customer might share across two visits.
        """
        if not barcode:
            return self.env["repair.order"].browse()
        model = self.env["repair.order"]
        for domain in (
            [("name", "=", barcode)],
            [("sale_order_id.name", "=", barcode)],
            [("vehicle_id.vin_sn", "=ilike", barcode)],
            [("vehicle_id.license_plate", "=ilike", barcode)],
            # Last: unlike a plate, a unit number is only unique within one
            # customer's fleet, so it is the least specific match.
            [("vehicle_id.unit_number", "=ilike", barcode)],
        ):
            # Newest first: a plate or VIN legitimately matches every past
            # visit of that vehicle, and the technician means the current one.
            record = model.search(domain, order="id desc", limit=1)
            if record:
                return record
        return model.browse()

    def product_from_scan(self, barcode):
        """Find a part from its barcode, then its internal reference."""
        if not barcode:
            return self.env["product.product"].browse()
        model = self.env["product.product"]
        for domain in ([("barcode", "=", barcode)], [("default_code", "=", barcode)]):
            record = model.search(domain, limit=1)
            if record:
                return record
        return model.browse()

    def lot_from_scan(self, barcode, product=None):
        if not barcode:
            return self.env["stock.lot"].browse()
        domain = [("name", "=", barcode)]
        if product:
            domain.append(("product_id", "=", product.id))
        return self.env["stock.lot"].search(domain, limit=1)
