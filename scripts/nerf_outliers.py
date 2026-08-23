"""Apply manual nerfs/buffs from balance reports. Never changes starting gold."""

from __future__ import annotations

import json
from pathlib import Path

from engine.cards import write_manifest

# Phase A: reduce King card power and buff Noble catch-up without touching start gold.
NERFS: dict[str, dict] = {
    "king_royal_pardon_001": {
        "effect": {
            "primitive": "gold_gain",
            "params": {"target": "self", "amount": 120},
            "secondary_effect": {
                "primitive": "gold_loss",
                "params": {"target": "self", "amount": 90},
            },
        },
        "designer_notes": "Nerfed from 300 flat gain; supercard now has built-in cost on reveal.",
    },
    "king_imperial_edict_001": {
        "effect": {
            "primitive": "gold_gain",
            "params": {"target": "self", "amount": 170},
            "secondary_effect": {
                "primitive": "gold_loss",
                "params": {"target": "self", "amount": 110},
            },
        },
    },
    "king_tax_levy_001": {
        "effect": {"primitive": "gold_gain", "params": {"target": "self", "amount": 55}},
    },
    "king_treasury_dividend_001": {
        "effect": {"primitive": "gold_gain", "params": {"target": "self", "amount": 80}},
    },
    "king_crown_tribute_001": {
        "effect": {
            "primitive": "gold_transfer",
            "params": {"from": "target", "to": "self", "amount": 70},
        },
    },
    "king_regal_momentum_001": {
        "effect": {
            "primitive": "draw_extra",
            "params": {"target": "self", "count": 1},
        },
    },
    "king_alliance_summit_001": {
        "effect": {
            "primitive": "alliance_bonus",
            "params": {"players": ["self", "target"], "amount": 40},
        },
    },
    "noble_assassins_blade_001": {
        "effect": {
            "primitive": "gold_transfer",
            "params": {"from": "king", "to": "self", "amount": 270, "as_theft": True},
            "secondary_effect": {
                "primitive": "mark_status",
                "params": {"target": "self", "status_name": "marked", "duration_rounds": 3},
            },
        },
    },
    "noble_coup_plot_001": {
        "effect": {
            "primitive": "gold_transfer",
            "params": {"from": "target", "to": "self", "amount": 140, "as_theft": True},
            "secondary_effect": {
                "primitive": "mark_status",
                "params": {"target": "self", "status_name": "marked", "duration_rounds": 2},
            },
        },
    },
    "noble_blackmail_001": {
        "effect": {
            "primitive": "gold_transfer",
            "params": {"from": "target", "to": "self", "amount": 75, "as_theft": True},
        },
    },
    "noble_market_manipulation_001": {
        "effect": {"primitive": "gold_gain", "params": {"target": "self", "amount": 90}},
    },
    "noble_tithe_collectors_001": {
        "effect": {"primitive": "gold_gain", "params": {"target": "self", "amount": 85}},
    },
    "king_corruption_inquiry_001": {
        "effect": {
            "primitive": "conditional_swing",
            "params": {
                "condition": {
                    "prior_choice": "invest_private",
                    "target": "target",
                    "within_rounds": 2,
                },
                "effect_if_true": {
                    "primitive": "conditional_swing",
                    "params": {
                        "condition": {
                            "dice_failed": True,
                            "card_id": "noble_development_fund_001",
                            "target": "target",
                            "within_rounds": 2,
                        },
                        "effect_if_true": {
                            "primitive": "gold_loss",
                            "params": {"target": "target", "amount": 140},
                        },
                        "effect_if_false": {
                            "primitive": "gold_loss",
                            "params": {"target": "target", "amount": 70},
                        },
                    },
                },
                "effect_if_false": {
                    "primitive": "gold_loss",
                    "params": {"target": "target", "amount": 35},
                },
            },
        },
    },
    "noble_poisoned_chalice_001": {
        "effect": {
            "primitive": "gold_transfer",
            "params": {"from": "target", "to": "self", "amount": 155, "as_theft": True},
        },
    },
    "noble_fence_goods_001": {
        "effect": {
            "primitive": "gold_transfer",
            "params": {"from": "target", "to": "self", "amount": 72, "as_theft": True},
        },
    },
    "noble_loan_shark_001": {
        "effect": {
            "primitive": "gold_transfer",
            "params": {"from": "target", "to": "self", "amount": 95, "as_theft": True},
        },
    },
}


def apply_nerfs(cards_dir: Path | None = None) -> list[str]:
    root = cards_dir or Path(__file__).resolve().parent.parent / "cards"
    changes: list[str] = []

    for cid, patch in NERFS.items():
        owner = "king" if cid.startswith("king_") else "noble"
        slug = cid.replace("_001", "").split("_", 1)[-1]
        path = root / f"{owner}_deck" / f"{slug}.json"
        if not path.exists():
            continue
        card = json.loads(path.read_text(encoding="utf-8"))
        old_effect = json.dumps(card.get("effect", {}))
        if "effect" in patch:
            card["effect"] = patch["effect"]
        if "designer_notes" in patch:
            card["designer_notes"] = patch["designer_notes"]
        path.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
        changes.append(f"{cid}: effect updated (was {old_effect[:80]}...)")

    write_manifest()
    return changes


def main() -> None:
    changes = apply_nerfs()
    for c in changes:
        print(c)
    print(f"Applied {len(changes)} card patches (starting gold unchanged)")


if __name__ == "__main__":
    main()
