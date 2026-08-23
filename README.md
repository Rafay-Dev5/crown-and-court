# Crown & Court

Simulation and balance lab for the Crown & Court political card game.

## Quick start

```bash
cd crown-and-court
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -e ".[dev]"

# Validate cards
python -m engine.validate

# Run a game
python -m engine.play --seed 42 --players 6 --rounds 3

# Run tests
pytest

# Card gallery + live training dashboard
cd viewer && npm install && npm run dev
# Open "Live Training" tab, then in another terminal:
python -m training.trainer --episodes 200

# Adding new cards — see docs/ADDING_CARDS.md
```

## Layout

- `engine/` — pure rules engine (no RL deps in core)
- `cards/` — JSON card definitions + schema
- `env/` — PettingZoo wrapper
- `agents/` — heuristic bots + optional LLM negotiator
- `training/` — PPO league training
- `analytics/` — sweeps and balance reports
- `viewer/` — local read-only card gallery
