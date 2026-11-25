# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Write the JSON Schema of some modules' facades for a frontend.

Needs no database: importing the addons is enough for ``@facade`` to have
seen every method. The addons path comes from the nearest ``odoo.conf`` above
the current directory (the dev shell writes one at the repository root), or
from ``-c``. A frontend's ``pnpm run generate`` runs it from the addon::

    python ../repair_tech_api/tools/export_api_schema.py \\
        --module repair_tech_app --title RepairTechApp \\
        --out frontend/api/api.schema.json [--check]
"""

import argparse
import importlib
import json
import os
import pathlib
import sys


def render(schema):
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def find_config(start):
    for folder in (start, *start.parents):
        candidate = folder / "odoo.conf"
        if candidate.is_file():
            return candidate
    sys.exit(f"no odoo.conf in {start} or above it: pass -c")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-c", "--config", type=pathlib.Path)
    parser.add_argument(
        "--module",
        action="append",
        required=True,
        help="an addon whose facades the frontend calls (repeat for several)",
    )
    parser.add_argument("--title", required=True, help="the root type's name")
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument(
        "--check", action="store_true", help="fail instead of writing if out of date"
    )
    args = parser.parse_args(argv)

    from odoo.tools import config

    out = args.out.resolve()
    # absolute(), not resolve(): the dev shell links odoo.conf into the Nix store.
    conf = (args.config or find_config(pathlib.Path.cwd())).absolute()
    # The dev shell's addons_path is relative to the repository root.
    os.chdir(conf.parent)
    config.parse_config(["-c", str(conf)])  # also sets up odoo.addons.__path__
    for module in args.module:
        importlib.import_module(f"odoo.addons.{module}")
    # A script run with a config, not a module of the addon: no relative import.
    from odoo.addons.repair_tech_api.facade import (  # pylint: disable=odoo-addons-relative-import
        api_schema,
    )

    text = render(api_schema(args.module, args.title))
    if args.check:
        if not out.exists() or out.read_text() != text:
            sys.exit(f"{out} is out of date: run `pnpm run generate`")
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(f"wrote {out}")  # pylint: disable=print-used


if __name__ == "__main__":
    main()
