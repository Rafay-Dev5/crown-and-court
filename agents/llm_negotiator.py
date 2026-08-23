from __future__ import annotations

import json
import os
from typing import Any

from engine.negotiation import (
    accept_proposal,
    pass_action,
    propose_alliance,
    propose_conditional,
    propose_trade,
)
from engine.rng import GameRNG
from engine.state import GameState


def llm_negotiation_policy(state: GameState, seat: int, rng: GameRNG) -> None:
    """Optional LLM seat — playtest mode only. Falls back to heuristics without API key."""
    if not state.config.get("playtest_mode"):
        pass_action(state, seat)
        return

    llm_seat = state.config.get("llm_negotiator_seat")
    if llm_seat is not None and seat != llm_seat:
        pass_action(state, seat)
        return

    api_key = os.environ.get("OPENAI_API_KEY")
    others = [s for s in range(state.num_players) if s != seat]
    if not others:
        pass_action(state, seat)
        return
    target = rng.choice(others)

    if api_key:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
            prompt = (
                "You are negotiating in Crown & Court. Anyone can promise anything, anyone can break it. "
                "Respond with JSON: {\"action\": \"trade|conditional|alliance|pass\", "
                "\"offer\": {\"gold\": N}, \"condition\": {\"type\": \"no_attack\", \"target\": seat}} "
                f"State: round={state.current_round}, your_seat={seat}, target={target}"
            )
            resp = client.chat.completions.create(
                model=state.config.get("llm_model", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            action_data = json.loads(resp.choices[0].message.content or "{}")
            action = action_data.get("action", "pass")
            if action == "conditional":
                propose_conditional(
                    state,
                    seat,
                    target,
                    action_data.get("offer", {"gold": 50}),
                    action_data.get("condition", {"type": "no_disruption", "target": seat}),
                )
                return
            if action == "trade":
                hand = state.seats[seat].hand
                if hand:
                    propose_trade(
                        state,
                        seat,
                        target,
                        {"gold": 0, "cards": [hand[0]["id"]]},
                        {"gold": 30, "card_count": 0},
                    )
                else:
                    pass_action(state, seat)
                return
            if action == "alliance":
                propose_alliance(state, seat, [target], terms="LLM proposed pact")
                return
        except Exception as exc:
            state.log_event("llm_negotiator_error", seat=seat, error=str(exc))

    if rng.random() > 0.5:
        propose_conditional(
            state,
            seat,
            target,
            {"gold": 100},
            {"type": "no_disruption", "description": "do not play Disruption against me this round"},
        )
    else:
        pass_action(state, seat)
