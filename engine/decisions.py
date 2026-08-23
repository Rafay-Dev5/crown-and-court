from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from engine.effects.interpreter import resolve_card
from engine.negotiation import pass_action, random_negotiation_policy
from engine.phases import (
    _cards_to_play,
    _default_target,
    draw_to_hand,
    run_succession_check,
    setup_game,
)
from engine.rng import GameRNG
from engine.state import GameState, Phase


class DecisionType(str, Enum):
    NEGOTIATION = "negotiation"
    PLAY = "play"
    CHOICE = "choice"
    DONE = "done"


@dataclass
class PendingDecision:
    seat: int
    dtype: DecisionType
    context: dict[str, Any] = field(default_factory=dict)


class DecisionEngine:
    """Incremental game driver — one agent decision per env step."""

    def __init__(self, config: dict[str, Any], rng: GameRNG):
        self.config = config
        self.rng = rng
        self.state: GameState | None = None
        self.queue: list[PendingDecision] = []
        self._neg_tick = 0
        self._neg_seat_idx = 0
        self._played_buffer: list[tuple[int, dict]] = []
        self._play_reveal_idx = 0
        self._phase_stage = "negotiation"

    def reset(self) -> GameState:
        self.state = setup_game(self.config, self.rng)
        self._neg_tick = 0
        self._neg_seat_idx = 0
        self._played_buffer = []
        self._play_reveal_idx = 0
        self._phase_stage = "negotiation"
        self._reset_negotiation_tracking()
        self._build_negotiation_queue()
        return self.state

    def _reset_negotiation_tracking(self) -> None:
        """Clear pending deals and per-phase gift/trade caps for a fresh negotiation."""
        assert self.state
        self.state.pending_proposals = []
        self.state.negotiation_gift_sent = {}
        self.state.negotiation_trades_executed = {}

    def _expire_pending_proposals(self) -> None:
        """Mark leftover proposals expired when negotiation ends (cannot carry to next round)."""
        assert self.state
        for proposal in self.state.pending_proposals:
            if proposal.get("status") == "pending":
                proposal["status"] = "expired"

    @property
    def done(self) -> bool:
        return self.state is not None and self.state.phase == Phase.GAME_END

    def current_decision(self) -> PendingDecision | None:
        return self.queue[0] if self.queue else None

    def step(self, action: int, action_handler: Callable | None = None) -> GameState:
        if self.state is None:
            raise RuntimeError("Call reset() first")
        if self.done:
            return self.state

        dec = self.current_decision()
        if dec is None:
            self._advance_phase()
            return self.state

        if dec.dtype == DecisionType.NEGOTIATION:
            if action_handler:
                action_handler(self.state, dec.seat, action, self.rng)
            else:
                random_negotiation_policy(self.state, dec.seat, self.rng)
            self.queue.pop(0)
            if not self.queue and self._phase_stage == "negotiation":
                self._build_negotiation_queue()
        elif dec.dtype == DecisionType.PLAY:
            if action_handler:
                action_handler(self.state, dec.seat, action, self.rng)
            else:
                hand = self.state.seats[dec.seat].hand
                n = dec.context.get("n_play", 2)
                indices = list(range(min(n, len(hand))))
                if action < len(hand):
                    indices = [action % len(hand)]
                    for _ in range(n - 1):
                        indices.append((action + _ + 1) % len(hand))
                indices = sorted(set(indices))[:n]
                selected = [hand[i] for i in indices if i < len(hand)]
                for idx in sorted([i for i in indices if i < len(hand)], reverse=True):
                    self.state.seats[dec.seat].hand.pop(idx)
                for card in selected:
                    self._played_buffer.append((dec.seat, card))
                self.queue.pop(0)
                if not self.queue and self._phase_stage == "playing_commit":
                    self._phase_stage = "playing_reveal"
                    self._play_reveal_idx = 0
                    self._resolve_next_reveal()
        elif dec.dtype == DecisionType.CHOICE:
            card = dec.context["card"]
            card_seat = dec.context.get("card_seat", dec.seat)
            options = dec.context.get("options", [])
            choice = options[action % len(options)]["id"] if options else None
            target = dec.context.get("target_seat", card_seat)
            resolve_card(
                self.state,
                card,
                card_seat,
                self.rng,
                target_seat=target,
                selected_choice=choice,
            )
            self.state.seats[card_seat].discard.append(card)
            self.queue.pop(0)
            self._play_reveal_idx += 1
            self._resolve_next_reveal()

        if not self.queue and not self.done:
            self._advance_phase()
        return self.state

    def _build_negotiation_queue(self) -> None:
        assert self.state
        ticks = int(self.state.config.get("negotiation_ticks", 4))
        order = self.state.seat_order_from_king()
        if self._neg_tick >= ticks:
            self.queue = []
            return
        if self._neg_seat_idx >= len(order):
            self._neg_tick += 1
            self._neg_seat_idx = 0
            if self._neg_tick >= ticks:
                self.queue = []
                return
        seat = order[self._neg_seat_idx]
        self.queue = [PendingDecision(seat=seat, dtype=DecisionType.NEGOTIATION)]
        self._neg_seat_idx += 1

    def _build_play_queue(self) -> None:
        assert self.state
        self.state.phase = Phase.PLAYING
        self.state.phase_attacks = []
        order = [self.state.king_seat] + self.state.noble_play_order()
        self.queue = []
        for seat in order:
            n = _cards_to_play(self.state, seat)
            if n > 0 and self.state.seats[seat].hand:
                self.queue.append(
                    PendingDecision(
                        seat=seat,
                        dtype=DecisionType.PLAY,
                        context={"n_play": n},
                    )
                )
        self._phase_stage = "playing_commit"
        self._played_buffer = []

    def _resolve_next_reveal(self) -> None:
        assert self.state
        if self._play_reveal_idx >= len(self._played_buffer):
            hand_size = int(self.state.config.get("hand_size", 8))
            for seat in range(self.state.num_players):
                redraw = 3 if seat == self.state.king_seat else 2
                draw_to_hand(self.state, seat, redraw, self.rng, hand_size)
            from engine.status_ticks import apply_status_tick_effects

            apply_status_tick_effects(self.state, self.rng)
            self.state.tick_statuses()
            self.queue = []
            return

        seat, card = self._played_buffer[self._play_reveal_idx]
        self.state.log_event(
            "card_revealed",
            seat=seat,
            card_id=card.get("id"),
            name=card.get("name"),
        )
        target = _default_target(self.state, seat, card)
        effect = card.get("effect", {})
        if effect.get("primitive") == "dice_swing":
            choices = (effect.get("params") or {}).get("choices", [])
            if choices:
                params = effect.get("params") or {}
                choice_seat = target if params.get("choice_seat") == "target" else seat
                self.queue = [
                    PendingDecision(
                        seat=choice_seat,
                        dtype=DecisionType.CHOICE,
                        context={
                            "card": card,
                            "options": choices,
                            "target_seat": target,
                            "card_seat": seat,
                        },
                    )
                ]
                return

        resolve_card(self.state, card, seat, self.rng, target_seat=target)
        self.state.seats[seat].discard.append(card)
        self._play_reveal_idx += 1
        self._resolve_next_reveal()

    def _advance_phase(self) -> None:
        assert self.state
        if self._phase_stage == "negotiation":
            self._expire_pending_proposals()
            self.state.log_event("negotiation_complete")
            run_succession_check(self.state)
            self._build_play_queue()
            if not self.queue:
                run_succession_check(self.state)
                self._next_round_or_end()
        elif self._phase_stage in ("playing_commit", "playing_reveal"):
            run_succession_check(self.state)
            self._next_round_or_end()

    def _next_round_or_end(self) -> None:
        assert self.state
        if self.state.current_round >= self.state.n_rounds:
            self.state.phase = Phase.GAME_END
            self.state.log_event(
                "game_end",
                winner_seat=self.state.king_seat,
                winner_person=self.state.seats[self.state.king_seat].person_id,
            )
            self.queue = []
            return
        self.state.current_round += 1
        if self.state.config.get("alternate_turn_direction", True):
            self.state.turn_direction = 1 if self.state.current_round % 2 == 1 else -1
        self.state.phase = Phase.NEGOTIATION
        self._neg_tick = 0
        self._neg_seat_idx = 0
        self._phase_stage = "negotiation"
        self._reset_negotiation_tracking()
        self.state.log_event("round_start", round=self.state.current_round)
        self._build_negotiation_queue()
