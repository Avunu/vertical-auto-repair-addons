# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Typed model methods for frontends that talk to Odoo over ``call_kw``.

A facade is an ordinary public ``@api.model`` method whose signature *is* its
contract::

    @facade
    def tech_job(self, repair_id: int) -> JobDetail:
        ...

``@facade`` reads the annotations once, at import time, and from then on:

- validates the keyword arguments against a Pydantic model built from the
  parameters (unknown or mistyped arguments are refused before the body runs),
- validates the return value against the return annotation and dumps it to
  JSON-safe primitives, so a facade can never leak a field it didn't declare,
- records the method so :func:`api_schema` can describe every facade of some
  modules as one JSON Schema, which ``tools/generate_api_types.mjs`` turns
  into TypeScript in the frontend that calls them.

Nothing here talks HTTP. The same method answers ``/web/dataset/call_kw`` on
18.0 and ``/json/2/<model>/<method>`` on 19.0+ (JSON-2 posts the keyword
arguments as the body, which is exactly what a facade takes), and is a plain
Python call from tests and server actions.

Datetimes cross the wire with their offset (Pydantic's ``AwareDatetime``);
:func:`naive_utc` turns one into what Odoo stores, and :func:`aware` back.
"""

import functools
import inspect
import typing
from datetime import UTC, datetime

from pydantic import ConfigDict, Field, TypeAdapter, create_model
from pydantic import ValidationError as PydanticValidationError

from odoo import api
from odoo.exceptions import ValidationError

FACADE_ATTR = "_facade_spec"


class FacadeSpec:
    """What ``@facade`` learned from one method's signature."""

    def __init__(self, func):
        self.name = func.__name__
        self.doc = inspect.getdoc(func) or ""
        # include_extras: without it Annotated[...] loses its metadata, and
        # with it every Field(gt=0, max_length=...) constraint.
        hints = typing.get_type_hints(func, include_extras=True)
        if "return" not in hints:
            raise TypeError(f"facade {self.name}() needs a return annotation")
        self.result_type = hints["return"]
        self.result = TypeAdapter(self.result_type)

        self.signature = inspect.signature(func)
        fields = {}
        for param in list(self.signature.parameters.values())[1:]:  # skip self
            if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                raise TypeError(f"facade {self.name}() cannot take *args/**kwargs")
            if param.name not in hints:
                raise TypeError(f"facade {self.name}(): {param.name} is not annotated")
            default = ... if param.default is param.empty else param.default
            fields[param.name] = (hints[param.name], default)
        self.params = create_model(
            f"{_pascal(self.name)}Params",
            __config__=ConfigDict(extra="forbid"),
            **fields,
        )

    def validate_params(self, args, kwargs):
        try:
            bound = self.signature.bind(None, *args, **kwargs)
        except TypeError as err:
            raise ValidationError(f"{self.name}: {err}") from err
        bound.arguments.pop("self")
        try:
            params = self.params.model_validate(bound.arguments)
        except PydanticValidationError as err:
            raise ValidationError(_format_errors(self.name, err)) from err
        # Field values, not ``model_dump()``: nested models stay models.
        return {name: getattr(params, name) for name in type(params).model_fields}

    def dump_result(self, value):
        # Validating first means a facade body that builds the wrong shape
        # fails in tests, not in the technician's hands.
        return self.result.dump_python(
            self.result.validate_python(value, from_attributes=True), mode="json"
        )


def facade(func):
    """Declare a typed, ``call_kw``-callable model method. Implies ``@api.model``."""
    spec = FacadeSpec(func)

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        return spec.dump_result(func(self, **spec.validate_params(args, kwargs)))

    setattr(wrapper, FACADE_ATTR, spec)
    return api.model(wrapper)


def module_facades(module):
    """``{model_name: [FacadeSpec, ...]}`` for every facade a module defines.

    Read from the model classes the module itself declares, so it works
    without a database or a registry - all it needs is the module imported.
    """
    from odoo.models import MetaModel

    found = {}
    for cls in MetaModel.module_to_models.get(module, []):
        model_name = cls._name or cls._inherit
        for attr in vars(cls).values():
            spec = getattr(attr, FACADE_ATTR, None)
            if spec is not None:
                found.setdefault(model_name, []).append(spec)
    for specs in found.values():
        specs.sort(key=lambda spec: spec.name)
    return dict(sorted(found.items()))


def api_schema(modules, title):
    """One JSON Schema describing every facade of ``modules`` (a module name
    or several).

    The root object maps model name -> method name -> ``{params, result}``,
    and every Pydantic model involved lands once in ``$defs``. Built by
    nesting the specs into one throwaway Pydantic model, so Pydantic itself
    resolves and deduplicates the references.
    """
    if isinstance(modules, str):
        modules = [modules]
    facades = {}
    for module in modules:
        for model_name, specs in module_facades(module).items():
            facades.setdefault(model_name, []).extend(specs)
    model_fields = {}
    for model_name, specs in sorted(facades.items()):
        specs = sorted(specs, key=lambda spec: spec.name)
        method_fields = {}
        for spec in specs:
            method = create_model(
                f"{_pascal(spec.name)}Method",
                __config__=ConfigDict(title=f"{_pascal(spec.name)}Method"),
                __doc__=spec.doc or None,
                params=(spec.params, ...),
                result=(spec.result_type, ...),
            )
            method_fields[spec.name] = (method, ...)
        methods = create_model(
            f"{_pascal(model_name)}Methods",
            __doc__=f"Facades on {model_name}.",
            **method_fields,
        )
        model_fields[_identifier(model_name)] = (
            methods,
            Field(..., alias=model_name),
        )
    root = create_model(
        title, __doc__=f"Facades defined by {', '.join(modules)}.", **model_fields
    )
    return root.model_json_schema(by_alias=True)


def naive_utc(value):
    """An aware datetime from a client -> the naive UTC Odoo stores."""
    if value is None:
        return None
    return value.astimezone(UTC).replace(tzinfo=None)


def aware(value):
    """Odoo's naive UTC -> aware, so JSON carries the offset (``...Z``) and a
    browser doesn't read it as local time."""
    if not value:
        return None
    if not isinstance(value, datetime):
        raise TypeError(f"aware() takes a datetime, not {value!r}")
    return value.replace(tzinfo=UTC)


def _pascal(name):
    return "".join(
        part[:1].upper() + part[1:] for part in name.replace(".", "_").split("_")
    )


def _identifier(model_name):
    return model_name.replace(".", "_")


def _format_errors(name, err):
    lines = [f"Invalid arguments for {name}:"]
    for error in err.errors():
        location = ".".join(str(part) for part in error["loc"]) or "(arguments)"
        lines.append(f"- {location}: {error['msg']}")
    return "\n".join(lines)
