"""Per-card balance diagnostics and scoped tuning (single card only).

Use when the deck is already signed off and you are adding or editing one card.
Global auto_tune mutates many cards; this module adjusts only the target card.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from analytics.auto_tune import _adjust_card_amounts, _load_targets, _write_card
from analytics.export_viewer_balance import _verdict
from analytics.signoff_compare import _load_gate_targets, _score
from analytics.sweeps import run_sweep
from engine.cards import CARDS_DIR, compute_card_set_version, load_all_cards, write_manifest

BASELINE_PATH = Path("game_logs/card_balance_baseline.json")
CARD_DIAG_PATH = Path("game_logs/card_diagnostics.json")


def card_content_hash(card: dict[str, Any]) -> str:
    payload = json.dumps(card, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _card_path_for_id(card_id: str) -> Path | None:
    for sub in ("king_deck", "noble_deck"):
        deck = CARDS_DIR / sub
        if not deck.exists():
            continue
        for path in deck.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if data.get("id") == card_id:
                return path
    return None


def resolve_card_id(card_id: str | None = None, card_file: str | Path | None = None) -> str:
    if card_id:
        return card_id
    if not card_file:
        raise ValueError("Provide card_id or card_file")
    path = Path(card_file)
    if not path.is_absolute():
        path = Path.cwd() / path
    data = json.loads(path.read_text(encoding="utf-8"))
    cid = data.get("id")
    if not cid:
        raise ValueError(f"No id field in {path}")
    return str(cid)


def load_baseline(path: Path = BASELINE_PATH) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_baseline(
    sweep: dict[str, Any],
    path: Path = BASELINE_PATH,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cards = load_all_cards()
    metrics = sweep.get("metrics", {})
    contrib = metrics.get("card_win_contribution", {})
    baseline = {
        "card_set_version": sweep.get("card_set_version") or compute_card_set_version(cards),
        "games": int(sweep.get("games_run") or metrics.get("total_games") or 0),
        "deck_gates": _deck_gate_summary(metrics, int(sweep.get("games_run") or metrics.get("total_games") or 0)),
        "cards": {
            c["id"]: {
                "content_hash": card_content_hash(c),
                "file": str(_card_path_for_id(c["id"]) or ""),
                "win_delta": float(contrib.get(c["id"], {}).get("delta_vs_fair", 0.0)),
                "games_with_card": int(contrib.get(c["id"], {}).get("games_with_card", 0)),
            }
            for c in cards
        },
    }
    if extra:
        baseline.update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
    return baseline


def detect_changed_card_ids(baseline: dict[str, Any] | None = None) -> list[str]:
    baseline = baseline if baseline is not None else load_baseline()
    if not baseline:
        return []
    cards = load_all_cards()
    prev = baseline.get("cards") or {}
    current_by_id = {c["id"]: c for c in cards}
    changed: list[str] = []

    for cid, card in current_by_id.items():
        h = card_content_hash(card)
        old = prev.get(cid)
        if old is None or old.get("content_hash") != h:
            changed.append(cid)

    for cid in prev:
        if cid not in current_by_id:
            changed.append(cid)

    return sorted(set(changed))


def _deck_gate_summary(metrics: dict[str, Any], games_run: int) -> dict[str, Any]:
    gates = _load_gate_targets()
    score = _score(metrics, 385, games_run)
    return {
        "gates_passed": score["gates_passed"],
        "gates_total": score["gates_total"],
        "phase_c_ready": score["phase_c_ready"],
        "started_as_king_win_rate": score["started_as_king_win_rate"],
        "shield_hit_rate": score["shield_hit_rate"],
        "assisted_win_rate": score["assisted_win_rate"],
        "seat_win_spread": score["seat_win_spread"],
        "role_win_rate_min": gates.get("role_win_rate_min", 0.35),
        "role_win_rate_max": gates.get("role_win_rate_max", 0.45),
    }


def diagnose_card(
    card_id: str,
    metrics: dict[str, Any],
    diagnostics: dict[str, Any] | None = None,
    names: dict[str, str] | None = None,
) -> dict[str, Any]:
    names = names or {c["id"]: c.get("name", c["id"]) for c in load_all_cards()}
    cards = {c["id"]: c for c in load_all_cards()}
    card = cards.get(card_id)
    if not card:
        raise KeyError(f"Unknown card id: {card_id}")

    contrib = metrics.get("card_win_contribution", {}).get(card_id, {})
    games = int(contrib.get("games_with_card", 0))
    delta = float(contrib.get("delta_vs_fair", 0.0))
    verdict = _verdict(delta, games)

    by_role = metrics.get("card_win_contribution_by_role", {}).get(card_id, {})
    pick = int(metrics.get("card_pick_counts", {}).get(card_id, 0))
    shield = (diagnostics or metrics.get("diagnostics") or {}).get("shield_by_card", {}).get(card_id, {})
    sh_hit = int(shield.get("hit", 0))
    sh_whiff = int(shield.get("whiff", 0))
    sh_block = int(shield.get("block", 0))
    sh_total = sh_hit + sh_whiff

    protection_verdict = None
    if card.get("category") == "protection" and sh_total >= 5:
        hit_rate = sh_hit / sh_total
        if hit_rate < 0.25:
            protection_verdict = "whiffs_often"
        elif hit_rate > 0.75:
            protection_verdict = "hits_often"
        else:
            protection_verdict = "in_band"

    tune_action = "none"
    tune_reason = "Card is within expected win contribution band."
    if verdict == "overperformer":
        tune_action = "nerf"
        tune_reason = f"Win rate when played is {delta:+.1%} above fair — nerf numeric knobs on this card only."
    elif verdict == "underperformer":
        tune_action = "buff"
        tune_reason = f"Win rate when played is {delta:+.1%} below fair — buff numeric knobs on this card only."
    elif verdict == "too_few_games":
        tune_action = "none"
        tune_reason = "Not enough games where this card was played — increase sweep games or play more bots."

    if protection_verdict == "whiffs_often" and tune_action == "none":
        tune_action = "reduce_whiff"
        tune_reason = "Protection card whiffs often — reduce on_whiff_penalty on this card only."
    elif protection_verdict == "hits_often" and tune_action == "none":
        tune_action = "increase_whiff"
        tune_reason = "Protection card hits very often — slightly increase whiff penalty on this card only."

    return {
        "card_id": card_id,
        "name": names.get(card_id, card_id),
        "category": card.get("category"),
        "owner_type": card.get("owner_type"),
        "times_played": pick,
        "games_with_card": games,
        "wins_when_played": int(contrib.get("wins_when_played", 0)),
        "win_rate_when_played": float(contrib.get("win_rate_when_played", 0.0)),
        "delta_vs_fair": delta,
        "verdict": verdict,
        "by_role": by_role,
        "shield": {
            "hit": sh_hit,
            "whiff": sh_whiff,
            "block": sh_block,
            "hit_rate": sh_hit / sh_total if sh_total else None,
            "protection_verdict": protection_verdict,
        },
        "tune_action": tune_action,
        "tune_reason": tune_reason,
        "deck_gates": _deck_gate_summary(metrics, int(metrics.get("total_games", 0))),
    }


def _tune_factor_for_action(action: str, step: float) -> float | None:
    if action == "nerf":
        return 1.0 - step
    if action == "buff":
        return 1.0 + step
    return None


def tune_single_card(
    card_id: str,
    diagnosis: dict[str, Any],
    targets: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    targets = targets or _load_targets()
    step = float(targets.get("tune_step_pct", 0.10))
    action = diagnosis.get("tune_action", "none")
    cards = {c["id"]: dict(c) for c in load_all_cards()}
    card = cards.get(card_id)
    if not card:
        raise KeyError(card_id)

    applied: list[str] = []
    if action in ("nerf", "buff"):
        factor = _tune_factor_for_action(action, step)
        assert factor is not None
        cats = {
            "economy",
            "betrayal",
            "disruption",
            "tempo",
            "alliance",
            "protection",
            "information",
            "supercard",
        }
        applied = _adjust_card_amounts(card, factor, cats)
    elif action == "reduce_whiff":
        whiff = card.get("on_whiff_penalty") or {}
        params = whiff.get("params") or {}
        if "amount" in params:
            old = int(params["amount"])
            new_val = max(5, int(old * 0.9))
            if new_val != old:
                params["amount"] = new_val
                applied.append(f"{card_id}: on_whiff_penalty.amount {old} -> {new_val}")
    elif action == "increase_whiff":
        whiff = card.get("on_whiff_penalty") or {}
        params = whiff.get("params") or {}
        if "amount" in params:
            old = int(params["amount"])
            new_val = int(old * 1.1)
            if new_val != old:
                params["amount"] = new_val
                applied.append(f"{card_id}: on_whiff_penalty.amount {old} -> {new_val}")

    if applied and not dry_run:
        _write_card(card)
        write_manifest()

    return {
        "card_id": card_id,
        "tune_action": action,
        "changes_applied": applied,
        "dry_run": dry_run,
        "card_set_version": compute_card_set_version() if not dry_run else None,
    }


def run_card_sweep(
    card_id: str,
    games: int = 385,
    seed: int = 0,
    config_path: str = "configs/balance.yaml",
) -> dict[str, Any]:
    sweep = run_sweep(config_path, games=games, seed=seed)
    metrics = sweep["metrics"]
    diag = diagnose_card(card_id, metrics)
    out = {
        "card_id": card_id,
        "card_set_version": sweep.get("card_set_version"),
        "games_run": sweep.get("games_run"),
        "diagnosis": diag,
        "deck_gates": diag["deck_gates"],
    }
    CARD_DIAG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CARD_DIAG_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    (Path("game_logs") / "sweep_result.json").write_text(json.dumps(sweep, indent=2), encoding="utf-8")
    diag_embed = metrics.get("diagnostics")
    if diag_embed:
        (Path("game_logs") / "diagnostics.json").write_text(json.dumps(diag_embed, indent=2), encoding="utf-8")
    return out


def run_card_tune_loop(
    card_id: str,
    games: int = 385,
    seed: int = 0,
    max_passes: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    targets = _load_targets()
    max_passes = max_passes or int(targets.get("max_tune_passes", 5))
    passes: list[dict[str, Any]] = []

    for pass_num in range(1, max_passes + 1):
        sweep_out = run_card_sweep(card_id, games=games, seed=seed + pass_num * 1000)
        diagnosis = sweep_out["diagnosis"]
        if diagnosis["verdict"] == "balanced" and diagnosis["tune_action"] == "none":
            break
        tune_out = tune_single_card(card_id, diagnosis, targets, dry_run=dry_run)
        passes.append({"pass": pass_num, "diagnosis": diagnosis, "tune": tune_out})
        if not tune_out.get("changes_applied"):
            break

    final = run_card_sweep(card_id, games=games, seed=seed + (len(passes) + 1) * 1000)
    result = {
        "card_id": card_id,
        "passes": passes,
        "final_diagnosis": final["diagnosis"],
        "final_deck_gates": final["deck_gates"],
    }
    out_path = Path("game_logs") / "card_tune_result.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Per-card balance diagnostics and scoped tuning")
    parser.add_argument("--card-id", help="Card id to diagnose/tune")
    parser.add_argument("--card-file", help="Path to card JSON (uses its id field)")
    parser.add_argument("--games", type=int, default=385)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--tune", action="store_true", help="Adjust only this card's numeric knobs")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--save-baseline", action="store_true", help="Snapshot current deck for change detection")
    parser.add_argument("--detect-changed", action="store_true", help="Print card ids changed since baseline")
    parser.add_argument("--max-passes", type=int, default=None)
    args = parser.parse_args()

    if args.save_baseline:
        sweep = run_sweep("configs/balance.yaml", games=args.games, seed=args.seed)
        baseline = save_baseline(sweep)
        print(json.dumps({"saved": str(BASELINE_PATH), "card_set_version": baseline["card_set_version"]}, indent=2))
        if not args.card_id and not args.card_file and not args.detect_changed and not args.tune:
            return

    if args.detect_changed:
        changed = detect_changed_card_ids()
        print(json.dumps({"changed_card_ids": changed}, indent=2))
        if not args.card_id and not args.card_file and not args.tune:
            return

    card_id = None
    if args.card_id or args.card_file:
        card_id = resolve_card_id(args.card_id, args.card_file)
    else:
        changed = detect_changed_card_ids()
        if len(changed) == 1:
            card_id = changed[0]
            print(f"Auto-detected changed card: {card_id}")
        elif not changed:
            raise SystemExit("No changed cards vs baseline — pass --card-id or run --save-baseline after signoff")
        else:
            raise SystemExit(f"Multiple changed cards {changed} — pass --card-id explicitly")

    if args.tune:
        result = run_card_tune_loop(
            card_id,
            games=args.games,
            seed=args.seed,
            max_passes=args.max_passes,
            dry_run=args.dry_run,
        )
        print(json.dumps(result["final_diagnosis"], indent=2))
        print(json.dumps(result["final_deck_gates"], indent=2))
        return

    out = run_card_sweep(card_id, games=args.games, seed=args.seed)
    print(json.dumps(out["diagnosis"], indent=2))


if __name__ == "__main__":
    main()
