# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).


def typesafe_format_datetime(value):
    """Format a datetime for a TypeSafe state/criteria value, or None."""
    return value.strftime("%m/%d/%Y %I:%M %p") if value else None
