"""Post card-edit workflow: manifest, validate, tests, balance signoff, viewer export.

Run after adding, editing, or deleting a card JSON file.

Examples:
  python scripts/card_workflow.py              # validate + tests + 385-game signoff
  python scripts/card_workflow.py --quick      # manifest + validate + tests only
  python scripts/card_workflow.py --card-id king_royal_edict_25_025 --tune
  python scripts/card_workflow.py --save-baseline   # snapshot deck after signoff passes
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class StepResult:
    name: str
    ok: bool
    seconds: float
    detail: str = ""
    data: dict[str, Any] = field(default_factory=dict)


def _banner(title: str) -> None:
    print(f"\n=== {title} ===")


def step_manifest() -> StepResult:
    _banner("Manifest")
    t0 = time.perf_counter()
    from engine.cards import write_manifest

    manifest = write_manifest()
    detail = f"version={manifest['version']} cards={manifest['card_count']}"
    print(detail)
    return StepResult("manifest", True, time.perf_counter() - t0, detail, manifest)


def step_validate() -> StepResult:
    _banner("Validate")
    t0 = time.perf_counter()
    from engine.validate import validate_all

    count, errors = validate_all()
    if errors:
        print(f"FAILED ({count} error(s)):")
        for err in errors[:20]:
            print(f"  - {err}")
        if count > 20:
            print(f"  ... and {count - 20} more")
        return StepResult("validate", False, time.perf_counter() - t0, f"{count} errors", {"errors": errors})

    print("All cards valid.")
    return StepResult("validate", True, time.perf_counter() - t0)


def step_tests() -> StepResult:
    _banner("Tests")
    t0 = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    tail = (proc.stdout or proc.stderr or "").strip().splitlines()
    summary = tail[-1] if tail else f"exit {proc.returncode}"
    print(summary)
    if proc.returncode != 0 and proc.stdout:
        print(proc.stdout[-2000:])
    return StepResult("tests", proc.returncode == 0, time.perf_counter() - t0, summary)


def step_signoff(games_standard: int, games_prd: int, seed: int) -> StepResult:
    _banner(f"Signoff ({games_standard} + {games_prd} games, --no-tune)")
    t0 = time.perf_counter()
    from analytics.signoff_compare import compare_signoff

    result = compare_signoff(
        games_standard=games_standard,
        games_prd=games_prd,
        seed=seed,
        tune_standard=False,
    )
    prd = result["prd_sample_run"]
    score = prd["score"]
    summary = {
        "card_set_version": prd["card_set_version"],
        "gates_passed": score["gates_passed"],
        "gates_total": score["gates_total"],
        "phase_c_ready": score["phase_c_ready"],
        "started_as_king_win_rate": score["started_as_king_win_rate"],
        "shield_hit_rate": score["shield_hit_rate"],
        "assisted_win_rate": score["assisted_win_rate"],
        "seat_win_spread": score["seat_win_spread"],
    }
    print(json.dumps(summary, indent=2))
    ok = bool(score["phase_c_ready"])
    if not ok:
        print("Sign-off gates FAILED — see game_logs/signoff_comparison.json")
    else:
        print("Sign-off gates PASSED (phase_c_ready).")
    return StepResult(
        "signoff",
        ok,
        time.perf_counter() - t0,
        f"{score['gates_passed']}/{score['gates_total']} gates",
        summary,
    )


def step_save_baseline(games: int, seed: int) -> StepResult:
    _banner("Save card balance baseline")
    t0 = time.perf_counter()
    from analytics.card_balance import save_baseline
    from analytics.sweeps import run_sweep

    sweep_path = ROOT / "game_logs" / "sweep_result.json"
    if sweep_path.exists():
        sweep = json.loads(sweep_path.read_text(encoding="utf-8"))
    else:
        sweep = run_sweep("configs/balance.yaml", games=games, seed=seed)
    baseline = save_baseline(sweep)
    detail = f"baseline {baseline['card_set_version']} ({len(baseline['cards'])} cards)"
    print(detail)
    return StepResult("save_baseline", True, time.perf_counter() - t0, detail, baseline)


def step_card_diagnostics(card_id: str, games: int, seed: int) -> StepResult:
    _banner(f"Card diagnostics ({card_id})")
    t0 = time.perf_counter()
    from analytics.card_balance import run_card_sweep

    out = run_card_sweep(card_id, games=games, seed=seed)
    diag = out["diagnosis"]
    print(json.dumps(diag, indent=2))
    print(f"Wrote game_logs/card_diagnostics.json")
    return StepResult(
        "card_diagnostics",
        True,
        time.perf_counter() - t0,
        f"{diag['verdict']} delta={diag['delta_vs_fair']:+.1%}",
        diag,
    )


def step_card_tune(card_id: str, games: int, seed: int, max_passes: int | None) -> StepResult:
    _banner(f"Scoped card tune ({card_id} only)")
    t0 = time.perf_counter()
    from analytics.card_balance import run_card_tune_loop

    result = run_card_tune_loop(card_id, games=games, seed=seed, max_passes=max_passes, dry_run=False)
    diag = result["final_diagnosis"]
    changes = sum(len(p["tune"].get("changes_applied", [])) for p in result["passes"])
    detail = f"{changes} change(s) on {card_id}; verdict={diag['verdict']}"
    print(detail)
    print(json.dumps(diag, indent=2))
    print("Deck gates after tune:", json.dumps(result["final_deck_gates"], indent=2))
    return StepResult(
        "card_tune",
        True,
        time.perf_counter() - t0,
        detail,
        result,
    )


def step_export_balance() -> StepResult:
    _banner("Export viewer balance")
    t0 = time.perf_counter()
    from analytics.export_viewer_balance import export_viewer_balance

    out = export_viewer_balance()
    path = ROOT / "viewer" / "public" / "balance" / "summary.json"
    detail = f"wrote {path.relative_to(ROOT)}"
    print(detail)
    return StepResult("export_balance", True, time.perf_counter() - t0, detail, out)


def step_diagnostics(card_id: str | None = None) -> StepResult:
    if card_id:
        path = ROOT / "game_logs" / "card_diagnostics.json"
        if not path.exists():
            return StepResult("diagnostics", True, 0.0, "no card_diagnostics.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        _banner(f"Card diagnostics file ({card_id})")
        print(json.dumps(data.get("diagnosis", data), indent=2))
        return StepResult("diagnostics", True, 0.0, "card scope", data)

    _banner("Deck diagnostics summary")
    t0 = time.perf_counter()
    path = ROOT / "game_logs" / "diagnostics.json"
    if not path.exists():
        return StepResult("diagnostics", True, time.perf_counter() - t0, "no diagnostics.json (run signoff first)")

    data = json.loads(path.read_text(encoding="utf-8"))
    keys = (
        "assisted_win_rate",
        "protection_hit_rate",
        "shield_block_rate",
        "assisted_win_modes",
    )
    summary = {k: data[k] for k in keys if k in data}
    print(json.dumps(summary, indent=2))
    return StepResult("diagnostics", True, time.perf_counter() - t0, "deck scope", summary)


def _resolve_target_card(card_id: str | None, card_file: str | None) -> str | None:
    from analytics.card_balance import detect_changed_card_ids, resolve_card_id

    if card_id or card_file:
        return resolve_card_id(card_id, card_file)
    changed = detect_changed_card_ids()
    if len(changed) == 1:
        print(f"Auto-detected changed card: {changed[0]}")
        return changed[0]
    if len(changed) > 1:
        print(f"Multiple changed cards vs baseline: {changed}")
        print("Pass --card-id or --card-file to scope diagnostics/tuning.")
    return None


def _print_report(results: list[StepResult]) -> int:
    _banner("Summary")
    failed = [r for r in results if not r.ok]
    total = sum(r.seconds for r in results)
    for r in results:
        mark = "OK" if r.ok else "FAIL"
        print(f"  [{mark}] {r.name:20} {r.seconds:6.1f}s  {r.detail}")
    print(f"\nTotal: {total:.1f}s")
    if failed:
        print(f"\nFailed steps: {', '.join(r.name for r in failed)}")
        return 1
    print("\nAll steps passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run manifest, validation, tests, and balance checks after card edits.",
    )
    parser.add_argument("--quick", action="store_true", help="Manifest + validate + tests only.")
    parser.add_argument(
        "--tune",
        action="store_true",
        help="Scoped tune: adjust numeric knobs on one card only (not global auto_tune).",
    )
    parser.add_argument("--card-id", help="Card id for isolated diagnostics/tuning.")
    parser.add_argument("--card-file", help="Path to edited card JSON.")
    parser.add_argument(
        "--save-baseline",
        action="store_true",
        help="Save per-card hashes after signoff passes (enables auto-detect).",
    )
    parser.add_argument(
        "--global-tune",
        action="store_true",
        help="Legacy: run global auto_tune (mutates many cards). Prefer --tune.",
    )
    parser.add_argument("--games-standard", type=int, default=100)
    parser.add_argument("--games-prd", type=int, default=385)
    parser.add_argument("--games", type=int, default=None, help="Card diagnostic sweep size (default: games-prd).")
    parser.add_argument("--max-passes", type=int, default=None, help="Max scoped tune passes.")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    card_games = args.games if args.games is not None else args.games_prd
    target_card = _resolve_target_card(args.card_id, args.card_file)

    results: list[StepResult] = []

    results.append(step_manifest())
    if not results[-1].ok:
        return _print_report(results)

    results.append(step_validate())
    if not results[-1].ok:
        return _print_report(results)

    results.append(step_tests())
    if not results[-1].ok:
        return _print_report(results)

    if args.quick:
        return _print_report(results)

    if target_card:
        results.append(step_card_diagnostics(target_card, card_games, args.seed))

    results.append(step_signoff(args.games_standard, args.games_prd, args.seed))
    signoff_ok = results[-1].ok

    if args.save_baseline or signoff_ok:
        results.append(step_save_baseline(args.games_prd, args.seed))

    if args.tune and target_card:
        results.append(step_card_tune(target_card, card_games, args.seed, args.max_passes))
        results.append(step_signoff(args.games_standard, args.games_prd, args.seed + 90000))
    elif args.tune and not target_card:
        print("\n=== Scoped tune skipped ===")
        print("Pass --card-id/--card-file or save a baseline and edit one card for auto-detect.")
    elif args.global_tune:
        _banner("WARNING: global auto_tune mutates many cards")
        from analytics.auto_tune import run_balance_pipeline

        run_balance_pipeline(games=card_games, seed=args.seed, tune=True)
        results.append(step_signoff(args.games_standard, args.games_prd, args.seed))

    results.append(step_export_balance())
    results.append(step_diagnostics(target_card))

    return _print_report(results)


if __name__ == "__main__":
    raise SystemExit(main())
