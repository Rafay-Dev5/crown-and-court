# Adding Cards Manually

Cards are plain JSON files. The engine and viewer pick them up automatically — no code changes needed for simple cards.

## 1. Create a JSON file

Add one file per unique card design:

- **King cards:** `cards/king_deck/your_card_name.json`
- **Noble cards:** `cards/noble_deck/your_card_name.json`

Copy an existing card from the same category and edit it, or use this template:

```json
{
  "id": "noble_my_card_001",
  "name": "My Card Name",
  "owner_type": "noble",
  "category": "economy",
  "rarity": "common",
  "copies_in_deck": 3,
  "timing": "on_reveal",
  "effect": {
    "primitive": "gold_gain",
    "params": { "target": "self", "amount": 75 }
  },
  "tags": ["economy"],
  "flavor_text": "Short thematic quote for the card."
}
```

### Required fields

| Field | Values |
|-------|--------|
| `id` | Unique slug, e.g. `noble_smugglers_route_001` |
| `name` | Display name |
| `owner_type` | `king` or `noble` |
| `category` | `economy`, `alliance`, `betrayal`, `disruption`, `protection`, `tempo`, `information`, `supercard` |
| `rarity` | `common`, `rare`, `supercard` |
| `copies_in_deck` | How many copies go in the deck (integer ≥ 1) |
| `timing` | `on_reveal`, `reactive`, `end_of_round`, `negotiation_only` |
| `effect` | `{ "primitive": "...", "params": { ... } }` |

### Optional fields

- `on_whiff_penalty` — **required for protection cards** (what happens if your guess was wrong)
- `requires_state` — preconditions (alliance, prior choice, etc.)
- `synergy_tags` — combo tags for balance tooling
- `tags`, `flavor_text`, `designer_notes`

See [`cards/schema.json`](cards/schema.json) and [`../prd_card_design.md`](../prd_card_design.md) for the full spec.

## 2. Validate

From `crown-and-court/`:

```bash
.venv\Scripts\activate
python -m engine.validate
```

Fix any reported errors before committing.

## 3. Refresh the card-set hash (for balance sweeps)

```bash
make manifest
```

This updates `cards/manifest.json` so simulation reports trace which card version was used.

## 4. View in the gallery

The dev server watches card files and reloads automatically:

```bash
cd viewer
npm run dev
```

Open http://localhost:5173 — your new card appears in the grid with a plain-English effect summary.

## 5. Test in simulation (optional)

```bash
python -m engine.play --seed 42 --players 6 --rounds 3
```

## Effect primitives (quick reference)

| Primitive | Plain meaning |
|-----------|----------------|
| `gold_gain` / `gold_loss` | Add or remove gold |
| `gold_transfer` | Move gold between players (set `"as_theft": true` for steals) |
| `dice_swing` | Player chooses a path, rolls a die, success/failure branches |
| `protect_gold` | Block gold theft if your guess was right |
| `block_succession` | Prevent a Noble becoming King this check |
| `mark_status` | Apply a visible status tag |
| `conditional_swing` | Different outcomes based on prior choices or dice |

Full list: `engine/effects/primitives.py` and Environment PRD §4.3.

## Tips

- **Unique IDs** — duplicate `id` values are rejected by validation.
- **Protection cards** must include `on_whiff_penalty` (even a small gold loss).
- **Betrayal cards** should use `"as_theft": true` on `gold_transfer`.
- After adding several cards, run `pytest` to ensure nothing broke.
