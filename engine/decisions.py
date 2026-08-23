from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from engine.card_text import describe_card_full_lines
from engine.effects.interpreter import resolve_card
from engine.negotiation import pass_action, random_negotiation_policy
from engine.phases import (
    _cards_to_play,
    _default_target,
    card_requires_chosen_target,
    draw_to_hand,
    legal_card_targets,
    run_succession_check,
    setup_game,
)
from engine.rng import GameRNG
from engine.state import GameState, Phase


class DecisionType(str, Enum):
    NEGOTIATION = "negotiation"
    PLAY = "play"
    TARGET = "target"
    DISCARD = "discard"
    CHOICE = "choice"
    REVEAL = "reveal"
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
        self._deferred_reveal: dict[str, Any] | None = None

    def reset(self) -> GameState:
        self.state = setup_game(self.config, self.rng)
        self._neg_tick = 0
        self._neg_seat_idx = 0
        self._played_buffer = []
        self._play_reveal_idx = 0
        self._phase_stage = "negotiation"
        self._deferred_reveal = None
        self._reset_negotiation_tracking()
        self._build_negotiation_queue()
        return self.state

    def _reset_negotiation_tracking(self) -> None:
        """Clear pending deals and per-phase gift/trade caps for a fresh negotiation."""
        assert self.state
        self.state.pending_proposals = []
        self.state.negotiation_gift_sent = {}
        self.state.negotiation_cards_sent = {}
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
            event_start = len(self.state.event_log)
            resolve_card(
                self.state,
                card,
                card_seat,
                self.rng,
                target_seat=target,
                selected_choice=choice,
            )
            self.state.seats[card_seat].discard.append(card)
            effects = self.state.event_log[event_start:]
            self.queue.pop(0)
            self._finish_card_resolution(card, card_seat, target, effects, selected_choice=choice)
        elif dec.dtype == DecisionType.TARGET:
            legal = list(dec.context.get("legal_targets") or [])
            target = int(action)
            if legal and target not in legal:
                target = legal[action % len(legal)] if legal else target
            card = dec.context["card"]
            card_seat = int(dec.context.get("card_seat", dec.seat))
            self.queue.pop(0)
            self._continue_reveal_with_target(card, card_seat, target)
        elif dec.dtype == DecisionType.DISCARD:
            if action_handler:
                action_handler(self.state, dec.seat, action, self.rng)
            else:
                self._apply_discard_indices(dec, [action])
            self.queue.pop(0)
            if self.state.pending_discards:
                self._queue_next_discard()
            elif self._deferred_reveal:
                self._emit_deferred_reveal()
            else:
                self._resolve_next_reveal()
        elif dec.dtype == DecisionType.REVEAL:
            self.queue.pop(0)
            if self.state:
                self.state.private_peeks.clear()
            self._resolve_next_reveal()

        if not self.queue and not self.done:
            self._advance_phase()
        return self.state

    def _pause_reveals(self) -> bool:
        return bool(self.config.get("pause_between_reveals"))

    def _reveal_decision(
        self,
        card: dict[str, Any],
        card_seat: int,
        target_seat: int | None,
        effects: list[dict[str, Any]],
        selected_choice: str | None = None,
    ) -> PendingDecision:
        return PendingDecision(
            seat=card_seat,
            dtype=DecisionType.REVEAL,
            context={
                "card": copy.deepcopy(card),
                "card_seat": card_seat,
                "target_seat": target_seat,
                "index": self._play_reveal_idx,
                "total": len(self._played_buffer),
                "effects": copy.deepcopy(effects),
                "effect_lines": describe_card_full_lines(card),
                "selected_choice": selected_choice,
            },
        )

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
        self.state.private_peeks.clear()
        self.state.pending_discards.clear()
        self._deferred_reveal = None
        self.state.log_event(
            "card_revealed",
            seat=seat,
            card_id=card.get("id"),
            name=card.get("name"),
        )

        # Interactive tables: card player picks the opponent. Training keeps auto-target.
        if self._pause_reveals() and card_requires_chosen_target(card):
            legal = legal_card_targets(self.state, seat)
            self.queue = [
                PendingDecision(
                    seat=seat,
                    dtype=DecisionType.TARGET,
                    context={
                        "card": copy.deepcopy(card),
                        "card_seat": seat,
                        "legal_targets": legal,
                        "index": self._play_reveal_idx + 1,
                        "total": len(self._played_buffer),
                        "effect_lines": describe_card_full_lines(card),
                    },
                )
            ]
            return

        target = _default_target(self.state, seat, card)
        self._continue_reveal_with_target(card, seat, target)

    def _continue_reveal_with_target(
        self, card: dict[str, Any], seat: int, target: int
    ) -> None:
        assert self.state
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
                            "card": copy.deepcopy(card),
                            "options": choices,
                            "target_seat": target,
                            "card_seat": seat,
                            "index": self._play_reveal_idx + 1,
                            "total": len(self._played_buffer),
                            "effect_lines": describe_card_full_lines(card),
                            "choice_seat_role": params.get("choice_seat", "self"),
                        },
                    )
                ]
                return

        event_start = len(self.state.event_log)
        resolve_card(self.state, card, seat, self.rng, target_seat=target)
        self.state.seats[seat].discard.append(card)
        effects = self.state.event_log[event_start:]
        self._finish_card_resolution(card, seat, target, effects)

    def _finish_card_resolution(
        self,
        card: dict[str, Any],
        card_seat: int,
        target: int | None,
        effects: list[dict[str, Any]],
        selected_choice: str | None = None,
    ) -> None:
        assert self.state
        self._deferred_reveal = {
            "card": copy.deepcopy(card),
            "card_seat": card_seat,
            "target": target,
            "effects": copy.deepcopy(effects),
            "selected_choice": selected_choice,
        }
        if self.state.pending_discards:
            self._queue_next_discard()
            return
        self._emit_deferred_reveal()

    def _queue_next_discard(self) -> None:
        assert self.state
        if not self.state.pending_discards:
            self._emit_deferred_reveal()
            return
        req = self.state.pending_discards[0]
        seat = int(req["seat"])
        count = int(req["count"])
        hand = self.state.seats[seat].hand
        count = min(count, len(hand))
        if count <= 0:
            self.state.pending_discards.pop(0)
            self._queue_next_discard()
            return
        req["count"] = count
        deferred = self._deferred_reveal or {}
        self.queue = [
            PendingDecision(
                seat=seat,
                dtype=DecisionType.DISCARD,
                context={
                    "count": count,
                    "card": deferred.get("card"),
                    "card_seat": deferred.get("card_seat"),
                    "target_seat": deferred.get("target"),
                    "index": self._play_reveal_idx + 1,
                    "total": len(self._played_buffer),
                    "effect_lines": describe_card_full_lines(deferred["card"])
                    if deferred.get("card")
                    else [],
                },
            )
        ]

    def _apply_discard_indices(self, dec: PendingDecision, indices: list[int]) -> None:
        assert self.state
        seat = dec.seat
        hand = self.state.seats[seat].hand
        count = int(dec.context.get("count", 1))
        cleaned = sorted({int(i) for i in indices if 0 <= int(i) < len(hand)})[:count]
        while len(cleaned) < count and len(cleaned) < len(hand):
            for i in range(len(hand)):
                if i not in cleaned:
                    cleaned.append(i)
                if len(cleaned) >= count:
                    break
        discarded = []
        for idx in sorted(cleaned, reverse=True):
            card = self.state.seats[seat].hand.pop(idx)
            self.state.seats[seat].discard.append(card)
            discarded.append(
                {
                    "id": card.get("id"),
                    "name": card.get("name"),
                    "category": card.get("category"),
                }
            )
        if self.state.pending_discards:
            self.state.pending_discards.pop(0)
        self.state.log_event(
            "force_discard",
            seat=seat,
            count=len(discarded),
            discarded=discarded,
        )
        if self._deferred_reveal is not None:
            self._deferred_reveal["effects"] = list(self._deferred_reveal.get("effects") or []) + [
                {
                    "type": "force_discard",
                    "seat": seat,
                    "count": len(discarded),
                    "discarded": discarded,
                    "round": self.state.current_round,
                    "phase": self.state.phase.value,
                }
            ]

    def _emit_deferred_reveal(self) -> None:
        assert self.state
        deferred = self._deferred_reveal
        self._deferred_reveal = None
        self._play_reveal_idx += 1
        if not deferred:
            self._resolve_next_reveal()
            return
        if self._pause_reveals():
            self.queue = [
                self._reveal_decision(
                    deferred["card"],
                    deferred["card_seat"],
                    deferred.get("target"),
                    deferred.get("effects") or [],
                    selected_choice=deferred.get("selected_choice"),
                )
            ]
            return
        self.state.private_peeks.clear()
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
