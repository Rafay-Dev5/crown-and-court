from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engine.cards import CARDS_DIR, load_all_cards, load_schema, validate_card
from engine.effects.registry import VALID_PRIMITIVES


def _collect_primitives(effect: dict | None, found: set[str]) -> None:
    if not effect:
        return
    prim = effect.get("primitive")
    if prim:
        found.add(prim)
    for key in ("secondary_effect", "on_success", "on_failure", "effect_if_true", "effect_if_false"):
        if key in effect and isinstance(effect[key], dict):
            _collect_primitives(effect[key], found)
    params = effect.get("params") or {}
    for key in ("on_success", "on_failure", "effect_if_match", "effect_if_no_match", "effect_if_present", "effect_if_absent"):
        if key in params and isinstance(params[key], dict):
            _collect_primitives(params[key], found)
    branches = params.get("branches", {})
    for branch in branches.values():
        if isinstance(branch, dict):
            for bk in ("on_success", "on_failure"):
                if bk in branch and isinstance(branch[bk], dict):
                    _collect_primitives(branch[bk], found)


def validate_all() -> tuple[int, list[str]]:
    schema = load_schema()
    cards = load_all_cards()
    errors: list[str] = []
    seen_ids: set[str] = set()

    if not cards:
        errors.append(f"No cards found under {CARDS_DIR}")

    for card in cards:
        cid = card.get("id", "<unknown>")
        if cid in seen_ids:
            errors.append(f"Duplicate card id: {cid}")
        seen_ids.add(cid)

        for msg in validate_card(card, schema):
            errors.append(f"{cid}: {msg}")

        primitives: set[str] = set()
        _collect_primitives(card.get("effect"), primitives)
        for prim in primitives:
            if prim not in VALID_PRIMITIVES:
                errors.append(f"{cid}: unknown primitive '{prim}'")

    return len(errors), errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Crown & Court card JSON")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    args = parser.parse_args()

    count, errors = validate_all()
    if args.json:
        print(json.dumps({"valid": count == 0, "error_count": count, "errors": errors}, indent=2))
    else:
        if errors:
            print(f"Validation failed with {count} error(s):")
            for err in errors:
                print(f"  - {err}")
        else:
            print("All cards valid.")

    sys.exit(0 if count == 0 else 1)


if __name__ == "__main__":
    main()
