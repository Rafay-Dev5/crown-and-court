"""Export the full card catalog into rules.md / rules-print.html and (optionally) PDF."""

from __future__ import annotations

import argparse
import html
import re
import subprocess
from pathlib import Path

from engine.card_text import describe_card_full_lines
from engine.cards import build_deck, load_all_cards, load_config, write_manifest

ROOT = Path(__file__).resolve().parent.parent
BALANCE_CONFIG = ROOT / "configs" / "balance.yaml"
RULES_MD = ROOT / "rules.md"
RULES_HTML = ROOT / "rules-print.html"
RULES_PDF = ROOT / "rules.pdf"

BEGIN_MD = "<!-- BEGIN CARD CATALOG -->"
END_MD = "<!-- END CARD CATALOG -->"
BEGIN_HTML = "<!-- BEGIN CARD CATALOG -->"
END_HTML = "<!-- END CARD CATALOG -->"

CATEGORY_ORDER = [
    "economy",
    "alliance",
    "betrayal",
    "disruption",
    "protection",
    "tempo",
    "information",
    "supercard",
]


def _play_deck_cards(owner: str, deck_size: int | None) -> list[dict]:
    """Same subset the engine builds for play (first N designs by id)."""
    cards = build_deck(load_all_cards(), owner, deck_size)
    # Display order: category, then name (ids already filtered)
    cards.sort(
        key=lambda c: (
            CATEGORY_ORDER.index(c.get("category", "economy"))
            if c.get("category") in CATEGORY_ORDER
            else 99,
            c.get("name", ""),
            c.get("id", ""),
        )
    )
    return cards


def _effect_md(card: dict) -> str:
    lines = describe_card_full_lines(card)
    # Flatten nested bullets for markdown readability
    out: list[str] = []
    for line in lines:
        if line.startswith("  • "):
            out.append(f"  - {line[4:]}")
        elif line.startswith("  "):
            out.append(f"  - {line.strip()}")
        else:
            out.append(line)
    return "\n".join(out)


def render_markdown_catalog(king: list[dict], noble: list[dict], version: str) -> str:
    parts: list[str] = [
        BEGIN_MD,
        "",
        "## Card catalog",
        "",
        f"Play-deck cards used in the standard rules (**{len(king)} King** / **{len(noble)} Noble**). "
        f"Card set version: `{version}`.",
        "",
        "This list matches the simulation play decks "
        "(`king_deck_size` / `noble_deck_size` in `configs/balance.yaml`). "
        "Numbers and wording may change between playtest printings. "
        "Statuses mentioned on cards (e.g. *oathbreaker*, *marked*, *corrupt*, *discredited*) "
        "are temporary tags applied by effects; follow each card’s text.",
        "",
        "### King deck",
        "",
    ]
    for card in king:
        cat = str(card.get("category", "")).capitalize()
        rar = str(card.get("rarity", "")).capitalize()
        flavor = card.get("flavor_text")
        parts.append(f"#### {card.get('name')} — *{cat}* · {rar}")
        parts.append("")
        if flavor:
            parts.append(f"> {flavor}")
            parts.append("")
        parts.append(_effect_md(card))
        parts.append("")

    parts.extend(["### Noble deck", ""])
    for card in noble:
        cat = str(card.get("category", "")).capitalize()
        rar = str(card.get("rarity", "")).capitalize()
        flavor = card.get("flavor_text")
        parts.append(f"#### {card.get('name')} — *{cat}* · {rar}")
        parts.append("")
        if flavor:
            parts.append(f"> {flavor}")
            parts.append("")
        parts.append(_effect_md(card))
        parts.append("")

    parts.append(END_MD)
    return "\n".join(parts).rstrip() + "\n"


def _effect_html(card: dict) -> str:
    lines = describe_card_full_lines(card)
    items: list[str] = []
    for line in lines:
        if line.startswith("  • "):
            items.append(f"<li>{html.escape(line[4:])}</li>")
        elif line.startswith("  "):
            items.append(f"<li class=\"sub\">{html.escape(line.strip())}</li>")
        else:
            items.append(f"<li>{html.escape(line)}</li>")
    return "<ul class=\"card-effect\">" + "".join(items) + "</ul>"


def render_html_catalog(king: list[dict], noble: list[dict], version: str) -> str:
    parts: list[str] = [
        BEGIN_HTML,
        '<section class="card-catalog page-break">',
        "<h2>Card catalog</h2>",
        (
            f"<p>Play-deck cards used in the standard rules "
            f"(<strong>{len(king)} King</strong> / <strong>{len(noble)} Noble</strong>). "
            f"Card set version: <code>{html.escape(version)}</code>.</p>"
        ),
        (
            "<p>This list matches the simulation play decks "
            "(<code>king_deck_size</code> / <code>noble_deck_size</code>). "
            "Numbers and wording may change between playtest printings. "
            "Statuses named on cards (e.g. <em>oathbreaker</em>, <em>marked</em>, "
            "<em>corrupt</em>, <em>discredited</em>) are temporary tags from effects.</p>"
        ),
        "<h3>King deck</h3>",
    ]
    for card in king:
        cat = html.escape(str(card.get("category", "")).capitalize())
        rar = html.escape(str(card.get("rarity", "")).capitalize())
        name = html.escape(str(card.get("name", "")))
        flavor = card.get("flavor_text")
        parts.append('<article class="card-entry">')
        parts.append(f"<h4>{name} <span class=\"meta\">— {cat} · {rar}</span></h4>")
        if flavor:
            parts.append(f'<p class="flavor">{html.escape(str(flavor))}</p>')
        parts.append(_effect_html(card))
        parts.append("</article>")

    parts.append("<h3 class=\"page-break\">Noble deck</h3>")
    for card in noble:
        cat = html.escape(str(card.get("category", "")).capitalize())
        rar = html.escape(str(card.get("rarity", "")).capitalize())
        name = html.escape(str(card.get("name", "")))
        flavor = card.get("flavor_text")
        parts.append('<article class="card-entry">')
        parts.append(f"<h4>{name} <span class=\"meta\">— {cat} · {rar}</span></h4>")
        if flavor:
            parts.append(f'<p class="flavor">{html.escape(str(flavor))}</p>')
        parts.append(_effect_html(card))
        parts.append("</article>")

    parts.append("</section>")
    parts.append(END_HTML)
    return "\n".join(parts) + "\n"


def _replace_between(text: str, begin: str, end: str, replacement: str) -> str:
    pattern = re.compile(
        re.escape(begin) + r".*?" + re.escape(end),
        flags=re.DOTALL,
    )
    if pattern.search(text):
        return pattern.sub(replacement.rstrip("\n"), text, count=1)
    # Insert before design note / footer if markers missing
    return text


def update_rules_md(catalog: str, king_n: int, noble_n: int) -> None:
    text = RULES_MD.read_text(encoding="utf-8")
    # Refresh deck counts in the "what you need" table
    text = re.sub(
        r"(\| King deck \| \*\*)\d+( cards\*\*)",
        rf"\g<1>{king_n}\g<2>",
        text,
    )
    text = re.sub(
        r"(\| Noble deck \| \*\*)\d+( cards\*\*)",
        rf"\g<1>{noble_n}\g<2>",
        text,
    )
    text = re.sub(
        r"(\| Deck size \| )\d+( \| )\d+( \(each Noble\) \|)",
        rf"\g<1>{king_n}\g<2>{noble_n}\g<3>",
        text,
    )

    if BEGIN_MD in text and END_MD in text:
        text = _replace_between(text, BEGIN_MD, END_MD, catalog)
    else:
        # Replace the short "for the full card list" note with the catalog
        needle = (
            "For the full card list, see the `cards/king_deck/` and `cards/noble_deck/` "
            "folders, or run the card gallery in `viewer/`."
        )
        if needle in text:
            text = text.replace(needle, catalog.strip())
        else:
            # Insert before final italic line
            text = text.rstrip() + "\n\n" + catalog + "\n"

    # Keep a short pointer after catalog
    if "cards/king_deck/" not in text.split(END_MD)[-1] if END_MD in text else True:
        pass

    RULES_MD.write_text(text, encoding="utf-8")


CARD_CATALOG_CSS = """
    .card-catalog h3 {
      margin-top: 1.5rem;
    }
    .card-entry {
      margin: 0.85rem 0 1rem;
      padding-bottom: 0.65rem;
      border-bottom: 1px dotted var(--rule);
      break-inside: avoid;
    }
    .card-entry h4 {
      margin: 0 0 0.25rem;
      font-size: 1rem;
      color: var(--accent);
    }
    .card-entry .meta {
      font-weight: normal;
      color: var(--muted);
      font-size: 0.9rem;
    }
    .card-entry .flavor {
      margin: 0.2rem 0 0.35rem;
      font-style: italic;
      color: var(--muted);
      font-size: 0.9rem;
    }
    .card-effect {
      margin: 0.25rem 0 0;
      padding-left: 1.1rem;
      font-size: 0.88rem;
    }
    .card-effect li { margin: 0.12rem 0; }
    .card-effect li.sub { list-style: disc; }
"""


def update_rules_html(catalog: str, king_n: int, noble_n: int) -> None:
    text = RULES_HTML.read_text(encoding="utf-8")

    text = re.sub(
        r"(King deck: )\d+( cards)",
        rf"\g<1>{king_n}\g<2>",
        text,
    )
    text = re.sub(
        r"(Noble deck: )\d+( cards)",
        rf"\g<1>{noble_n}\g<2>",
        text,
    )
    text = re.sub(
        r"(<tr><td>King deck</td><td class=\"num\">)\d+( cards)",
        rf"\g<1>{king_n}\g<2>",
        text,
    )
    text = re.sub(
        r"(<tr><td>Noble deck</td><td class=\"num\">)\d+( cards)",
        rf"\g<1>{noble_n}\g<2>",
        text,
    )
    text = re.sub(
        r"(<tr><td>Deck size</td><td class=\"num\">)\d+(</td><td class=\"num\">)\d+",
        rf"\g<1>{king_n}\g<2>{noble_n}",
        text,
    )

    if "/* CARD CATALOG STYLES */" not in text:
        text = text.replace(
            "    .cheat-sheet h2 { margin-top: 0; }",
            "    .cheat-sheet h2 { margin-top: 0; }\n\n"
            "    /* CARD CATALOG STYLES */\n"
            + CARD_CATALOG_CSS,
        )

    if BEGIN_HTML in text and END_HTML in text:
        text = _replace_between(text, BEGIN_HTML, END_HTML, catalog)
    else:
        # Prefer after cheat-sheet, before footer; else before closing content div
        marker = '</section>\n    </div>\n  </article>'
        if marker in text:
            text = text.replace(
                marker,
                f"</section>\n\n      {catalog}\n    </div>\n  </article>",
                1,
            )
        else:
            insert_at = text.rfind('<p class="footer-note">')
            if insert_at != -1:
                text = text[:insert_at] + catalog + "\n      " + text[insert_at:]
            else:
                text = text.replace("</article>", catalog + "\n  </article>")

    RULES_HTML.write_text(text, encoding="utf-8")


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


def export_pdf() -> Path:
    browser = find_browser()
    if browser is None:
        raise RuntimeError("No Chrome/Edge found to print PDF")
    html_uri = RULES_HTML.resolve().as_uri()
    out = RULES_PDF.resolve()
    if out.exists():
        out.unlink()
    cmd = [
        str(browser),
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={out}",
        html_uri,
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    if not out.exists():
        raise RuntimeError("PDF was not created")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation")
    args = parser.parse_args()

    manifest = write_manifest()
    version = manifest["version"]
    config = load_config(BALANCE_CONFIG)
    king_size = config.get("king_deck_size")
    noble_size = config.get("noble_deck_size")
    king = _play_deck_cards("king", int(king_size) if king_size else None)
    noble = _play_deck_cards("noble", int(noble_size) if noble_size else None)

    md_catalog = render_markdown_catalog(king, noble, version)
    html_catalog = render_html_catalog(king, noble, version)
    update_rules_md(md_catalog, len(king), len(noble))
    update_rules_html(html_catalog, len(king), len(noble))

    print(f"Updated {RULES_MD.name} and {RULES_HTML.name}")
    print(
        f"Play deck {version}: {len(king)} King / {len(noble)} Noble "
        f"(from {BALANCE_CONFIG.name})"
    )

    if not args.no_pdf:
        pdf = export_pdf()
        print(f"Wrote {pdf} ({pdf.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
