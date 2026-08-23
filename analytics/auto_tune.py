"""Apply numeric card tuning from sweep + kingmaker results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from analytics.kingmaker_test import run_kingmaker_scenario
from analytics.sweeps import run_sweep
from engine.cards import CARDS_DIR, compute_card_set_version, load_all_cards, write_manifest

LOCKED_RULE_KEYS = (
    "king_start_gold",
    "noble_start_gold",
    "king_plays_per_round",
    "king_redraw",
)
BALANCE_CONFIG_PATH = Path("configs/balance.yaml")


def _load_targets(path: str = "configs/balance_targets.yaml") -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {
            "assisted_win_rate_max": 0.12,
            "shield_hit_rate_min": 0.25,
            "shield_hit_rate_max": 0.70,
            "role_win_rate_min": 0.35,
            "role_win_rate_max": 0.45,
            "tune_step_pct": 0.10,
            "max_tune_passes": 5,
        }
    with p.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _enforce_locked_rules(config: dict[str, Any], targets: dict[str, Any]) -> list[str]:
    """Restore immutable core rules if something tried to change them."""
    locked = targets.get("locked_rules") or {}
    restored: list[str] = []
    for key in LOCKED_RULE_KEYS:
        expected = locked.get(key)
        if expected is None:
            continue
        if config.get(key) != expected:
            old = config.get(key)
            config[key] = expected
            restored.append(f"{key} {old} -> {expected} (locked rule restored)")
    return restored


def _write_balance_config(updates: dict[str, Any], targets: dict[str, Any]) -> list[str]:
    applied: list[str] = []
    if not BALANCE_CONFIG_PATH.exists():
        return applied
    bal = yaml.safe_load(BALANCE_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    for key, val in updates.items():
        if key in LOCKED_RULE_KEYS:
            continue
        if bal.get(key) != val:
            applied.append(f"configs/balance.yaml: {key} {bal.get(key)} -> {val}")
            bal[key] = val
    applied.extend(_enforce_locked_rules(bal, targets))
    BALANCE_CONFIG_PATH.write_text(yaml.safe_dump(bal, sort_keys=False), encoding="utf-8")
    return applied


def _iter_amount_fields(obj: Any, path: str = "") -> list[tuple[str, dict, str, int]]:
    """Find numeric amount fields in card effect trees."""
    found: list[tuple[str, dict, str, int]] = []
    if isinstance(obj, dict):
        if "amount" in obj and isinstance(obj["amount"], (int, float)):
            found.append((path, obj, "amount", int(obj["amount"])))
        for key, val in obj.items():
            found.extend(_iter_amount_fields(val, f"{path}.{key}" if path else key))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            found.extend(_iter_amount_fields(item, f"{path}[{i}]"))
    return found


def _adjust_owner_cards(
    card_map: dict[str, dict],
    owner_type: str,
    categories: set[str],
    factor: float,
) -> list[str]:
    applied: list[str] = []
    for cid, card in card_map.items():
        if card.get("owner_type") != owner_type:
            continue
        cat = card.get("category")
        eff = json.dumps(card.get("effect", {}))
        if cat not in categories and not (owner_type == "noble" and "as_theft" in eff):
            continue
        applied.extend(_adjust_card_amounts(card, factor, categories | {"betrayal", "economy", "disruption", "tempo"}))
    return applied


def _tune_role_balance(
    sweep: dict,
    card_map: dict[str, dict],
    targets: dict[str, Any],
    dry_run: bool,
) -> tuple[list[str], list[str]]:
    """Reduce King dominance via cards and action economy — never start gold."""
    recommendations: list[str] = []
    applied: list[str] = []
    role = sweep.get("metrics", {}).get("role_win_rate", {})
    king_wr = float(role.get("started_as_king", 0.0))
    role_min = float(targets.get("role_win_rate_min", 0.35))
    role_max = float(targets.get("role_win_rate_max", 0.45))
    step = float(targets.get("tune_step_pct", 0.10))

    if king_wr <= role_max and king_wr >= role_min:
        return recommendations, applied

    if king_wr > role_max:
        king_factor = 1.0 - step
        noble_factor = 1.0 + step
        recommendations.append(
            f"Started-as-King win rate {king_wr:.2%} above max {role_max:.2%}; "
            f"nerfing King cards and buffing Noble catch-up by {int(step * 100)}%."
        )
        applied.extend(_adjust_owner_cards(card_map, "king", {"economy", "disruption", "tempo", "alliance"}, king_factor))
        applied.extend(_adjust_owner_cards(card_map, "noble", {"betrayal", "economy", "disruption"}, noble_factor))
        cfg = sweep.get("config") or {}
        gift_cap = int(cfg.get("max_negotiation_gift", 180))
        if gift_cap > 50 and not dry_run:
            applied.extend(
                _write_balance_config(
                    {"max_negotiation_gift": max(50, int(gift_cap * king_factor))},
                    targets,
                )
            )
    elif king_wr < role_min:
        king_factor = 1.0 + step * 0.5
        noble_factor = 1.0 - step * 0.5
        recommendations.append(
            f"Started-as-King win rate {king_wr:.2%} below min {role_min:.2%}; "
            "slightly buffing King cards (starting gold remains locked)."
        )
        applied.extend(_adjust_owner_cards(card_map, "king", {"economy", "disruption", "tempo", "alliance"}, king_factor))
        applied.extend(_adjust_owner_cards(card_map, "noble", {"betrayal", "economy", "disruption"}, noble_factor))

    return recommendations, applied


def _adjust_card_amounts(card: dict, factor: float, categories: set[str]) -> list[str]:
    changes: list[str] = []
    if card.get("category") not in categories and "gold_transfer" not in json.dumps(card.get("effect", {})):
        return changes
    for path, holder, key, old in _iter_amount_fields(card.get("effect")):
        if "gold" not in path and holder.get("target") is None and "amount" in holder:
            pass
        new_val = max(10, int(old * factor))
        if new_val != old:
            holder[key] = new_val
            changes.append(f"{card['id']}: {path}.{key} {old} -> {new_val}")
    whiff = card.get("on_whiff_penalty")
    if whiff and card.get("category") == "protection":
        params = whiff.get("params") or {}
        if "amount" in params:
            old = int(params["amount"])
            new_val = max(5, int(old * (2 - factor)))  # inverse: reduce theft -> reduce whiff slightly
            if new_val != old:
                params["amount"] = new_val
                changes.append(f"{card['id']}: on_whiff_penalty.amount {old} -> {new_val}")
    return changes


def _write_card(card: dict) -> None:
    owner = card.get("owner_type", "noble")
    deck = CARDS_DIR / ("king_deck" if owner == "king" else "noble_deck")
    cid = card["id"]
    path = deck / f"{cid}.json"
    if not path.exists():
        for p in deck.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if data.get("id") == cid:
                path = p
                break
        else:
            slug = cid.replace("_001", "").split("_", 1)[-1]
            path = deck / f"{slug}.json"
    path.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")


def tune_from_metrics(
    sweep: dict,
    kingmaker: dict,
    targets: dict | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    targets = targets or _load_targets()
    metrics = sweep.get("metrics", {})
    assisted = metrics.get("assisted_win_rate", 0.0)
    shield_hit = metrics.get("shield_hit_rate", 0.0)
    whiff = metrics.get("whiff_penalty_rate", 0.0)
    km_on = kingmaker.get("earned_gold_ledger", {})
    km_off = kingmaker.get("gold_only", {})

    recommendations: list[str] = []
    applied: list[str] = []
    cards = load_all_cards()
    card_map = {c["id"]: dict(c) for c in cards}

    assisted_max = float(targets.get("assisted_win_rate_max", 0.12))
    if assisted > assisted_max:
        factor = 1.0 - float(targets.get("tune_step_pct", 0.10))
        recommendations.append(
            f"Assisted win rate {assisted:.2%} exceeds max {assisted_max:.2%}; "
            f"reducing betrayal/theft gold amounts by {int((1-factor)*100)}%."
        )
        gift_cap = int(sweep.get("config", {}).get("max_negotiation_gift", 200))
        new_cap = max(50, int(gift_cap * factor))
        if new_cap != gift_cap and not dry_run:
            applied.extend(_write_balance_config({"max_negotiation_gift": new_cap}, targets))
            recommendations.append(
                f"Negotiation gift cap lowered {gift_cap} -> {new_cap} to reduce kingmaking gifts."
            )
        for cid, card in card_map.items():
            if card.get("category") in ("betrayal", "economy", "disruption"):
                eff = json.dumps(card.get("effect", {}))
                if card.get("owner_type") == "king" and ("as_theft" in eff or card.get("category") == "betrayal"):
                    applied.extend(_adjust_card_amounts(card, factor, {"betrayal", "economy", "disruption"}))

    shield_min = float(targets.get("shield_hit_rate_min", 0.25))
    shield_max = float(targets.get("shield_hit_rate_max", 0.70))
    if shield_hit < shield_min:
        recommendations.append(
            f"Shield hit rate {shield_hit:.2%} below min {shield_min:.2%}; "
            "reducing protection whiff penalties slightly."
        )
        for cid, card in card_map.items():
            if card.get("category") == "protection":
                whiff_block = card.get("on_whiff_penalty") or {}
                params = whiff_block.get("params") or {}
                if "amount" in params:
                    old = int(params["amount"])
                    new_val = max(5, int(old * 0.9))
                    if new_val != old:
                        params["amount"] = new_val
                        applied.append(f"{cid}: on_whiff_penalty.amount {old} -> {new_val}")
    elif shield_hit > shield_max:
        recommendations.append(
            f"Shield hit rate {shield_hit:.2%} above max {shield_max:.2%}; "
            "increasing protection whiff penalties slightly."
        )
        for cid, card in card_map.items():
            if card.get("category") == "protection":
                whiff_block = card.get("on_whiff_penalty") or {}
                params = whiff_block.get("params") or {}
                if "amount" in params:
                    old = int(params["amount"])
                    new_val = int(old * 1.1)
                    params["amount"] = new_val
                    applied.append(f"{cid}: on_whiff_penalty.amount {old} -> {new_val}")

    if whiff > float(targets.get("whiff_penalty_rate_max", 0.75)):
        recommendations.append(f"Whiff rate {whiff:.2%} high — protection cards may be too narrow.")

    if not km_on.get("gift_recipient_ascension_rate", 1) < km_off.get("gift_recipient_ascension_rate", 0):
        recommendations.append(
            "Kingmaker fix did not reduce gift-driven ascension — check succession_checker config."
        )

    role_recs, role_applied = _tune_role_balance(sweep, card_map, targets, dry_run)
    recommendations.extend(role_recs)
    applied.extend(role_applied)

    if applied and not dry_run:
        for card in card_map.values():
            _write_card(card)
        write_manifest()

    return {
        "assisted_win_rate": assisted,
        "shield_hit_rate": shield_hit,
        "whiff_penalty_rate": whiff,
        "role_win_rate": metrics.get("role_win_rate", {}),
        "kingmaker": kingmaker,
        "recommendations": recommendations,
        "changes_applied": applied,
        "card_set_version": compute_card_set_version(list(card_map.values())),
        "dry_run": dry_run,
    }


def run_balance_pipeline(
    games: int = 80,
    kingmaker_games: int = 200,
    seed: int = 0,
    tune: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    targets = _load_targets()
    if BALANCE_CONFIG_PATH.exists():
        bal = yaml.safe_load(BALANCE_CONFIG_PATH.read_text(encoding="utf-8")) or {}
        assert not bal.get("reward_shaping", False), "reward_shaping must be false in balance pipeline"
        restored = _enforce_locked_rules(bal, targets)
        if restored:
            BALANCE_CONFIG_PATH.write_text(yaml.safe_dump(bal, sort_keys=False), encoding="utf-8")
    passes: list[dict] = []
    sweep = run_sweep("configs/balance.yaml", games=games, seed=seed)
    kingmaker = {
        "gold_only": run_kingmaker_scenario(kingmaker_games, seed, ledger=False),
        "earned_gold_ledger": run_kingmaker_scenario(kingmaker_games, seed + 10000, ledger=True),
    }
    kingmaker["fix_reduces_assisted_wins"] = (
        kingmaker["earned_gold_ledger"]["assisted_win_rate"]
        < kingmaker["gold_only"]["assisted_win_rate"]
    )

    tune_result = tune_from_metrics(sweep, kingmaker, targets, dry_run=dry_run) if tune else {}
    passes.append({"sweep": sweep, "kingmaker": kingmaker, "tune": tune_result})

    max_passes = int(targets.get("max_tune_passes", 3)) if tune else 1
    pass_num = 1
    role = sweep.get("metrics", {}).get("role_win_rate", {})
    king_wr = float(role.get("started_as_king", 0.0))
    role_min = float(targets.get("role_win_rate_min", 0.35))
    role_max = float(targets.get("role_win_rate_max", 0.45))
    role_out_of_band = king_wr < role_min or king_wr > role_max
    while tune and pass_num < max_passes and (tune_result.get("changes_applied") or role_out_of_band):
        pass_num += 1
        sweep = run_sweep("configs/balance.yaml", games=games, seed=seed + pass_num * 1000)
        tune_result = tune_from_metrics(sweep, kingmaker, targets, dry_run=dry_run)
        passes.append({"sweep": sweep, "tune": tune_result})
        role = sweep.get("metrics", {}).get("role_win_rate", {})
        king_wr = float(role.get("started_as_king", 0.0))
        role_out_of_band = king_wr < role_min or king_wr > role_max

    out = {
        "passes": len(passes),
        "final_sweep": passes[-1]["sweep"],
        "kingmaker": kingmaker,
        "final_tune": passes[-1].get("tune", {}),
        "targets": targets,
    }
    root = Path("game_logs")
    root.mkdir(parents=True, exist_ok=True)
    (root / "sweep_result.json").write_text(json.dumps(passes[-1]["sweep"], indent=2), encoding="utf-8")
    (root / "kingmaker_ab.json").write_text(json.dumps(kingmaker, indent=2), encoding="utf-8")
    (root / "tune_result.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    from analytics.export_viewer_balance import export_viewer_balance
    from analytics.log_store import log_sweep_run

    log_sweep_run(out["final_sweep"], bot_mode=out["final_sweep"].get("bot_mode", "league_heuristic"))
    export_viewer_balance()
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Run sweep, kingmaker test, and auto-tune")
    parser.add_argument("--games", type=int, default=80)
    parser.add_argument("--kingmaker-games", type=int, default=200)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-tune", action="store_true")
    args = parser.parse_args()
    result = run_balance_pipeline(
        games=args.games,
        kingmaker_games=args.kingmaker_games,
        seed=args.seed,
        tune=not args.no_tune,
        dry_run=args.dry_run,
    )
    m = result["final_sweep"]["metrics"]
    print(f"Pass {result['passes']}: assisted={m['assisted_win_rate']:.2%}, shield_hit={m['shield_hit_rate']:.2%}")
    print(f"Kingmaker fix works: {result['kingmaker']['fix_reduces_assisted_wins']}")
    changes = result["final_tune"].get("changes_applied", [])
    if changes:
        print(f"Applied {len(changes)} tuning changes (see game_logs/tune_result.json)")

    from analytics.export_viewer_balance import export_viewer_balance

    export_viewer_balance()


if __name__ == "__main__":
    main()
