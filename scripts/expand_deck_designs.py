"""Add 15 King + 15 Noble designs for deck-size subset sweeps (PRD §10)."""

from __future__ import annotations

import json
from pathlib import Path

from engine.cards import write_manifest

ROOT = Path(__file__).resolve().parent.parent

KING_EXPANSION: list[dict] = [
    {"file": "expand_king_01.json", "id": "king_expand_mint_dues_001", "name": "Mint Dues", "category": "economy",
     "effect": {"primitive": "gold_gain", "params": {"target": "self", "amount": 95}}},
    {"file": "expand_king_02.json", "id": "king_expand_toll_bridge_002", "name": "Toll Bridge", "category": "economy",
     "effect": {"primitive": "gold_transfer", "params": {"from": "target", "to": "self", "amount": 55, "as_theft": True}}},
    {"file": "expand_king_03.json", "id": "king_expand_border_levy_003", "name": "Border Levy", "category": "economy",
     "effect": {"primitive": "gold_gain", "params": {"target": "self", "amount": 78}}},
    {"file": "expand_king_04.json", "id": "king_expand_royal_pact_004", "name": "Royal Pact", "category": "alliance",
     "effect": {"primitive": "alliance_bonus", "params": {"amount": 72, "players": ["self", "target"]}}},
    {"file": "expand_king_05.json", "id": "king_expand_summit_oath_005", "name": "Summit Oath", "category": "alliance",
     "effect": {"primitive": "alliance_bonus", "params": {"amount": 58, "players": ["self", "target"]}}},
    {"file": "expand_king_06.json", "id": "king_expand_sealed_warrant_006", "name": "Sealed Warrant II", "category": "disruption",
     "effect": {"primitive": "force_discard", "params": {"target": "target", "count": 1}}},
    {"file": "expand_king_07.json", "id": "king_expand_quarter_search_007", "name": "Quarter Search", "category": "disruption",
     "effect": {"primitive": "force_discard", "params": {"target": "target", "count": 2}}},
    {"file": "expand_king_08.json", "id": "king_expand_court_scribe_008", "name": "Court Scribe", "category": "information",
     "effect": {"primitive": "reveal_hand", "params": {"target": "target"}}},
    {"file": "expand_king_09.json", "id": "king_expand_ledger_audit_009", "name": "Ledger Audit", "category": "information",
     "effect": {"primitive": "reveal_hand", "params": {"target": "target"}}},
    {"file": "expand_king_10.json", "id": "king_expand_bastion_wall_010", "name": "Bastion Wall", "category": "protection",
     "timing": "reactive",
     "effect": {"primitive": "protect_gold", "params": {"target": "self", "amount": 90, "duration_rounds": 1,
                "specificity": "targeted", "blocks": "force_discard", "trigger": {"type": "attacked_this_phase", "target": "self"}}},
     "on_whiff_penalty": {"primitive": "gold_loss", "params": {"target": "self", "amount": 25}}},
    {"file": "expand_king_11.json", "id": "king_expand_iron_gate_011", "name": "Iron Gate", "category": "protection",
     "timing": "reactive",
     "effect": {"primitive": "block_succession", "params": {"scope": "next_check_this_round", "duration_rounds": 1,
                "trigger": {"type": "succession_imminent"}, "specificity": "targeted"}},
     "on_whiff_penalty": {"primitive": "gold_loss", "params": {"target": "self", "amount": 25}}},
    {"file": "expand_king_12.json", "id": "king_expand_haste_edict_012", "name": "Haste Edict", "category": "tempo",
     "effect": {"primitive": "extra_play", "params": {"target": "self", "count": 1}}},
    {"file": "expand_king_13.json", "id": "king_expand_muster_call_013", "name": "Muster Call", "category": "tempo",
     "effect": {"primitive": "draw_extra", "params": {"target": "self", "count": 2}}},
    {"file": "expand_king_14.json", "id": "king_expand_crown_gambit_014", "name": "Crown Gambit", "category": "betrayal",
     "effect": {"primitive": "gold_transfer", "params": {"from": "target", "to": "self", "amount": 88, "as_theft": True}}},
    {"file": "expand_king_15.json", "id": "king_expand_imperial_mandate_015", "name": "Imperial Mandate", "category": "supercard",
     "rarity": "supercard", "effect": {"primitive": "gold_gain", "params": {"target": "self", "amount": 145}},
     "secondary_effect": {"primitive": "draw_extra", "params": {"target": "self", "count": 1}}},
]

NOBLE_EXPANSION: list[dict] = [
    {"file": "expand_noble_01.json", "id": "noble_expand_silk_route_001", "name": "Silk Route", "category": "economy",
     "effect": {"primitive": "gold_gain", "params": {"target": "self", "amount": 88}}},
    {"file": "expand_noble_02.json", "id": "noble_expand_smugglers_cut_002", "name": "Smuggler's Cut", "category": "economy",
     "effect": {"primitive": "gold_transfer", "params": {"from": "king", "to": "self", "amount": 52, "as_theft": True}}},
    {"file": "expand_noble_03.json", "id": "noble_expand_merchant_league_003", "name": "Merchant League", "category": "economy",
     "effect": {"primitive": "gold_gain", "params": {"target": "self", "amount": 70}}},
    {"file": "expand_noble_04.json", "id": "noble_expand_secret_compact_004", "name": "Secret Compact", "category": "alliance",
     "effect": {"primitive": "alliance_bonus", "params": {"amount": 65, "players": ["self", "target"]}}},
    {"file": "expand_noble_05.json", "id": "noble_expand_blood_oath_005", "name": "Blood Oath", "category": "alliance",
     "effect": {"primitive": "alliance_bonus", "params": {"amount": 55, "players": ["self", "target"]}}},
    {"file": "expand_noble_06.json", "id": "noble_expand_sabotage_006", "name": "Sabotage", "category": "disruption",
     "effect": {"primitive": "force_discard", "params": {"target": "target", "count": 1}}},
    {"file": "expand_noble_07.json", "id": "noble_expand_poisoned_chalice_007", "name": "Poisoned Chalice", "category": "disruption",
     "effect": {"primitive": "force_discard", "params": {"target": "target", "count": 2}}},
    {"file": "expand_noble_08.json", "id": "noble_expand_spy_network_008", "name": "Spy Network", "category": "information",
     "effect": {"primitive": "reveal_hand", "params": {"target": "target"}}},
    {"file": "expand_noble_09.json", "id": "noble_expand_whisper_ring_009", "name": "Whisper Ring", "category": "information",
     "effect": {"primitive": "reveal_hand", "params": {"target": "target"}}},
    {"file": "expand_noble_10.json", "id": "noble_expand_hidden_cache_010", "name": "Hidden Cache II", "category": "protection",
     "timing": "reactive",
     "effect": {"primitive": "protect_gold", "params": {"target": "self", "amount": 85, "duration_rounds": 1,
                "specificity": "targeted", "blocks": "force_discard", "trigger": {"type": "attacked_this_phase", "target": "self"}}},
     "on_whiff_penalty": {"primitive": "gold_loss", "params": {"target": "self", "amount": 25}}},
    {"file": "expand_noble_11.json", "id": "noble_expand_body_double_011", "name": "Body Double", "category": "protection",
     "timing": "reactive",
     "effect": {"primitive": "block_succession", "params": {"scope": "next_check_this_round", "duration_rounds": 1,
                "trigger": {"type": "succession_imminent"}, "specificity": "targeted"}},
     "on_whiff_penalty": {"primitive": "gold_loss", "params": {"target": "self", "amount": 25}}},
    {"file": "expand_noble_12.json", "id": "noble_expand_night_ride_012", "name": "Night Ride", "category": "tempo",
     "effect": {"primitive": "extra_play", "params": {"target": "self", "count": 1}}},
    {"file": "expand_noble_13.json", "id": "noble_expand_courier_swap_013", "name": "Courier Swap", "category": "tempo",
     "effect": {"primitive": "draw_extra", "params": {"target": "self", "count": 2}}},
    {"file": "expand_noble_14.json", "id": "noble_expand_coup_plot_014", "name": "Coup Plot II", "category": "betrayal",
     "effect": {"primitive": "gold_transfer", "params": {"from": "king", "to": "self", "amount": 75, "as_theft": True}}},
    {"file": "expand_noble_15.json", "id": "noble_expand_grand_conspiracy_015", "name": "Grand Conspiracy", "category": "supercard",
     "rarity": "supercard", "effect": {"primitive": "gold_transfer", "params": {"from": "king", "to": "self", "amount": 120, "as_theft": True}},
     "secondary_effect": {"primitive": "draw_extra", "params": {"target": "self", "count": 1}}},
]


def _write_card(deck: str, spec: dict) -> Path:
    owner = "king" if deck == "king_deck" else "noble"
    card = {
        "id": spec["id"],
        "name": spec["name"],
        "owner_type": owner.replace("_deck", ""),
        "category": spec["category"],
        "rarity": spec.get("rarity", "common"),
        "copies_in_deck": 1,
        "timing": spec.get("timing", "on_reveal"),
        "effect": spec["effect"],
        "tags": [spec["category"]],
        "flavor_text": spec.get("flavor_text", f"Expansion design — {spec['name']}."),
        "designer_notes": "Phase 5a deck expansion for subset sweeps.",
    }
    if "secondary_effect" in spec:
        card["effect"]["secondary_effect"] = spec["secondary_effect"]
    if "on_whiff_penalty" in spec:
        card["on_whiff_penalty"] = spec["on_whiff_penalty"]
    path = ROOT / "cards" / deck / spec["file"]
    path.write_text(json.dumps(card, indent=2), encoding="utf-8")
    return path


def main() -> None:
    written = []
    for spec in KING_EXPANSION:
        written.append(_write_card("king_deck", spec))
    for spec in NOBLE_EXPANSION:
        written.append(_write_card("noble_deck", spec))
    manifest = write_manifest()
    print(f"Wrote {len(written)} expansion cards. Manifest version={manifest['version']}")


if __name__ == "__main__":
    main()
