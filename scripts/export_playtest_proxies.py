"""Generate printable playtest proxy cards (3×3 on A4) via HTML → Edge/Chrome PDF.

Uses browser print-to-PDF so the file opens reliably in Cursor, Edge, and Chrome.
"""

from __future__ import annotations

import argparse
import html
import subprocess
from pathlib import Path

from engine.card_text import describe_card_full_lines, describe_timing
from engine.cards import build_deck, load_all_cards, load_config, write_manifest

ROOT = Path(__file__).resolve().parent.parent
BALANCE_CONFIG = ROOT / "configs" / "balance.yaml"
DEFAULT_HTML = ROOT / "cards" / "playtest_proxies.html"
DEFAULT_PDF = ROOT / "cards" / "playtest_proxies.pdf"

CATEGORY_COLORS = {
    "economy": "#8c6b1f",
    "alliance": "#2e6647",
    "betrayal": "#73201e",
    "disruption": "#593872",
    "protection": "#34527a",
    "tempo": "#664c26",
    "information": "#405866",
    "supercard": "#805a1a",
}

OWNER_COLORS = {
    "king": "#6b1419",
    "noble": "#1f4761",
}


def _play_decks() -> tuple[list[dict], list[dict], str]:
    manifest = write_manifest()
    config = load_config(BALANCE_CONFIG)
    cards = load_all_cards()
    king = build_deck(cards, "king", int(config.get("king_deck_size") or 0) or None)
    noble = build_deck(cards, "noble", int(config.get("noble_deck_size") or 0) or None)
    king.sort(key=lambda c: c.get("id", ""))
    noble.sort(key=lambda c: c.get("id", ""))
    return king, noble, manifest["version"]


def _rules_lines(card: dict) -> tuple[list[str], str | None]:
    timing = describe_timing(card.get("timing") or "on_reveal")
    body = [ln for ln in describe_card_full_lines(card) if ln != timing]
    flavor = card.get("flavor_text")
    if isinstance(flavor, str) and flavor.startswith("Expansion design"):
        flavor = None
    return body, flavor if isinstance(flavor, str) else None


def _card_html(card: dict) -> str:
    owner = str(card.get("owner_type", "noble"))
    cat = str(card.get("category", ""))
    rarity = str(card.get("rarity", "common")).capitalize()
    timing = str(card.get("timing", "on_reveal")).replace("_", " ")
    name = html.escape(str(card.get("name", "Unknown")))
    accent = OWNER_COLORS.get(owner, "#333")
    bar = CATEGORY_COLORS.get(cat, accent)
    body, flavor = _rules_lines(card)

    rules_bits: list[str] = []
    for line in body:
        raw = line.strip()
        cls = " sub" if line.startswith("  ") else ""
        if raw.startswith("• "):
            raw = raw[2:]
            rules_bits.append(f'<li class="bullet{cls}">{html.escape(raw)}</li>')
        elif cls:
            rules_bits.append(f'<li class="bullet{cls}">{html.escape(raw)}</li>')
        else:
            rules_bits.append(f"<li>{html.escape(raw)}</li>")
    rules_html = "<ul class=\"rules\">" + "".join(rules_bits) + "</ul>"
    flavor_html = f'<p class="flavor">{html.escape(flavor)}</p>' if flavor else ""

    return f"""
<article class="card" style="--accent:{accent};--bar:{bar}">
  <header class="card-head">
    <h2 class="name">{name}</h2>
    <span class="badge">{html.escape(owner.upper())}</span>
  </header>
  <div class="art"><span>playtest</span></div>
  <div class="type">{html.escape(cat.capitalize())} — {html.escape(timing)} · {html.escape(rarity)}</div>
  <div class="text">
    {rules_html}
    {flavor_html}
  </div>
  <footer class="foot">Crown &amp; Court · {html.escape(str(card.get("id", "")))}</footer>
</article>
"""


def _chunk(items: list, n: int):
    for i in range(0, len(items), n):
        yield items[i : i + n]


def render_html(king: list[dict], noble: list[dict], version: str, noble_copies: int) -> str:
    sheets: list[str] = []

    # Cover
    sheets.append(
        f"""
<section class="sheet cover">
  <h1>Crown &amp; Court</h1>
  <p class="sub">Playtest card proxies</p>
  <p>Card set version: <code>{html.escape(version)}</code></p>
  <p>King deck: <strong>{len(king)}</strong> cards (print once)</p>
  <p>Noble deck: <strong>{len(noble)}</strong> cards × <strong>{noble_copies}</strong>
     (one deck per Noble)</p>
  <ul>
    <li>Print at <strong>100% / actual size</strong> (do not fit-to-page).</li>
    <li>Paper: A4. Card size: 63 × 88 mm.</li>
    <li>Cut on the red dashed guides.</li>
    <li>Artwork intentionally blank — marked <em>playtest</em>.</li>
  </ul>
</section>
"""
    )

    def add_deck(cards: list[dict], title: str) -> None:
        for sheet_i, batch in enumerate(_chunk(cards, 9), start=1):
            cards_html = "".join(_card_html(c) for c in batch)
            # pad empty slots so cut guides stay aligned
            empty = 9 - len(batch)
            cards_html += '<div class="card empty"></div>' * empty
            sheets.append(
                f"""
<section class="sheet">
  <p class="banner">{html.escape(title)} · sheet {sheet_i} · cut on red dashes · 63×88 mm</p>
  <div class="grid">{cards_html}</div>
</section>
"""
            )

    add_deck(king, f"KING DECK ({len(king)} cards)")
    for copy_i in range(noble_copies):
        label = (
            f"NOBLE DECK ({len(noble)} cards)"
            if noble_copies == 1
            else f"NOBLE DECK copy {copy_i + 1}/{noble_copies} ({len(noble)} cards)"
        )
        add_deck(noble, label)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Crown &amp; Court — Playtest Proxies</title>
<style>
  @page {{ size: A4; margin: 0; }}
  * {{ box-sizing: border-box; }}
  html, body {{
    margin: 0;
    padding: 0;
    font-family: Georgia, "Times New Roman", serif;
    color: #1a120e;
    background: #fff;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}
  .sheet {{
    width: 210mm;
    height: 297mm;
    page-break-after: always;
    position: relative;
    overflow: hidden;
    padding: 8mm 6mm 6mm;
  }}
  .sheet:last-child {{ page-break-after: auto; }}
  .cover {{
    padding: 28mm 22mm;
  }}
  .cover h1 {{
    font-size: 32pt;
    font-weight: normal;
    color: #6b1419;
    margin: 0 0 0.25em;
  }}
  .cover .sub {{ font-size: 16pt; color: #5a4638; margin: 0 0 1.5em; }}
  .cover p {{ margin: 0.4em 0; font-size: 11pt; }}
  .cover ul {{ margin-top: 1.2em; font-size: 11pt; line-height: 1.5; }}

  .banner {{
    text-align: center;
    font-family: system-ui, sans-serif;
    font-size: 8pt;
    color: #5a4638;
    margin: 0 0 3mm;
  }}

  .grid {{
    width: 189mm; /* 3 × 63mm */
    height: 264mm; /* 3 × 88mm */
    margin: 0 auto;
    display: grid;
    grid-template-columns: repeat(3, 63mm);
    grid-template-rows: repeat(3, 88mm);
    outline: 0.4pt dashed #d62828;
  }}

  .card {{
    width: 63mm;
    height: 88mm;
    border: 1.2pt solid #1a120e;
    outline: 0.35pt dashed #d62828;
    outline-offset: -0.35pt;
    background: #faf6ef;
    padding: 2mm;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    position: relative;
  }}
  .card.empty {{
    background: transparent;
    border-color: transparent;
    outline-color: #d62828;
  }}

  .card-head {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1mm;
    margin-bottom: 1.2mm;
  }}
  .name {{
    margin: 0;
    font-size: 9pt;
    font-weight: normal;
    line-height: 1.15;
    flex: 1;
  }}
  .badge {{
    flex: 0 0 auto;
    background: var(--accent);
    color: #fff;
    font-family: system-ui, sans-serif;
    font-size: 6.5pt;
    font-weight: 600;
    letter-spacing: 0.04em;
    padding: 0.8mm 1.4mm;
  }}

  .art {{
    height: 22mm;
    border: 0.6pt solid #8a7a68;
    background: #e4dfd6;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 1.2mm;
  }}
  .art span {{
    font-family: system-ui, sans-serif;
    font-size: 12pt;
    color: #6a5e54;
    letter-spacing: 0.04em;
  }}

  .type {{
    background: var(--bar);
    color: #fff;
    font-family: system-ui, sans-serif;
    font-size: 6pt;
    padding: 0.9mm 1.2mm;
    margin-bottom: 1.2mm;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}

  .text {{
    flex: 1;
    border: 0.5pt solid #c4a882;
    background: #fffcf7;
    padding: 1mm 1.2mm;
    overflow: hidden;
    font-size: 6.2pt;
    line-height: 1.25;
  }}
  .rules {{
    margin: 0;
    padding: 0;
    list-style: none;
  }}
  .rules li {{ margin: 0.15mm 0; }}
  .rules li.bullet {{ padding-left: 2mm; }}
  .rules li.bullet::before {{ content: "• "; margin-left: -2mm; }}
  .rules li.sub {{ font-size: 5.8pt; color: #2a2018; }}
  .flavor {{
    margin: 1mm 0 0;
    font-style: italic;
    color: #5a4638;
    font-size: 5.6pt;
  }}

  .foot {{
    margin-top: 0.8mm;
    font-family: system-ui, sans-serif;
    font-size: 4.5pt;
    color: #6a5e54;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}

  @media screen {{
    body {{ background: #d8d0c4; }}
    .sheet {{
      background: #fff;
      margin: 8px auto;
      box-shadow: 0 2px 12px rgba(0,0,0,0.18);
    }}
  }}
</style>
</head>
<body>
{"".join(sheets)}
</body>
</html>
"""


def find_browser() -> Path | None:
    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def export_pdf_from_html(html_path: Path, pdf_path: Path) -> Path:
    browser = find_browser()
    if browser is None:
        raise RuntimeError("No Chrome/Edge found to print PDF")
    if pdf_path.exists():
        pdf_path.unlink()
    cmd = [
        str(browser),
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path.resolve()}",
        html_path.resolve().as_uri(),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    if not pdf_path.exists() or pdf_path.stat().st_size < 1000:
        raise RuntimeError("PDF was not created or is too small")
    return pdf_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML)
    parser.add_argument("--noble-copies", type=int, default=1)
    parser.add_argument("--no-pdf", action="store_true")
    args = parser.parse_args()

    king, noble, version = _play_decks()
    html_doc = render_html(king, noble, version, max(1, args.noble_copies))
    args.html.parent.mkdir(parents=True, exist_ok=True)
    args.html.write_text(html_doc, encoding="utf-8")
    print(f"Wrote {args.html}")

    if not args.no_pdf:
        pdf = export_pdf_from_html(args.html, args.out)
        print(f"Wrote {pdf} ({pdf.stat().st_size} bytes)")
        print(f"Play deck: {len(king)} King / {len(noble)} Noble × {max(1, args.noble_copies)}")


if __name__ == "__main__":
    main()
