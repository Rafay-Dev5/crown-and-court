"""Targeted shield balance pass — fix protection play heuristics and card triggers.

Run after deck resize or when 385-game signoff shows shield_hit_rate below 25%.
Does not mutate start gold or core play/redraw counts.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Miscategorized stub fillers (legacy — stubs now real cards; kept empty).
STUB_ECONOMY_IDS: set[str] = set()


def _recategorize_stub_protection() -> list[str]:
    from engine.cards import load_all_cards, write_manifest

    changes: list[str] = []
    for card in load_all_cards():
        if card["id"] not in STUB_ECONOMY_IDS:
            continue
        if card.get("category") == "economy":
            continue
        owner = card.get("owner_type", "noble")
        deck = ROOT / "cards" / ("king_deck" if owner == "king" else "noble_deck")
        slug = card["id"].replace("_001", "").split("_", 1)[-1]
        for path in deck.glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("id") != card["id"]:
                continue
            data["category"] = "economy"
            tags = list(data.get("tags") or [])
            if "protection" in tags:
                tags = [t for t in tags if t != "protection"] + ["economy"]
            data["tags"] = tags
            path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            changes.append(f"{card['id']}: category protection -> economy")
            break
    if changes:
        write_manifest()
    return changes


def _run_signoff() -> dict:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "analytics.signoff_compare",
            "--games-standard",
            "100",
            "--games-prd",
            "385",
            "--no-tune",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode not in (0, 1):
        print(proc.stderr or proc.stdout, file=sys.stderr)
        proc.check_returncode()
    path = ROOT / "game_logs" / "signoff_comparison.json"
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    card_changes = _recategorize_stub_protection()
    print("Card fixes:", card_changes or ["none needed"])
    print("Bot fixes: smarter protection play in agents/heuristic/bots.py (already applied).")
    print("Running 385-game signoff...")
    result = _run_signoff()
    prd = result["prd_sample_run"]["score"]
    shield = prd["shield_hit_rate"]
    print(
        json.dumps(
            {
                "card_set_version": result["prd_sample_run"]["card_set_version"],
                "shield_hit_rate": shield,
                "shield_in_prd_band": prd["shield_in_prd_band"],
                "gates_passed": prd["gates_passed"],
                "phase_c_ready": prd["phase_c_ready"],
                "role_win_rate": result["prd_sample_run"]["metrics"]["role_win_rate"],
                "assisted_win_rate": prd["assisted_win_rate"],
                "seat_win_spread": prd["seat_win_spread"],
            },
            indent=2,
        )
    )
    if not prd["shield_in_prd_band"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
