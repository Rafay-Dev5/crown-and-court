from __future__ import annotations

import json
from pathlib import Path

from analytics.report_generator import generate_report


def generate_html_report(sweep_path: str, out_path: str) -> str:
    md = generate_report(sweep_path, out_path.replace(".html", ".md"))
    data = json.loads(Path(sweep_path).read_text(encoding="utf-8"))
    metrics = data.get("metrics", {})
    rows = "".join(
        f"<tr><td>{k}</td><td>{v}</td><td>{metrics.get('explanations', {}).get(k, '')}</td></tr>"
        for k, v in metrics.items()
        if k != "explanations" and not isinstance(v, dict)
    )
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Crown & Court Balance Report</title>
<style>
body {{ font-family: Georgia, serif; max-width: 900px; margin: 2rem auto; background: #f4ead5; color: #2c1810; }}
h1 {{ color: #4a0e12; }}
table {{ border-collapse: collapse; width: 100%; background: white; }}
th, td {{ border: 1px solid #c9a227; padding: 0.5rem; text-align: left; }}
th {{ background: #4a0e12; color: #f4ead5; }}
</style></head><body>
<h1>Crown & Court Balance Report</h1>
<p>Card set: <code>{data.get('card_set_version', '?')}</code> · Games: {data.get('games_run', 0)}</p>
<table><tr><th>Metric</th><th>Value</th><th>What it means</th></tr>{rows}</table>
<pre>{md}</pre>
</body></html>"""
    Path(out_path).write_text(html, encoding="utf-8")
    return html


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--sweep", default="game_logs/sweep_result.json")
    p.add_argument("--out", default="game_logs/balance_report.html")
    args = p.parse_args()
    generate_html_report(args.sweep, args.out)
    print(f"Wrote {args.out}")
