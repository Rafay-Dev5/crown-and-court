# Crown & Court — Project Status

**Last updated:** 2026-07-06 (stub card design + re-signoff on singleton deck)  
**Repository:** `D:\Kingmaker\crown-and-court`  
**Card set version:** `af4e2166dbec6af5` (70 unique: **30 King / 40 Noble**, 1 copy each)  
**Tests:** 40 passing (`pytest -q`)

---

## 1. What this project is

Crown & Court is a **Python simulation and balance lab** for a 4–8 player political card game. It is not the tabletop product itself — it is the engine, card data, bots, RL training loop, and analytics pipeline used to answer:

- Are cards balanced?
- Is kingmaking controllable?
- Can agents learn to play?
- Does starting seat / role matter too much?

Companion PRDs live at repo root: `prd_card_design.md`, `prd_rl_agents.md`.

---

## 2. Architecture (high level)

```
cards/          JSON card definitions + schema + manifest hash
engine/         Rules: rounds, negotiation, playing, effects, shields, succession
agents/         Heuristic bots + smart choice policies
env/            PettingZoo AEC wrapper (incremental DecisionEngine stepping)
training/       CTDE PPO (numpy + PyTorch CUDA), parallel rollouts, league, benchmarks
analytics/      Sweeps, kingmaker A/B, auto-tune, sign-off compare, SQLite log
viewer/         React gallery: cards, balance charts, replay, live training
game_logs/      sweep_result.json, signoff_comparison.json, training/live.json, …
configs/        balance.yaml, training.yaml, balance_targets.yaml
```

**Simulation loop:** Negotiation → Succession check → Playing (commit/reveal) → Succession check → next round. Winner = whoever holds the **King seat** at game end.

---

## 3. What has been implemented (detailed)

### 3.1 Rules engine (`engine/`)

| Component | Status | Notes |
|-----------|--------|-------|
| Round loop | Done | Negotiation → play → succession ×2 per round |
| Gold + earned gold ledger | Done | Gifted gold tracked separately; succession uses `earned_gold` |
| 27 effect primitives | Done | gold, theft, dice_swing, shields, alliance, etc. |
| Protection / whiff | Done | `on_whiff_penalty`, single-use shields |
| Negotiation | Done | trade, alliance, conditional, accept/reject/threaten/pass |
| Succession | Done | Noble ascends if `earned_gold` > King; seat swap keeps gold on people |
| Dice + player choice | Done | Development Fund, Gambler's Wager, etc. |
| CLI | Done | `python -m engine.play`, `python -m engine.validate` |

**Structural asymmetries (intentional in design; tunable via config/cards, not start gold):**

- King plays **3 cards/round** vs Noble **2** (`king_plays_per_round` / `noble_plays_per_round`; engine default 3/2)
- King redraws **3** vs Noble **2** after playing (`king_redraw` / `noble_redraw`; engine default 3/2)
- King **always plays first** each round (`king_seat` + `noble_play_order()`)
- Starting gold: **1000 King** / **600 Noble** — **locked** (see §4.0; never auto-tuned)
- King play/redraw counts (**3/3**) — **locked** alongside start gold
- **`random_starting_king_seat: true`** in balance/training configs — starting King seat rotates each game

### 3.2 Card set (`cards/`)

| Metric | Value |
|--------|-------|
| King designs | **30** (unique, 1 copy each) |
| Noble designs | **40** (unique, 1 copy each) |
| Total | **70** |
| Copies per design | **1** (`copies_in_deck: 1` everywhere) |
| Categories | All 8 covered ≥2× per deck (economy, alliance, betrayal, disruption, protection, tempo, information, supercard) |
| Validation | `python -m engine.validate` — all pass |

Deck resize: `make resize-decks` (`scripts/resize_unique_decks.py`) added 6 King + 10 Noble designs to hit 30/40 targets.

**Stub design pass (2026-07-06):** all 16 resize placeholders replaced with on-theme cards per PRD §10/§11 via `make replace-stubs` (`scripts/replace_stub_cards.py`). Examples: Grain Toll, Harbor Dues, Vault Seal, Smuggler's Tithe, Cut Supply Lines, Night Collection. Post-replacement balance pass (numeric tuning + targeted noble theft nerfs) re-established **5/5 sign-off gates** on the current singleton deck.

Manual outlier nerfs/buffs via `scripts/nerf_outliers.py` (Phase A: King economy down, Noble catch-up up; **never changes start gold**).

### 3.3 Bots & policies (`agents/`)

| Bot | Negotiation | Play | Choices |
|-----|-------------|------|---------|
| hoard | Pass | Prefers economy cards | Smart (safe/public paths) |
| aggressive | Trades (30–50 gold request; passes when ahead) | Prefers disruption/betrayal + smart protection | Smart (risky paths) |
| ally_neighbor | Alliance to neighbor | Prefers alliance cards + smart protection | Smart (alliance-friendly) |
| exploit | Accepts small trades/alliances; low random spam | Random play + smart protection on default theft target | Smart (context-aware) |
| random | Random | Random | Random |

**Balance sweeps** assign a bot per seat via `configs/balance.yaml` → `seat_bots`.

### 3.4 RL / training (`training/`)

| Feature | Status |
|---------|--------|
| PPO (numpy) | Done — **keep PPO**; no CFR/regret-matching |
| **CTDE shared GRU policy** | Done (`use_ctde: true`) — one actor + centralized critic |
| Seat embedding (one-hot) | Done — actor input 48 + 8 = **56-dim** |
| Centralized critic | Done — stacked global obs **392-dim** (all seats + acting-seat) |
| GAE + clipped surrogate | Done |
| Train all seats (rotate) | Done (`train_all_seats: true`) — shared policy, not 6 independent nets |
| Policy-driven negotiation | Done (pass/trade/alliance/accept/reject/fallback) |
| Policy play + choice | Done |
| Live metrics JSON | Done → `viewer/public/training/live.json` |
| **Population league** | Done — heuristic bots + frozen checkpoints (`checkpoint_mix: 0.35`) |
| **Skill-gap / exploitability benchmark** | Done — `training/benchmark.py`, `make benchmark` |
| **PyTorch GPU CTDE** | Done — `policy_backend: torch`, CUDA, batched PPO (`ctde_policy_torch.py`) |
| **Parallel rollouts** | Done — `rollout_workers: 4`, `episodes_per_update: 4` (~0.9 s/ep vs ~71 s CPU) |
| **5k episode training** | **Pipeline validation only** — GPU run on prior card set `1387a23db64e03da`; **not** a result to build on after stub redesign |
| Legacy numpy CTDE | Kept for tests / league export; production path is torch when configured |

**Observation space (48-dim, `agents/heuristic/observation.py`):**

| Index | Signal |
|-------|--------|
| 0 | Round progress (`current_round / n_rounds`) |
| 1 | Is King seat |
| 2–3 | Self gold / earned gold (÷2000) |
| 4 | Hand size (÷8) |
| 5–6 | Phase flags (negotiation / playing) |
| 7–14 | Hand category counts (8 categories, ÷8) |
| 15–26 | Per-seat gold + earned gold (6 seats × 2, ÷2000) |
| 27–30 | Negotiation context: threat received, alliance active, pending trade, default theft target |
| 31 | Earned-gold rank percentile |
| 32 | Gifted gold ratio (÷2000) |
| 33–47 | Reserved (zeros) |

**Reward shaping:** `reward_shaping` in `configs/training.yaml` (default `false`). Sweeps and signoff assert it stays off.

**Benchmark metrics** (`training/benchmark.py` — run **before** scaling to 5k+ episodes):

| Metric | Meaning |
|--------|---------|
| `skill_gap` | League win rate − fair share (1/n) |
| `skill_gap_vs_random` | League WR − all-random opponent WR |
| `exploitability_gap` | League WR − all-exploit roster WR |
| `exploitability` | `stats.exploitability_estimate(league_wr, 1 − exploit_wr)` |

Output: `game_logs/training/benchmark.json`. Artifacts: `benchmark_pre_5k.json`, `benchmark_mid_1750.json`, `benchmark_post_5k.json`.

### 3.5 Analytics (`analytics/`)

| Tool | Purpose |
|------|---------|
| `sweeps.py` | Run N games with league bots; export metrics + replay sample |
| `kingmaker_test.py` | Synthetic gift scenario: gold_only vs earned_gold checker |
| `auto_tune.py` | Numeric card tweaks, role-win tuning, negotiation gift cap — **never touches start gold** |
| `signoff_compare.py` | Compare 100-game tuned vs 385-game PRD sample |
| `export_viewer_balance.py` | Plain + dev JSON for gallery Balance tab |
| `log_store.py` | SQLite history `game_logs/balance_history.db` |
| `report_generator.py` | Markdown balance report |
| `metrics.py` | Seat wins, role wins, card win contribution, assisted wins, shields |

### 3.6 Viewer (`viewer/`)

| Tab | Content |
|-----|---------|
| Card Gallery | 70 cards, plain-English effects, validation badges |
| Balance Results | Seat win chart, card win contribution, sign-off comparison, kingmaker summary |
| Game Replay | Plain timeline from last sweep |
| Live Training | Polls training metrics every 2s |
| Category Gaps | Taxonomy coverage |
| Analytics Guide | Metric definitions |

### 3.7 Tests (`tests/`)

40 tests: engine, shields, dice, cards schema, env stepping, PPO, CTDE, benchmarks, training smoke, metrics, smart choices, random starting King seat.

---

## 4. Current results (everything we have measured)

### 4.0 Immutable core rules (mandated everywhere)

**Starting gold is not a balance knob.** These values are fixed in `configs/balance.yaml`, `configs/training.yaml`, and enforced by `configs/balance_targets.yaml` → `locked_rules` plus `analytics/auto_tune.py` (`LOCKED_RULE_KEYS`, `_enforce_locked_rules`).

| Rule | Value | May change for balance? |
|------|-------|-------------------------|
| `king_start_gold` | **1000** | **No** |
| `noble_start_gold` | **600** | **No** |
| `king_plays_per_round` | **3** | **No** |
| `king_redraw` | **3** | **No** |

Allowed balance levers: `random_starting_king_seat`, card numeric params, negotiation gift cap, bot assignment, protection whiff tuning, Noble play/redraw (2/2).

### 4.1 PRD sign-off sweep — **385 games** (post Phase A)

Source: `game_logs/sweep_result.json`, `game_logs/signoff_comparison.json` (run: `make signoff`, 2026-07-05)

| Metric | Result | Target | Pass? |
|--------|--------|--------|-------|
| **Started-as-King win rate** | **41.8%** | 35–45% | **Yes** |
| Started-as-Noble win rate | 58.2% | 55–65% | **Yes** |
| Seat win spread | **22.6%** | ≤15–20% | Borderline |
| Assisted win rate | **31.2%** | ≤12% | No |
| Shield hit rate | **2.0%** | 25–70% | No |
| Whiff penalty rate | **98.0%** | — | Protection rarely triggers |
| Kingmaker fix (synthetic) | earned_gold blocks gift ascension | Must work | **Yes** |
| Sample size | 385 games | ≥385 | **Yes** |
| Sign-off gates passed | **2 / 5** | role + sample | Partial |

**Phase A goal met:** role win rate is in the **35–45%** band at 385 games with **King 3 plays / 3 redraw** restored and start gold unchanged.

### 4.1b Previous baseline (pre Phase A, for comparison)

| Metric | Before Phase A | After Phase A |
|--------|----------------|---------------|
| Started-as-King win rate | **65.2%** | **41.8%** |
| Seat 0 win rate | **65.2%** | ~16–23% per seat (rotating start) |
| Seat win spread | **64.7%** | **22.6%** |
| Card set version | `a214bb4996cd396a` | `7b01aa4e0329a524` |

### 4.2 Auto-tune run (100 games, 3 passes)

| Metric | Before tuning era | After recent pipeline |
|--------|-------------------|------------------------|
| Assisted win (random bots) | ~60% | ~8–12% |
| Negotiation gift cap | uncapped | **180 gold** (auto-tuned down from 200) |

### 4.3 Training run — **5000 episodes**, CTDE torch GPU, seed 7 (2026-07-06)

Source: `game_logs/training/live.json`, `benchmark_pre_5k.json`, `benchmark_mid_1750.json`, `benchmark.json`

**Run summary:** CPU numpy run stopped at ep ~1772 (~71 s/ep). Resumed on **PyTorch CUDA** (hidden 128, minibatch 256, 4 parallel workers) — 3250 episodes in **~47 min** (~0.9 s/ep).

| Metric | Value | Notes |
|--------|-------|-------|
| Total episodes | **5000** | Resumed from `policy_ep001750.json` |
| Final train win rate MA50 | **12%** | In-training league games (high variance) |
| Assisted win MA20 (end) | **10%** | Within signoff band |
| Policy | CTDE torch GRU + centralized critic | `policy_backend: torch`, device cuda |
| Checkpoint | `game_logs/training/checkpoints/policy_ep005000.json` | |

**Skill-gap benchmarks** (100 games each, seat 0, `reward_shaping: false`):

| Stage | League WR | Skill gap | Exploitability |
|-------|-----------|-----------|----------------|
| Pre (untrained) | 15% | −1.7% | 0.76 |
| Mid (ep 1750, numpy) | 20% | +3.3% | 0.55 |
| **Post (ep 5000, torch)** | **24%** | **+7.3%** | **0.64** |

League win rate improved vs fair share (16.7%); exploit roster WR dropped (12% post vs 9% pre), so gains are not purely roster overfitting. Next levers: 20k+ episodes, reward shaping experiments, richer league/self-play mix.

### 4.3b Legacy — **200 episodes**, numpy GRU, seed 7 (pre–Phase C)

Source: `viewer/public/training/live.json`

| Metric | Value | Notes |
|--------|-------|-------|
| Final win rate MA50 | **12%** | Agent wins when their person ends as King |
| Win rate MA20 | 20% | High variance |
| Assisted win MA20 | 15% | During training games |
| Per-seat MA20 | Seat 0: 25%, 1: 5%, 2: 15%, 3: 20%, 4–5: 0% | Only ~33 episodes/seat in 200 ep rotation |
| Policy | GRU + policy negotiation | 6 separate policies |

Training win rate **≠** balance win rate: post Phase A, started-as-King prior is **~39%** (not 65%), so training metrics should be re-benchmarked.

### 4.4 Card win contribution (385-game sample)

Top flagged overperformers are **mostly King deck cards** (Royal Pardon ~79% win-when-played before second nerf). This metric **correlates with “who is King when King cards are played”** — interpret with caution until role-normalized metrics exist.

---

## 5. Why was the King winning so much? (and what Phase A changed)

Historically this was **expected from old rules + setup**, not primarily a training bug. Six compounding causes — **Phase A addressed 1, 3, 4, and 6 without touching start gold:**

### 5.1 Starting resource gap (unchanged — locked)

```yaml
king_start_gold: 1000   # DO NOT CHANGE for balance
noble_start_gold: 600   # DO NOT CHANGE for balance
```

King still begins with **67% more gold and earned gold**. Succession requires a Noble's **earned_gold > King's earned_gold**. Phase A compensates via card/action tuning, not gold changes.

### 5.2 Fixed starting seat → **fixed in Phase A**

- **`random_starting_king_seat: true`** — King seat rotates each game (`engine/phases.py`).
- Metrics read `starting_king_person` from `game_setup` events (`analytics/metrics.py`).
- Seat 0 no longer dominates win rate.

### 5.3 Structural turn / card advantage → **partially reduced in Phase A**

| Rule | King (core rules) | Noble |
|------|-------------------|-------|
| Cards played per round | **3** | **2** |
| Cards redrawn after round | **3** | **2** |
| Play order | First every round | After King |
| Deck | 24 King designs | 30 Noble (buffed steal/economy) |

### 5.4 Heuristic + deck synergy at seat 0

Balance config puts **hoard** on seat 0 — plays economy King cards. King deck + extra plays + gold lead = self-reinforcing lead.

### 5.5 Succession is hard to trigger

Two checks per round × 5 rounds, but bar is high (`earned_gold` strictly greater than King). Many games end with **never ascended** or ascended once then King pulls ahead again.

### 5.6 Metric coupling (card “overperformers”)

“Win when this card was played” counts games where **the player who played the card ended as King**. King cards are mostly played **by whoever is King** → inflated win rates for King card IDs.

---

## 6. How to improve training (and what to fix first)

Training cannot fix a **65% role prior** without either **balance changes** or **much richer learning**. Recommended order:

### 6.1 Fix simulation fairness first (Phase A — **done**)

These were **balance/engine/card** changes, not ML hyperparameters. **Start gold was not changed.**

1. **`random_starting_king_seat: true`** — rotates starting King seat each game.
2. **Card tuning + random King seat** — King 3 plays / 3 redraw and Noble 2/2 remain locked core rules.
3. **Card tuning** — King economy nerfs + Noble catch-up buffs (`scripts/nerf_outliers.py`, `auto_tune.py` role loop).
4. **Locked gold mandate** — `balance_targets.yaml` + `auto_tune.py` refuse to modify `king_start_gold` / `noble_start_gold`.
5. **Role-normalized analytics** — still TODO (Phase B).

Until assisted-win and shield gates pass, **full print sign-off remains open** — but role win rate is now in band.

5. **Role-normalized analytics** — done (Phase B5); use before further card nerfs.

Until **all Phase C entry requirements** (§9) pass at 385 games, do not scale training — agents will learn to exploit broken shield/assisted-win mechanics, not to play well.

### 6.2 Training loop improvements — **Phase C prerequisites vs Phase C work**

| Change | When | Status |
|--------|------|--------|
| **385-game shield + assisted gates pass** | Before Phase C | **Pass** — shield **26.4%**, assisted **9.9%** (385-game, `--no-tune`) |
| **Assisted-win mechanics** (bilateral cap, tighter metric, bot volume) | Before Phase C | **Done** (B7) |
| **Richer observations** (hand composition, opponent gold, negotiation) | **Before Phase C** | **Done** — 48-dim obs |
| **Reward shaping toggle** (on for training, **off** for sweeps/signoff) | **Before 5k episodes** | **Done** — asserted in sweeps/balance pipeline |
| **CTDE shared actor + centralized critic** | Before 5k episodes | **Done** |
| **Skill-gap / exploitability benchmark** | Before 5k episodes | **Done** — `make benchmark` |
| **Population league + frozen checkpoints** | Before 5k episodes | **Done** |
| **Unique decks 30 King / 40 Noble** | Before 5k episodes | **Done** — shield re-tuned via `make tune-shield` |
| More episodes (5k–50k) | Phase C | **Done** — 5k complete; scale to 20k+ optional |
| PyTorch + GPU | Phase C | **Done** — `ctde_policy_torch.py`, CUDA 12.4 |

### 6.3 What we already did for training

- CTDE: shared GRU actor (local obs + seat embed) + centralized critic (full stacked state at train time)  
- All-seat rotation through one shared policy (sample-efficient vs 6 independent nets)  
- Population league: heuristic bots + periodic frozen checkpoint opponents  
- Skill-gap / exploitability benchmarks to separate “got better” from “beat this bot roster”  
- CTDE torch GPU: parallel rollouts, batched PPO on CUDA, resume from numpy checkpoints  
- Policy-driven negotiation (6 discrete negotiation actions)  
- Live dashboard for monitoring  

### 6.4 Realistic training targets (post 5k run)

| Metric | Pre-5k | Post-5k (5k ep) | Reasonable target |
|--------|--------|-----------------|-------------------|
| League WR (benchmark) | 15% | **24%** | 25–40% |
| Skill gap vs fair share | −1.7% | **+7.3%** | >0% sustained |
| Train win rate MA50 | 12% | 12% | 25–40% (in-training) |
| Exploitability | 0.76 | 0.64 | Lower = less counterable |

---

## 7. PRD milestone checklist

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0 | Core engine | **Done** |
| M1 | Effects + 54 cards | **Done** |
| M2 | Negotiation | **Done** |
| M3 | PettingZoo env | **Done** (incremental stepping) |
| M4 | Baseline PPO | **Done** — numpy + torch CTDE GRU |
| M5 | League training | **Done** — heuristics + smart choices |
| M6 | Analytics pipeline | **Done** — sweep, tune, sign-off, viewer |
| M6b | Replay viewer | **Partial** — browser timeline + CLI |
| M7 | Kingmaker validation | **Done** — synthetic A/B passes |
| M8 | Full balance pass | **Done** — 5/5 sign-off gates at 385 games on current deck (`phase_c_ready: true`, 2026-07-06) |
| M4 scale | 5k+ CTDE PPO training | **Pipeline validated** — fresh training pending on card set `af4e2166dbec6af5` |

---

## 8. What is left to build

### 8.1 Balance / design (blocking print & Phase C)

- [x] Seat win spread ≤ 20% at 385 games (**4.9%** latest)  
- [x] Role win rate **35–45%** started-as-King (**37.9%** latest 385-game)  
- [x] Shield hit rate **25–70%** at 385 games (**34.6%**)  
- [x] Assisted win rate ≤ **12%** at 385 games (**10.6%**, person-matched)  
- [x] Role-normalized card win contribution  
- [x] Rotate starting King without changing start gold  
- [x] Full 385-game sign-off (`make signoff --no-tune`) — **5/5 gates** (2026-07-06, post-stub design)  
- [x] Stub card design pass — 16 resize placeholders → real PRD §10/§11 cards (`make replace-stubs`)

### 8.2 Engine / analytics

- [x] Per-negotiation-phase gift cap  
- [x] Bilateral trade gift cap (`max_negotiation_gift_per_trade`)  
- [x] Per-seat trade limit (`max_negotiation_trades_per_phase`)  
- [x] Tighter assisted-win metric (person-matched `to_person == winner_person`; legacy seat rate in diagnostics)  
- [ ] Pick-rate denominator (eligible hands, not just reveal count)  
- [x] Exploitability bot + skill-gap metric (`training/benchmark.py`, `make benchmark`)  
- [ ] Parquet / full game log export for large sweeps  

### 8.3 ML — Phase C entry (all required before 5k+ episodes)

- [x] **385-game gates:** assisted ≤12%, shield 25–70% (see §9 table)  
- [x] **Assisted-win mechanics** (bilateral cap, metric, bot volume)  
- [x] **Richer observation space** (48-dim; hand, opponent gold, negotiation flags)  
- [x] **Reward shaping toggle** — wired; **off** for sweeps/signoff  
- [x] **CTDE** — shared actor + seat embedding + centralized critic (`training/ctde_policy.py`)  
- [x] **Benchmarks** — skill gap + exploitability before scale  
- [x] **Population league** — frozen checkpoints mixed with heuristics  
- [x] Long runs (5k+ episodes) — **5000 ep GPU run complete** (2026-07-06)  
- [x] PyTorch PPO + GPU — `training/ctde_policy_torch.py`, parallel rollouts  

### 8.4 Product / viewer

- [ ] Balance tab: role-normalized card charts  
- [x] Training tab: per-seat graphs, loss curves, skill-gap chart (2026-07-06)  
- [ ] Export PDF balance report from viewer  

---

## 9. What to do next (prioritized roadmap)

### Phases 1–6 roadmap (2026-07-06)

| Phase | Status | Notes |
|-------|--------|-------|
| 1–3 Baseline | **Done** | Signoff 5/5 pre-expansion; `benchmark_pre_train.json` saved |
| 3.5 Live viewer | **Done** | Skill-gap, exploit gap, per-seat bars, loss MA20 in Live Training tab |
| 4 Exploratory 10k | **Partial** | Started ep 0; stopped ~ep 248 when grid locked config |
| 5a Card expansion | **Done** | +15 King / +15 Noble (`3829e707413b8f83`) |
| 5b Grid infra | **Done** | Parallel sweeps, deck subset, succession metrics, `parameter_grid.py` |
| 5c Parameter grid | **Done** | Winner: **n_rounds=4, king_deck_size=42, noble_deck_size=40** (5/5 at confirm) |
| 6 Scale training | **Running** | 20k CTDE ep 0, `benchmark_every=5000`, live viewer on, 2 rollout workers |

**Locked print parameters** (in `configs/balance.yaml` + `configs/training.yaml`):

- `n_rounds: 4`, `king_deck_size: 42`, `noble_deck_size: 40`
- Re-signoff at locked cell: **4/5** (King role 34.3% — borderline; grid confirm was 5/5)

Watch training: `cd viewer && npm run dev` → Live Training tab, or `viewer/public/training/live.json`.

### Phase A — Fix King dominance — **COMPLETE (2026-07-05)**

1. Added `random_starting_king_seat: true` to balance + training configs.  
2. **Did not change** `king_start_gold` / `noble_start_gold` (mandated locked at 1000/600).  
3. King **3 plays / 3 redraw** and Noble **2/2** restored as locked core rules (not balance knobs).  
4. Card nerfs (King economy) + Noble catch-up buffs via `make nerf-outliers` + auto-tune role loop.  
5. Re-ran `make signoff` — **385-game started-as-King win rate: 41.8%** with King 3/3 (target 35–45%).

### Phase B — Fix mechanic bugs + instrument — **COMPLETE (2026-07-05)**

**Do not start Phase C (training scale) or PRD n_rounds/deck-size sweeps until all 5 sign-off gates pass.** Two failing gates are mechanic bugs, not numeric tuning problems.

#### B1. Instrument — **done (2026-07-05)**

- `analytics/diagnostics.py` + `game_logs/diagnostics.json` on every sweep/signoff
- `metrics.diagnostics`, `assisted_win_modes`, `shield_by_card`, `whiff_reasons`, `trigger_types`
- `shield_block_rate` separate from `shield_hit_rate`; `make diagnostics` to print latest

#### B2. Shield mechanic — **partial fix landed (2026-07-05)**

Root cause was **structural**, not bot stupidity:

- Protection used retrospective `attacked_this_phase` at reveal time; King always reveals first → **0% hit** on King gold shields.
- Shipped cards never wired the `attacker_is` guess loop; Bodyguard blocked wrong attack type.

**385-game sign-off (2026-07-05, `--no-tune`, after B7 + card re-apply):** shield hit **26.4%**, role King **38.2%**, seat spread **4.4%**, assisted **9.9%** — **5/5 gates**, `phase_c_ready: true`.

**Shipped in B7:** negotiation-informed protection play (default theft target); alliance accept checks `targets` list; bilateral + per-trade caps; person-matched assisted gate; bot negotiation volume reduction.

#### B3. Assisted wins — **partial fix landed (2026-07-05)**

Root cause: **synthetic A/B tests succession only**; sweep metric counts **any** `gold_gifted` to winner’s seat (~31% → ~26% after fixes).

- Per-negotiation-phase gift cap (`max_negotiation_gift_per_phase: 180`) — was per-trade only.
- `gold_transfer` no longer launders gifted → earned on receiver.
- `gold_gifted` events now include `from_person` / `to_person`.

**Still optional:** `attacker_is` + choice on Customs Seal for targeted noble shields; `assisted_win_strict` analytics filter.

#### B4. Seat spread artifact — **partial fix landed**

Seat 3 (0.5% wins) vs seat 4 (34.5%) was **not** a turn-order bug:

- Fixed `seat_bots` pinned `exploit` (random play) on seat 3 and `hoard` on seat 4 every game.
- `_default_target` always picked lowest-index noble → seat 4 never default-targeted.

**Fix applied:** rotate `seat_bots` per game in sweeps; default target uses `noble_play_order()[0]`. Post-fix seat spread ≈ **13–21%** per seat (much flatter).

#### B5. Role-normalized card win contribution — **done (2026-07-05)**

- `metrics.card_win_contribution_by_role` — split by King/Noble **at play time** (tracks succession)
- Exported to viewer as `card_contributions_by_role` — use before any further manual nerfs

#### B6. Re-run signoff — **done (2026-07-06, post-stub design)**

`make signoff` uses `--no-tune` (mechanic validation, not card mutation). **Current** 385-game diagnostics on card set `af4e2166dbec6af5`:

| Gate | Result | Pass? |
|------|--------|-------|
| Sample ≥385 | 385 | Yes |
| Role win 35–45% | **37.9%** King | Yes |
| Seat spread ≤20% | **4.9%** | Yes |
| Shield hit 25–70% | **34.6%** | Yes |
| Assisted ≤12% | **10.6%** | Yes |

*Prior 2026-07-05 sign-off (card set `1387a23db64e03da`, pre-stub): 38.2% King, 26.4% shield, 9.9% assisted — superseded by stub redesign.*

Assisted-win modes (counts): `ascended_noble_received_gifts` 28, `starting_king_received_gifts` 15, `multi_trade_stacking` 6.

**Phase C training scale unblocked** on the **current** deck after stub design + re-signoff (`phase_c_ready: true`). Prior 5k checkpoint is **invalid** for the new card set.

#### B7. Assisted-win mechanics — **done (2026-07-05)**

- [x] **Bilateral trade gift cap** — `max_negotiation_gift_per_trade` + shared per-side budget in `_execute_trade`  
- [x] **Tighter assisted-win metric** — person-matched gate; legacy seat rate retained for diagnostics  
- [x] **Bot negotiation volume** — lower aggressive requests, tighter exploit accept, alliance `targets` fix  
- [x] **`max_negotiation_trades_per_phase`** — limits trade stacking per seat per negotiation phase  

### Phase C entry requirements (mandatory — do not start 5k+ episodes until ALL checked)

Training against a broken shield mechanic (~2% hit before fix; noble cards still ~3% hit) or leaky assisted wins (~23%) teaches agents to **exploit the bug**, not play well. A 5k run on a 32-dim observation missing shield/negotiation signal is compute on the wrong bottleneck. Wire reward shaping **before** scale, not after.

| # | Requirement | Rationale | Status |
|---|-------------|-----------|--------|
| 1 | **385-game assisted win ≤ 12%** | `make signoff --no-tune`; person-matched metric | **10.6%** — pass |
| 2 | **385-game shield hit 25–70%** | PRD band | **34.6%** — pass |
| 3 | **385-game role 35–45%, seat spread ≤20%** | Fair simulation baseline | **pass** (37.9%, 4.9%) |
| 4 | **Assisted-win mechanics done** (B7) | Bilateral cap, metric, bots | **Done** |
| 5 | **Richer observation space** | Hand categories, opponent gold, negotiation flags | **Done** (48-dim) |
| 6 | **Reward shaping toggle** | Config flag; **off** for sweeps/signoff | **Done** |
| 7 | Re-run `make signoff` after stub design | All five sign-off gates green on current deck | **Done** — `phase_c_ready: true` (2026-07-06) |

**Phase C training scale is unblocked on the current deck.** Start fresh training from ep 0; do not resume the pre-stub 5k checkpoint.

### Phase C — Training scale — **PIPELINE VALIDATED; FRESH RUN PENDING (2026-07-06)**

The 5k GPU CTDE run exercised the training stack (torch CUDA, parallel rollouts, league, benchmarks). It trained on card set `1387a23db64e03da` **before** the stub design pass. Checkpoint `policy_ep005000.json` and pre/mid/post benchmark JSONs are **historical pipeline artifacts only** — do not resume from them.

**Pipeline validation results (stale card set, untrained→5k policy):**

| Eval | League WR | Skill gap | Exploit WR | `exploitability_gap` |
|------|-----------|-----------|------------|----------------------|
| Pre-5k | 15% | −1.7% | — | — |
| Mid ep 1750 | 20% | +3.3% | — | — |
| Post ep 5000 | ~24% | +7–9% | — | — |

**Exploit roster semantics (`training/benchmark.py`):** `exploit` mode sets **every seat** to the `exploit` heuristic (trade-friendly, safe-random play) — not a Nash best-response. `exploitability_gap = league_WR − exploit_WR`. **Positive** means the mixed league is harder than all-exploit; **negative** means all-exploit is easier (seen mid-run when exploit WR exceeded league WR). `exploitability = max(0, (1 − exploit_WR) − league_WR)` is a coarse proxy, not CFR exploitability.

**Fresh baseline after stub redesign (untrained policy, card set `af4e2166dbec6af5`, 100-game eval):**

| Metric | Value | Direction check |
|--------|-------|-----------------|
| League WR | 18% | — |
| Exploit WR | 13% | — |
| `exploitability_gap` | **+5%** | Positive — exploit roster harder than league (expected) |
| Skill gap vs fair share | +1.3% | — |

Saved: `game_logs/training/benchmark_post_stubs.json`.

**Next for real training:**

1. `make signoff --no-tune` — must stay **5/5** (current: **yes**, see §9 table below).  
2. `make benchmark` — establish pre-training baseline on current card set.  
3. `make train-gpu` from **episode 0** (do not resume `policy_ep005000.json`).  
4. Periodic `make benchmark` during scale.

```bash
make replace-stubs   # re-apply stub card definitions from script
make signoff         # 100 + 385 compare (--no-tune)
make benchmark       # skill gap + exploitability on current card set
make train-gpu       # fresh CTDE run after signoff green
```

Measurement runs (balance, signoff, skill-gap) always use **reward_shaping: false**.

### Phase D — Print readiness (ongoing)

Role-normalized nerfs, flavor pass, full PRD parameter sweep.

---

## 10. Commands reference

```bash
# Setup
cd crown-and-court
.venv\Scripts\activate
pip install -e ".[dev]"

# After card add/edit/delete
python scripts/card_workflow.py           # manifest + validate + tests + signoff + export
python scripts/card_workflow.py --quick   # manifest + validate + tests only
python scripts/card_workflow.py --card-id king_royal_edict_25_025 --tune   # tune ONE card only
python -m analytics.card_balance --card-id ID              # isolated diagnostics for one card
python -m analytics.card_balance --save-baseline --games 385   # snapshot after signoff passes
make save-baseline                        # same as above (requires make on PATH)

# Scoped tuning never changes other cards. Save a baseline when the deck is green so
# --tune can auto-detect which single card you edited. Global deck tuning: make balance

# Validate & test
python -m engine.validate
pytest -q

# Balance
make sweep                    # 100-game league sweep + diagnostics.json
make tune-shield             # targeted shield balance pass + signoff
make signoff                  # 100 + 385 compare (--no-tune)
make diagnostics              # print diagnostics from last sweep
make balance                  # auto-tune pipeline (card mutation — use sparingly in Phase B)
make nerf-outliers            # manual card nerfs
make kingmaker                # synthetic kingmaker A/B
make export-balance           # refresh viewer JSON

# Decks
make resize-decks             # 30 unique King + 40 unique Noble (1 copy each)
make replace-stubs            # apply PRD §10/§11 stub card designs

# Training (CTDE — policy_backend: torch in configs/training.yaml)
python -m training.trainer --episodes 3250 --start-episode 1750 --no-live
make train-gpu              # resume GPU run per training.yaml
make train-quick            # 20 episodes smoke test (training_test.yaml)
make benchmark              # skill gap + exploitability
python -m training.benchmark --games 100 --checkpoint game_logs/training/checkpoints/policy_ep005000.json

# Viewer
cd viewer && npm run dev      # http://localhost:5173
```

---

## 11. Key artifact paths

| File | Contents |
|------|----------|
| `game_logs/sweep_result.json` | Latest 385-game metrics |
| `game_logs/signoff_comparison.json` | 100 vs 385 comparison |
| `game_logs/kingmaker_ab.json` | Gift ascension A/B |
| `game_logs/tune_result.json` | Auto-tune passes + card changes |
| `game_logs/balance_history.db` | SQLite sweep history |
| `viewer/public/balance/summary.json` | Gallery Balance tab data |
| `viewer/public/training/live.json` | Live Training tab data |
| `game_logs/training/benchmark.json` | Latest skill-gap / exploitability eval |
| `game_logs/training/benchmark_post_stubs.json` | Post-stub-design baseline (untrained policy) |
| `game_logs/training/benchmark_pre_5k.json` | Pre-training baseline (**stale** card set) |
| `game_logs/training/benchmark_mid_1750.json` | Mid-run ep 1750 (**pipeline validation only**) |
| `game_logs/training/benchmark_post_5k.json` | Post-training ep 5000 (**pipeline validation only**) |
| `game_logs/training/checkpoints/policy_ep005000.json` | 5k torch checkpoint (**invalid** after stub redesign) |
| `viewer/public/replay/sample.json` | Last game event log |
| `configs/balance.yaml` | Sim parameters + seat bots |
| `configs/training.yaml` | Training parameters |
| `configs/balance_targets.yaml` | Gate thresholds, **locked_rules**, **`phase_c_requires`** |

---

## 12. Summary one-liner

**Balance re-signed off on current singleton deck.** Card set `af4e2166dbec6af5`: 16 stubs → real PRD cards; **5/5 gates** (`phase_c_ready: true`). 5k GPU run was **pipeline validation only** on prior card set — start fresh training + benchmark from `benchmark_post_stubs.json`. Next: ep 0 CTDE scale, optional 20k+, Phase D print readiness.
