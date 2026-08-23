from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import jsonschema
import yaml


CARDS_DIR = Path(__file__).resolve().parent.parent / "cards"
SCHEMA_PATH = CARDS_DIR / "schema.json"
MANIFEST_PATH = CARDS_DIR / "manifest.json"


def load_schema() -> dict[str, Any]:
    with SCHEMA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def load_card_file(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_all_cards() -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for sub in ("king_deck", "noble_deck"):
        deck_dir = CARDS_DIR / sub
        if not deck_dir.exists():
            continue
        for path in sorted(deck_dir.glob("*.json")):
            cards.append(load_card_file(path))
    return cards


def compute_card_set_version(cards: list[dict[str, Any]] | None = None) -> str:
    cards = cards or load_all_cards()
    payload = json.dumps(sorted(cards, key=lambda c: c.get("id", "")), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def write_manifest() -> dict[str, Any]:
    cards = load_all_cards()
    manifest = {
        "version": compute_card_set_version(cards),
        "card_count": len(cards),
        "card_ids": sorted(c.get("id", "") for c in cards),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def build_deck(
    cards: list[dict[str, Any]],
    owner_type: str,
    deck_size: int | None = None,
) -> list[dict[str, Any]]:
    """Build deck from cards, optionally taking first N designs (sorted by id)."""
    filtered = [c for c in cards if c.get("owner_type") == owner_type]
    filtered.sort(key=lambda c: c.get("id", ""))
    if deck_size is not None and deck_size > 0:
        filtered = filtered[:deck_size]
    deck: list[dict[str, Any]] = []
    for card in filtered:
        copies = int(card.get("copies_in_deck", 1))
        for _ in range(copies):
            deck.append(dict(card))
    return deck


def validate_card(card: dict[str, Any], schema: dict[str, Any] | None = None) -> list[str]:
    schema = schema or load_schema()
    errors: list[str] = []
    try:
        jsonschema.validate(instance=card, schema=schema)
    except jsonschema.ValidationError as exc:
        errors.append(str(exc.message))
    return errors


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    default = {
        "num_players": 6,
        "n_rounds": 5,
        "hand_size": 8,
        "king_start_gold": 1000,
        "noble_start_gold": 600,
        "negotiation_ticks": 4,
        "succession_checker": "earned_gold",
        "alternate_turn_direction": True,
    }
    if path is None:
        return default
    config_path = Path(path)
    if not config_path.exists():
        return default
    with config_path.open(encoding="utf-8") as f:
        loaded = yaml.safe_load(f) or {}
    return {**default, **loaded}
