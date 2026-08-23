# Agent Handoff — Crown & Court

Pass this file between Cursor agents (or humans) at session boundaries. **Update the "Current session" section before you stop.**

**Quick links:**

- Build guide: [`.cursor/ml_engineer.md`](../.cursor/ml_engineer.md)
- Status snapshot: [`PROJECT_STATUS.md`](PROJECT_STATUS.md)
- Environment PRD: [`../prd_rl_agents.md`](../prd_rl_agents.md)
- Card PRD: [`../prd_card_design.md`](../prd_card_design.md)

---

## Project one-liner

Multi-agent card game **balance lab** in `crown-and-court/` — Python engine + JSON cards + RL analytics + React card gallery. Not a consumer game client.

---

## Current session

| Field | Value |
|-------|-------|
| **Date** | 2026-07-05 |
| **Agent / human** | Phase A balance session |
| **Branch** | (not tracked — initialize git if needed) |
| **Card set version** | `7b01aa4e0329a524` |
| **Tests** | 29/29 passing (`pytest -q`) |
| **Cards valid** | Yes (`python -m engine.validate`) |

### Completed this session

- **Phase A:** `random_starting_king_seat`, play/redraw tuning, card nerfs/buffs
- **Locked start gold mandate:** 1000/600 enforced in `balance_targets.yaml`, `auto_tune.py`, configs, docs
- **385-game sign-off:** started-as-King win rate **38.7%** (target 35–45%)
- Role metrics fix: reads `starting_king_person` from `game_setup` events

### In progress

- Phase B7: assisted-win mechanics (bilateral cap, metric, bots)
- Shield hit rate to 25–70% (noble reactive cards still ~3% hit — bot/signal work)

### Phase C — do not start until ALL of the following pass

Documented in `PROJECT_STATUS.md` §9 and `configs/balance_targets.yaml` → `phase_c_requires`:

1. **385-game gates:** assisted ≤12%, shield 25–70%, role 35–45%, seat spread ≤20%  
2. **Assisted-win mechanics:** bilateral trade cap, tighter metric, bot negotiation volume  
3. **Richer observation space** (hand, opponent gold, negotiation, card IDs) — current 32-dim is insufficient for shield play  
4. **Reward shaping toggle** wired; **off** for measurement/sweeps/signoff  
5. Re-run `make signoff --no-tune` with everything green  

**Do not run 5k+ episodes or PRD n_rounds/deck sweeps until the checklist is complete.** Training on broken mechanics produces policies that exploit bugs (laundering, unguessable shields), not skill.

### Blocked / needs human decision

- Whether to init git repo and remote
- OpenAI API key for LLM negotiator playtests
- Whether further card-only tuning is needed to hold role win rate at 35–45% with King 3/3 restored

### Balance rules agents must not change

**Never modify `king_start_gold`, `noble_start_gold`, `king_plays_per_round`, or `king_redraw` for balance.** Use cards, negotiation caps, bot assignment instead. See `configs/balance_targets.yaml` → `locked_rules`.

---

## Where things live

```
engine/          Rules only — no torch/gym imports
cards/           JSON + schema.json + manifest.json
env/             crown_court_env.py (PettingZoo)
agents/          llm_negotiator.py
training/        ppo.py, league_trainer.py
analytics/       metrics, sweeps, reports, replay
viewer/          React card gallery (port 5173)
configs/         balance.yaml | playtest.yaml
tests/           18 tests — run before every change
```

---

## How to verify health

```bash
cd crown-and-court
.venv\Scripts\activate
pytest -q
python -m engine.validate
python -m engine.play --seed 42 --players 4 --rounds 2
```

Expected: all tests green, cards valid, game completes with winner logged.

---

## Architecture constraints (do not violate)

1. **Single RNG** per game — `GameRNG(seed=...)`
2. **Cards are data** — effects via primitive strings only
3. **Balance runs** use `configs/balance.yaml` — no LLM seat, no shaped rewards
4. **Playtest runs** use `configs/playtest.yaml`
5. **Schema changes** → update both PRDs + `engine/validate.py` + viewer `App.tsx` primitive list
6. **Protection cards** require `on_whiff_penalty` in JSON
7. **Sweep outputs** must record `card_set_version` from `cards/manifest.json`

---

## Recommended next tasks (priority order)

1. **PettingZoo env** — incremental `step()` for negotiation + playing + dice choices  
   Files: `env/crown_court_env.py`, new `tests/test_env.py`

2. **Expand cards** to ~24 King / ~30 Noble — fill category gaps (viewer **Category Gaps** tab)  
   Files: `cards/king_deck/*.json`, `cards/noble_deck/*.json`

3. **Real PPO** — CleanRL-style trainer, terminal sparse reward  
   Files: `training/ppo.py`, `training/league_trainer.py`

4. **M7 kingmaker test** — gift scenario script + assisted-win A/B  
   Files: `analytics/kingmaker_test.py` (new), `configs/balance.yaml`

5. **Ablation CLI** — remove one card, re-sweep, diff report  
   Files: `analytics/sweeps.py`

---

## Key APIs

```python
from engine.cards import load_config
from engine.phases import run_game, random_play_policy, random_choice_policy
from engine.negotiation import random_negotiation_policy
from engine.rng import GameRNG

config = load_config("configs/balance.yaml")
state = run_game(config, GameRNG(seed=42),
                 random_negotiation_policy,
                 random_play_policy,
                 random_choice_policy)
# state.event_log — structured JSON-serializable events
# state.king_seat — winning seat at game end
```

---

## Event log types (for replay / metrics)

Common events: `game_setup`, `round_start`, `negotiation_complete`, `propose_conditional`, `gold_gifted`, `card_revealed`, `choice_made`, `dice_roll`, `shield_blocked`, `protection_hit`, `protection_whiff`, `succession`, `game_end`.

Replay: `python -m analytics.replay <file.jsonl>`

---

## Handoff checklist

When **ending** your session, update this file:

- [ ] Fill **Current session** table (date, agent, tests, card version)
- [ ] List **Completed** and **In progress** bullets
- [ ] Note any **Blocked** items for human input
- [ ] Update [`PROJECT_STATUS.md`](PROJECT_STATUS.md) if milestone status changed
- [ ] Run `pytest -q` and record pass/fail count
- [ ] Run `make manifest` if cards changed

When **starting** your session:

- [ ] Read this file + `ml_engineer.md` + `PROJECT_STATUS.md`
- [ ] Run health checks above
- [ ] Confirm `card_set_version` matches `cards/manifest.json`

---

## Contact / context

- Game: **Crown & Court** — 1 King, 3–7 Nobles, negotiation + blind card play + succession
- Design pillars: skill + luck, King/Noble asymmetry, negotiation has teeth, controlled kingmaking
- Physical rule for dice: d6, threshold on card, success/failure branches

---

*End of handoff — append session notes below if needed.*

### Session notes

_(Next agent: add dated notes here.)_
