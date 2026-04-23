"""Validate a role YAML against the schema and the 10-item official gate.

Run from the showcase root:
    python examples/validate_yaml.py roles/engineering/backend_developer/v1.yaml
"""

import sys

import yaml

from rolecore.utils.schema_validator import SchemaValidator, OfficialGateValidator


def main(path: str):
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    print(f"Validating: {path}")
    print()

    # ─── layer 1: schema shape (9 required sections) ───────────────────────
    schema = SchemaValidator()
    schema_errors = schema.validate(data)
    print(f"Schema: {'✓ pass' if not schema_errors else '✗ fail'}")
    for err in schema_errors:
        print(f"  • {err}")

    # ─── layer 2: official gate (10 content-quality rules) ─────────────────
    gaps = OfficialGateValidator().check(data)
    print(f"Official gate: {'✓ pass' if not gaps else '✗ fail'}")
    for gap in gaps:
        print(f"  • {gap}")

    sys.exit(0 if not schema_errors and not gaps else 1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python examples/validate_yaml.py <path-to-role.yaml>")
        sys.exit(2)
    main(sys.argv[1])
