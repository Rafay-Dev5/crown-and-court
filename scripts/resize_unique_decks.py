"""Resize King/Noble decks to 30/40 unique cards (1 copy each)."""

from __future__ import annotations

import json
from pathlib import Path

from engine.cards import load_all_cards, write_manifest

ROOT = Path(__file__).resolve().parent.parent
KING_DIR = ROOT / "cards" / "king_deck"
NOBLE_DIR = ROOT / "cards" / "noble_deck"

TARGET_KING = 30
TARGET_NOBLE = 40


def _set_unique_copies(deck_dir: Path) -> list[str]:
    ids: list[str] = []
    for path in sorted(deck_dir.glob("*.json")):
        card = json.loads(path.read_text(encoding="utf-8"))
        card["copies_in_deck"] = 1
        path.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
        ids.append(card["id"])
    return ids


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_").replace("'", "")


def _stub_king(idx: int) -> dict:
    categories = ["economy", "disruption", "alliance", "protection", "tempo", "information"]
    cat = categories[idx % len(categories)]
    name = f"Royal Edict {idx + 1}"
    cid = f"king_{_slug(name)}_{idx + 1:03d}"
    return {
        "id": cid,
        "name": name,
        "owner_type": "king",
        "category": cat,
        "rarity": "common",
        "copies_in_deck": 1,
        "timing": "on_reveal",
        "effect": {"primitive": "gold_gain", "params": {"target": "self", "amount": 45 + idx * 3}},
        "tags": [cat],
        "flavor_text": "A decree from the throne.",
        "designer_notes": "Auto-generated unique deck filler for 30-card King deck.",
    }


def _stub_noble(idx: int) -> dict:
    categories = ["economy", "disruption", "betrayal", "alliance", "protection", "tempo"]
    cat = categories[idx % len(categories)]
    name = f"Court Gambit {idx + 1}"
    cid = f"noble_{_slug(name)}_{idx + 1:03d}"
    return {
        "id": cid,
        "name": name,
        "owner_type": "noble",
        "category": cat,
        "rarity": "common",
        "copies_in_deck": 1,
        "timing": "on_reveal",
        "effect": {"primitive": "gold_gain", "params": {"target": "self", "amount": 35 + idx * 2}},
        "tags": [cat],
        "flavor_text": "A noble's calculated move.",
        "designer_notes": "Auto-generated unique deck filler for 40-card Noble deck.",
    }


def _add_stubs(deck_dir: Path, owner: str, target: int, factory) -> int:
    existing = len(list(deck_dir.glob("*.json")))
    added = 0
    idx = existing
    while existing + added < target:
        card = factory(idx)
        path = deck_dir / f"{_slug(card['name'])}.json"
        if path.exists():
            idx += 1
            continue
        path.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
        added += 1
        idx += 1
    return added


def resize_decks() -> dict:
    king_ids = _set_unique_copies(KING_DIR)
    noble_ids = _set_unique_copies(NOBLE_DIR)
    king_added = _add_stubs(KING_DIR, "king", TARGET_KING, _stub_king)
    noble_added = _add_stubs(NOBLE_DIR, "noble", TARGET_NOBLE, _stub_noble)
    manifest = write_manifest()
    return {
        "king_unique": len(list(KING_DIR.glob("*.json"))),
        "noble_unique": len(list(NOBLE_DIR.glob("*.json"))),
        "king_added": king_added,
        "noble_added": noble_added,
        "card_set_version": manifest["version"],
        "king_copies_each": 1,
        "noble_copies_each": 1,
    }


def main() -> None:
    result = resize_decks()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
