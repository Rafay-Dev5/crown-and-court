from __future__ import annotations

import argparse
import json
from pathlib import Path

from analytics.metrics import METRIC_EXPLANATIONS


def generate_report(sweep_path: str, out_path: str) -> str:
    data = json.loads(Path(sweep_path).read_text(encoding="utf-8"))
    metrics = data.get("metrics", {})
    lines = [
        "# Crown & Court Balance Report",
        "",
        f"**Card set version:** `{data.get('card_set_version', 'unknown')}`",
        f"**Games simulated:** {data.get('games_run', 0)} (recommended min: {data.get('min_recommended_n', '?')})",
        "",
        "## Key Metrics",
        "",
    ]

    for key in (
        "assisted_win_rate",
        "shield_hit_rate",
        "whiff_penalty_rate",
        "exploitability",
    ):
        if key in metrics:
            val = metrics[key]
            expl = METRIC_EXPLANATIONS.get(key, "")
            if isinstance(val, dict):
                lines.append(f"- **{key}**: {val}")
            else:
                lines.append(f"- **{key}**: {val:.2%}" if isinstance(val, float) and val <= 1 else f"- **{key}**: {val}")
            if expl:
                lines.append(f"  - *Plain English:* {expl}")

    ci = metrics.get("assisted_win_rate_ci")
    if ci:
        lines.extend([
            "",
            f"Assisted-win 95% Wilson CI: [{ci['low']:.2%}, {ci['high']:.2%}]",
        ])

    protection_ev = metrics.get("protection_net_ev", {})
    if protection_ev:
        lines.extend(["", "## Protection Card Net EV", ""])
        for cid, ev in sorted(protection_ev.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- `{cid}`: {ev:+.0f} gold/play (hit reward minus whiff cost)")

    lines.extend(["", "## Metric Guide", ""])
    for name, expl in METRIC_EXPLANATIONS.items():
        lines.append(f"- **{name}**: {expl}")

    report = "\n".join(lines)
    Path(out_path).write_text(report, encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate balance report from sweep")
    parser.add_argument("--sweep", default="game_logs/sweep_result.json")
    parser.add_argument("--out", default="game_logs/balance_report.md")
    args = parser.parse_args()
    report = generate_report(args.sweep, args.out)
    print(report)


if __name__ == "__main__":
    main()
