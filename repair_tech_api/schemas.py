# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""The job board's data shapes, and the base every facade schema builds on.

Only Pydantic here, no Odoo: these classes are the contract, and the board's
``frontend/api/api.d.ts`` is generated from them. Field docstrings become
JSDoc comments on the TypeScript side.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

BoardStatus = Literal["diag", "pa", "cust", "parts", "ready", "repair"]
BoardIcon = Literal["car", "truck"]


class Schema(BaseModel):
    """Every facade shape: no unknown fields in, none leaked out, and field
    docstrings carried into the generated TypeScript."""

    model_config = ConfigDict(extra="forbid", use_attribute_docstrings=True)


class Ref(Schema):
    """Any record shown by name."""

    id: int
    name: str


class BoardJobType(Schema):
    """An appointment type with a job board icon."""

    id: int
    label: str
    """For the board's key, e.g. ``Heavy truck``."""
    icon: BoardIcon


class BoardJob(Schema):
    """One card on the shop's job board."""

    id: int
    name: str
    """The order's reference, e.g. ``RO/00123``."""
    number: str
    """The digits of ``name`` without leading zeros, for the card: ``123``."""
    customer: str
    vehicle: str
    """Model year and model, e.g. ``2019 Cascadia``. Empty without a vehicle."""
    job_type: BoardJobType | None
    """The job's appointment type, when that type has a board icon."""
    status: BoardStatus
    """From the job's stage (``repair.order.stage.board_status``)."""
    technician_id: int | None
    """``None`` puts the card in the board's unassigned column."""


class Board(Schema):
    """Everything the shop's job board draws."""

    jobs: list[BoardJob]
    """Open jobs whose stage has a board status, scheduled for today or
    earlier or not scheduled yet."""
    technicians: list[Ref]
    """Everyone with an open job that shows, by name: one column each."""
    job_types: list[BoardJobType]
    """Every appointment type with a board icon, for the board's key."""
