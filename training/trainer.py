from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from engine.cards import compute_card_set_version, load_all_cards, load_config
from engine.rng import GameRNG
from training.benchmark import run_benchmarks, write_benchmark_report
from training.checkpoints import CheckpointManager
from training.episode_runner import run_shared_episode
from training.league import LeaguePool
from training.live_metrics import LiveMetricsWriter
from training.parallel_rollout import collect_rollouts
from training.policy_factory import build_policy, load_policy


def moving_average(values: list[float], window: int) -> float:
    if not values:
        return 0.0
    tail = values[-window:]
    return sum(tail) / len(tail)


def _series_from_history(
    history: list[dict], value_key: str, window: int = 20, max_points: int = 300
) -> list[list[float]]:
    """Build [[episode, ma_value], ...] from persisted episode records."""
    if not history:
        return []
    values: list[float] = []
    points: list[list[float]] = []
    for rec in history:
        if value_key == "won":
            values.append(1.0 if rec.get("won") else 0.0)
        else:
            values.append(float(rec.get(value_key, 0) or 0))
        tail = values[-window:]
        points.append([float(rec["episode"]), sum(tail) / len(tail)])
    if len(points) <= max_points:
        return points
    step = max(1, len(points) // max_points)
    return points[::step]


def _hydrate_from_disk(out: Path, start_ep: int, benchmark_interval: int = 0) -> dict:
    """Reload rolling metrics and charts when resuming a crashed run."""
    raw_records: list[dict] = []
    hist_path = out / "history.jsonl"
    if hist_path.exists():
        for line in hist_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if int(rec.get("episode", 0)) < start_ep:
                raw_records.append(rec)

    # Mixed runs can append the same episode twice — keep the latest row.
    by_ep: dict[int, dict] = {}
    for rec in raw_records:
        by_ep[int(rec["episode"])] = rec
    records = [by_ep[k] for k in sorted(by_ep)][-200:]

    wins: list[float] = []
    losses: list[float] = []
    assisted: list[float] = []
    seat_wins: dict[int, list[float]] = {}
    for rec in records:
        wins.append(1.0 if rec.get("won") else 0.0)
        losses.append(float(rec.get("loss", 0) or 0))
        assisted.append(1.0 if rec.get("assisted_win") else 0.0)
        seat = int(rec.get("train_seat", 0))
        seat_wins.setdefault(seat, []).append(1.0 if rec.get("won") else 0.0)

    bench_hist: list[dict] = []
    bench_hist_path = out / "benchmark_history.json"
    if bench_hist_path.exists():
        bench_hist = json.loads(bench_hist_path.read_text(encoding="utf-8"))

    last_benchmark = None
    bench_path = out / "benchmark.json"
    if bench_path.exists():
        last_benchmark = json.loads(bench_path.read_text(encoding="utf-8"))

    if not bench_hist and last_benchmark and start_ep > 0 and benchmark_interval > 0:
        bench_ep = start_ep - (start_ep % benchmark_interval)
        if bench_ep > 0:
            bench_hist = [{
                "episode": bench_ep,
                "skill_gap": last_benchmark.get("skill_gap"),
                "league_wr": last_benchmark.get("league_eval", {}).get("win_rate"),
                "exploitability_gap": last_benchmark.get("exploitability_gap"),
                "skill_gap_vs_random": last_benchmark.get("skill_gap_vs_random"),
            }]

    return {
        "records": records,
        "wins": wins,
        "losses": losses,
        "assisted": assisted,
        "seat_wins": seat_wins,
        "benchmark_history": bench_hist,
        "last_benchmark": last_benchmark,
    }


def _save_benchmark_history(out: Path, benchmark_history: list[dict]) -> None:
    (out / "benchmark_history.json").write_text(
        json.dumps(benchmark_history, indent=2), encoding="utf-8"
    )


def _init_policy(config: dict, seed: int, resume_path: str | None):
    if resume_path:
        path = Path(resume_path)
        backend = str(config.get("policy_backend", "numpy")).lower()
        if backend == "torch" and path.exists():
            from training.ctde_policy_torch import TorchSharedGRUPolicy, resolve_device

            if path.with_suffix(".pt").exists() or json.loads(path.read_text(encoding="utf-8")).get("backend") == "torch":
                return load_policy(path, config)
            return TorchSharedGRUPolicy.from_numpy_checkpoint(
                path, device=resolve_device(config.get("device")), target_config=config
            )
        return load_policy(path, config)
    return build_policy(config, seed=seed)


def train(
    episodes: int = 200,
    seed: int = 0,
    config_path: str = "configs/training.yaml",
    live: bool = True,
    output_dir: Path | None = None,
    viewer_public_dir: Path | None = None,
    benchmark_every: int | None = None,
    resume_checkpoint: str | None = None,
    start_episode: int = 0,
) -> dict:
    config = load_config(config_path)
    card_version = compute_card_set_version(load_all_cards())
    root = Path(__file__).resolve().parent.parent
    out = output_dir or (root / "game_logs" / "training")
    pub = viewer_public_dir if viewer_public_dir is not None else (
        root / "viewer" / "public" / "training" if live else None
    )
    writer = LiveMetricsWriter(output_dir=out, viewer_public_dir=pub)

    num_players = int(config.get("num_players", 6))
    train_all = bool(config.get("train_all_seats", True))
    backend = str(config.get("policy_backend", "numpy")).lower()
    rollout_workers = int(config.get("rollout_workers", 1))
    episodes_per_update = max(1, int(config.get("episodes_per_update", 1)))
    resume_path = resume_checkpoint if resume_checkpoint is not None else config.get("resume_checkpoint")
    if not resume_path:
        resume_path = None
    if resume_path:
        start_ep = int(start_episode or config.get("resume_episode", 0))
    else:
        start_ep = int(start_episode or 0)

    policy = _init_policy(config, seed, resume_path)
    checkpoint_mgr = CheckpointManager(out / "checkpoints")
    league = LeaguePool(config, checkpoint_mgr) if rollout_workers <= 1 else None
    checkpoint_interval = int(config.get("checkpoint_interval_episodes", 50))
    benchmark_interval = benchmark_every or int(config.get("benchmark_every", 0))

    worker_weights = out / "worker_policy_snapshot.json"
    rng = np.random.default_rng(seed)
    wins: list[float] = []
    losses: list[float] = []
    assisted: list[float] = []
    seat_wins: dict[int, list[float]] = {i: [] for i in range(num_players)}
    last_benchmark: dict | None = None
    benchmark_history: list[dict] = []
    benchmark_games = int(config.get("benchmark_games", 100))
    ep = start_ep
    total_target = start_ep + episodes

    if start_ep > 0:
        hydrated = _hydrate_from_disk(out, start_ep, benchmark_interval)
        wins = hydrated["wins"]
        losses = hydrated["losses"]
        assisted = hydrated["assisted"]
        seat_wins = hydrated["seat_wins"]
        for i in range(num_players):
            seat_wins.setdefault(i, [])
        benchmark_history = hydrated["benchmark_history"]
        last_benchmark = hydrated["last_benchmark"]
        writer.preload_history(hydrated["records"])

    arch = "ctde_torch_gru" if backend == "torch" else "ctde_shared_gru"
    device_name = getattr(getattr(policy, "device", None), "type", "cpu")
    startup_seat = (
        int(writer._history[-1]["train_seat"]) if writer._history else 0  # noqa: SLF001
    )
    startup_metrics = _build_metrics(
        card_version, train_all, start_ep, startup_seat,
        wins, losses, assisted, seat_wins, arch, backend, device_name,
        rollout_workers, episodes_per_update, last_benchmark,
    )
    if start_ep > 0:
        startup_metrics["resumed_from_episode"] = start_ep
    startup_msg = (
        f"Resumed at episode {start_ep} ({backend}, {device_name})"
        if start_ep > 0
        else f"CTDE training started ({backend}, {device_name}, workers={rollout_workers})"
    )
    writer.write(
        status="running",
        episode=start_ep,
        total_episodes=total_target,
        metrics=startup_metrics,
        message=startup_msg,
        benchmark_history=benchmark_history,
        series={
            "loss_ma20": _series_from_history(writer._history, "loss"),
            "win_rate_ma20": _series_from_history(writer._history, "won"),
        },
    )

    while ep < total_target:
        batch_eps = min(episodes_per_update, total_target - ep)
        batch_results: list[dict] = []

        if rollout_workers > 1 and backend == "torch":
            batch_results = collect_rollouts(
                config,
                policy,
                episodes=batch_eps,
                start_episode=ep + 1,
                seed=seed,
                weights_path=worker_weights,
                workers=rollout_workers,
            )
            trajectories = [r["trajectory"] for r in batch_results if r.get("trajectory")]
            update_stats: dict = {}
            if trajectories:
                update_stats = policy.update(trajectories)
                batch_loss = update_stats.get("policy_loss", 0.0) + update_stats.get("value_loss", 0.0)
            else:
                batch_loss = 0.0
            for i, result in enumerate(batch_results):
                ep += 1
                train_seat = int(result["train_seat"])
                result["loss"] = batch_loss / max(1, len(batch_results))
                result["policy_loss"] = update_stats.get("policy_loss", 0.0)
                result["value_loss"] = update_stats.get("value_loss", 0.0)
                _record_episode(
                    writer, wins, losses, assisted, seat_wins, ep, total_target, train_seat, result
                )
        else:
            for _ in range(batch_eps):
                ep += 1
                train_seat = (ep - 1) % num_players if train_all else int(config.get("train_seat", 0))
                game_seed = int(rng.integers(0, 2**31 - 1))
                result = run_shared_episode(
                    config,
                    GameRNG(seed=game_seed),
                    train_seat,
                    policy,
                    league=league,
                    game_index=ep,
                )
                _record_episode(
                    writer, wins, losses, assisted, seat_wins, ep, total_target, train_seat, result
                )
                batch_results.append(result)

        if checkpoint_interval > 0 and ep % checkpoint_interval == 0:
            checkpoint_mgr.save(policy, ep)

        if benchmark_interval > 0 and ep % benchmark_interval == 0:
            last_benchmark = run_benchmarks(
                policy, config_path, games=benchmark_games, seed=seed + ep, config=config
            )
            write_benchmark_report(last_benchmark, out / "benchmark.json")
            benchmark_history.append({
                "episode": ep,
                "skill_gap": last_benchmark.get("skill_gap"),
                "league_wr": last_benchmark.get("league_eval", {}).get("win_rate"),
                "exploitability_gap": last_benchmark.get("exploitability_gap"),
                "skill_gap_vs_random": last_benchmark.get("skill_gap_vs_random"),
            })
            _save_benchmark_history(out, benchmark_history)

        metrics = _build_metrics(
            card_version, train_all, ep, batch_results[-1]["train_seat"] if batch_results else 0,
            wins, losses, assisted, seat_wins, arch, backend, device_name,
            rollout_workers, episodes_per_update, last_benchmark,
        )
        hist = writer._history  # noqa: SLF001 — paired with preload_history
        series = {
            "loss_ma20": _series_from_history(hist, "loss"),
            "win_rate_ma20": _series_from_history(hist, "won"),
        }
        writer.write(
            status="running",
            episode=ep,
            total_episodes=total_target,
            metrics=metrics,
            message=f"Episode {ep}/{total_target} — batch {batch_eps} ({backend})",
            benchmark_history=benchmark_history,
            series=series,
        )

    if last_benchmark is None:
        last_benchmark = run_benchmarks(
            policy, config_path, games=benchmark_games, seed=seed + 99999, config=config
        )
        write_benchmark_report(last_benchmark, out / "benchmark.json")

    checkpoint_mgr.save(policy, ep)
    final = {
        "episodes": ep,
        "episodes_this_run": episodes,
        "final_win_rate_ma50": moving_average(wins, 50),
        "card_set_version": card_version,
        "train_all_seats": train_all,
        "policy_backend": backend,
        "benchmark": last_benchmark,
    }
    writer.write(
        status="complete",
        episode=ep,
        total_episodes=total_target,
        metrics={**metrics, **final},
        message="Training complete",
        benchmark_history=benchmark_history,
        series={
            "loss_ma20": _series_from_history(writer._history, "loss"),
            "win_rate_ma20": _series_from_history(writer._history, "won"),
        },
    )
    return final


def _record_episode(writer, wins, losses, assisted, seat_wins, ep, total, train_seat, result):
    wins.append(1.0 if result["won"] else 0.0)
    losses.append(result["loss"])
    assisted.append(1.0 if result["assisted_win"] else 0.0)
    seat_wins[train_seat].append(1.0 if result["won"] else 0.0)
    record = {
        "episode": ep,
        "won": result["won"],
        "reward": result["reward"],
        "loss": result["loss"],
        "policy_loss": result.get("policy_loss"),
        "value_loss": result.get("value_loss"),
        "train_seat": train_seat,
        "assisted_win": result["assisted_win"],
        "timestamp": time.time(),
    }
    writer.record_episode(record)
    writer.append_history_file(record)


def _build_metrics(
    card_version, train_all, ep, train_seat, wins, losses, assisted, seat_wins,
    arch, backend, device_name, rollout_workers, episodes_per_update, last_benchmark,
):
    metrics = {
        "card_set_version": card_version,
        "train_all_seats": train_all,
        "train_seat": train_seat,
        "train_win_rate": wins[-1] if wins else 0.0,
        "train_win_rate_ma20": moving_average(wins, 20),
        "train_win_rate_ma50": moving_average(wins, 50),
        "avg_loss": moving_average(losses, 20),
        "assisted_win_rate_ma20": moving_average(assisted, 20),
        "policy_architecture": arch,
        "policy_backend": backend,
        "device": device_name,
        "rollout_workers": rollout_workers,
        "episodes_per_update": episodes_per_update,
    }
    if last_benchmark:
        metrics["skill_gap"] = last_benchmark.get("skill_gap")
        metrics["exploitability"] = last_benchmark.get("exploitability")
        metrics["exploitability_gap"] = last_benchmark.get("exploitability_gap")
        metrics["league_wr"] = last_benchmark.get("league_eval", {}).get("win_rate")
    for s, vals in seat_wins.items():
        if vals:
            metrics[f"seat_{s}_win_rate_ma20"] = moving_average(vals, min(20, len(vals)))
    return metrics


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Train Crown & Court CTDE policy with live metrics")
    parser.add_argument("--episodes", type=int, default=200)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--config", default="configs/training.yaml")
    parser.add_argument("--no-live", action="store_true", help="Do not write viewer public JSON")
    parser.add_argument("--benchmark-every", type=int, default=0)
    parser.add_argument("--resume-checkpoint", default="")
    parser.add_argument("--start-episode", type=int, default=0)
    args = parser.parse_args()
    config = load_config(args.config)
    start_ep = args.start_episode or int(config.get("resume_episode", 0))
    resume = args.resume_checkpoint or config.get("resume_checkpoint") or None
    result = train(
        episodes=args.episodes,
        seed=args.seed,
        config_path=args.config,
        live=not args.no_live,
        benchmark_every=args.benchmark_every or None,
        resume_checkpoint=resume,
        start_episode=start_ep,
    )
    print(f"Training complete: {json.dumps({k: v for k, v in result.items() if k != 'benchmark'}, indent=2)}")


if __name__ == "__main__":
    main()
