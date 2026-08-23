from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from engine.cards import load_config
from engine.decisions import DecisionEngine, DecisionType, PendingDecision
from engine.negotiation import (
    accept_proposal,
    pass_action,
    propose_alliance,
    propose_conditional,
    propose_trade,
    reject_proposal,
    threaten,
)
from engine.rng import GameRNG
from engine.state import GameState, Role

from web.server.protocol import (
    DecisionInfo,
    PrivateGameState,
    PublicGameState,
    PublicSeatState,
    PublicStatus,
)


@dataclass
class HumanAction:
    action_type: str
    payload: dict[str, Any] = field(default_factory=dict)


def default_web_config() -> dict[str, Any]:
    cfg = load_config()
    cfg.update(
        {
            "num_players": 4,
            "n_rounds": 4,
            "hand_size": 8,
            "negotiation_ticks": 4,
            "max_negotiation_gift": 120,
            "max_negotiation_gift_per_phase": 120,
            "max_negotiation_gift_per_trade": 120,
            "max_negotiation_trades_per_phase": 2,
            "alternate_turn_direction": True,
            "random_starting_king_seat": False,
            "pause_between_reveals": True,
        }
    )
    return cfg


class GameSession:
    """Wraps DecisionEngine for human multiplayer play."""

    def __init__(
        self,
        player_ids: list[str],
        player_names: list[str],
        starting_king_seat: int = 0,
        seed: int | None = None,
    ):
        self.player_ids = player_ids
        self.player_names = player_names
        self.config = default_web_config()
        self.config["starting_king_seat"] = starting_king_seat
        self.rng = GameRNG(seed=seed)
        self.engine = DecisionEngine(self.config, self.rng)
        self._pending_human_action: HumanAction | None = None
        self._decision_counter = 0
        self._last_decision_key: tuple[int, str] | None = None
        self._cached_decision_id = ""
        self._last_event_index = 0
        self.state = self.engine.reset()

    @property
    def done(self) -> bool:
        return self.engine.done

    def current_decision(self) -> PendingDecision | None:
        return self.engine.current_decision()

    def decision_id(self) -> str:
        dec = self.current_decision()
        if dec is None:
            self._last_decision_key = None
            self._cached_decision_id = ""
            return ""
        key = (dec.seat, dec.dtype.value)
        if key != self._last_decision_key:
            self._decision_counter += 1
            self._last_decision_key = key
            self._cached_decision_id = f"d{self._decision_counter}-{dec.seat}-{dec.dtype.value}"
        return self._cached_decision_id

    def apply_action(self, action: HumanAction) -> GameState:
        self._pending_human_action = action
        dec = self.current_decision()
        if dec is None:
            return self.state

        if dec.dtype == DecisionType.NEGOTIATION:
            self.engine.step(0, action_handler=self._negotiation_handler)
        elif dec.dtype == DecisionType.PLAY:
            indices = action.payload.get("card_indices", [])
            if not indices:
                indices = [0]
            self.engine.step(indices[0], action_handler=self._play_handler)
        elif dec.dtype == DecisionType.CHOICE:
            choice_idx = int(action.payload.get("choice_index", 0))
            self.engine.step(choice_idx)
        elif dec.dtype == DecisionType.REVEAL:
            self.engine.step(0)
        else:
            self.engine.step(0)

        self._pending_human_action = None
        self.state = self.engine.state
        return self.state

    def _negotiation_handler(
        self, state: GameState, seat: int, _action: int, _rng: GameRNG
    ) -> None:
        act = self._pending_human_action
        if act is None:
            pass_action(state, seat)
            return

        payload = act.payload
        atype = act.action_type

        if atype == "pass":
            pass_action(state, seat)
        elif atype == "propose_trade":
            target = int(payload["target"])
            offer = payload.get("offer", {"gold": 0})
            request = payload.get("request", {"gold": 0})
            try:
                propose_trade(state, seat, target, offer, request)
            except ValueError:
                pass_action(state, seat)
        elif atype == "propose_alliance":
            targets = [int(t) for t in payload.get("targets", [])]
            terms = payload.get("terms", "")
            try:
                propose_alliance(state, seat, targets, terms=terms)
            except ValueError:
                pass_action(state, seat)
        elif atype == "propose_conditional":
            target = int(payload["target"])
            offer = payload.get("offer", {})
            condition = payload.get("condition", {})
            propose_conditional(state, seat, target, offer, condition)
        elif atype == "accept_proposal":
            if not accept_proposal(state, seat, payload["proposal_id"]):
                pass_action(state, seat)
        elif atype == "reject_proposal":
            if not reject_proposal(state, seat, payload["proposal_id"]):
                pass_action(state, seat)
        elif atype == "threaten":
            target = int(payload["target"])
            terms = payload.get("terms", "")
            threaten(state, seat, target, terms)
        else:
            pass_action(state, seat)

    def _play_handler(
        self, state: GameState, seat: int, _action: int, _rng: GameRNG
    ) -> None:
        act = self._pending_human_action
        raw_indices = act.payload.get("card_indices") if act else None
        hand = state.seats[seat].hand
        dec = self.current_decision()
        n_play = dec.context.get("n_play", 2) if dec else 2

        if not raw_indices:
            # Bots / empty payload — play the first n_play cards.
            selected_indices = list(range(min(n_play, len(hand))))
        else:
            # Never pad a partial human selection — that plays unintended cards.
            selected_indices = sorted(
                set(int(i) for i in raw_indices if 0 <= int(i) < len(hand))
            )[:n_play]

        selected = [hand[i] for i in selected_indices if i < len(hand)]
        for idx in sorted([i for i in selected_indices if i < len(hand)], reverse=True):
            state.seats[seat].hand.pop(idx)
        for card in selected:
            self.engine._played_buffer.append((seat, card))
        self.engine.queue.pop(0)
        if not self.engine.queue and self.engine._phase_stage == "playing_commit":
            self.engine._phase_stage = "playing_reveal"
            self.engine._play_reveal_idx = 0
            self.engine._resolve_next_reveal()

    def new_events(self) -> list[dict[str, Any]]:
        events = self.state.event_log[self._last_event_index :]
        self._last_event_index = len(self.state.event_log)
        return events

    def build_public_state(self) -> PublicGameState:
        seats = []
        for seat in range(self.state.num_players):
            s = self.state.seats[seat]
            p = self.state.person_at_seat(seat)
            pid = self.player_ids[s.person_id]
            seats.append(
                PublicSeatState(
                    seat_id=seat,
                    person_id=s.person_id,
                    role=s.role.value,
                    player_id=pid,
                    player_name=self.player_names[s.person_id],
                    gold=p.gold,
                    earned_gold=p.earned_gold,
                    gifted_gold=p.gifted_gold,
                    hand_size=len(s.hand),
                    deck_size=len(s.deck),
                    gift_sent=int(self.state.negotiation_gift_sent.get(seat, 0)),
                    statuses=[
                        PublicStatus(
                            name=st.name,
                            remaining_rounds=max(1, st.expires_after_round - self.state.current_round),
                        )
                        for st in self.state.unique_statuses(seat)
                    ],
                )
            )

        phase = self.state.phase.value
        neg_tick = getattr(self.engine, "_neg_tick", None) if phase == "negotiation" else None
        neg_ticks = int(self.state.config.get("negotiation_ticks", 4))
        max_gift = int(self.state.config.get("max_negotiation_gift", 120))
        max_gift_phase = int(self.state.config.get("max_negotiation_gift_per_phase", 120))
        played = getattr(self.engine, "_played_buffer", []) or []
        locked_seats = sorted({int(seat) for seat, _card in played})

        return PublicGameState(
            current_round=self.state.current_round,
            n_rounds=self.state.n_rounds,
            phase=phase,
            king_seat=self.state.king_seat,
            turn_direction=self.state.turn_direction,
            seats=seats,
            alliances=[list(a.members) for a in self.state.alliances],
            event_log_tail=self.state.event_log[-20:],
            pending_proposals=[
                p for p in self.state.pending_proposals if p.get("status") == "pending"
            ],
            negotiation_tick=neg_tick,
            negotiation_ticks=neg_ticks,
            locked_seats=locked_seats,
            max_negotiation_gift=max_gift,
            max_negotiation_gift_per_phase=max_gift_phase,
        )

    def build_private_state(self, player_id: str) -> PrivateGameState:
        seat = self.player_ids.index(player_id)
        s = self.state.seats[seat]
        return PrivateGameState(
            hand=copy.deepcopy(s.hand),
            seat=seat,
            person_id=s.person_id,
        )

    def build_decision_info(self) -> DecisionInfo | None:
        dec = self.current_decision()
        if dec is None:
            return None
        ctx = copy.deepcopy(dec.context)
        if dec.dtype == DecisionType.PLAY:
            hand = self.state.seats[dec.seat].hand
            ctx["hand_preview"] = [
                {"index": i, "id": c.get("id"), "name": c.get("name"), "category": c.get("category")}
                for i, c in enumerate(hand)
            ]
        return DecisionInfo(
            decision_id=self.decision_id(),
            seat=dec.seat,
            dtype=dec.dtype.value,
            context=ctx,
        )

    def seat_for_player(self, player_id: str) -> int:
        return self.player_ids.index(player_id)

    def player_id_for_seat(self, seat: int) -> str:
        return self.player_ids[seat]

    def starting_king_player_name(self) -> str:
        king_seat = self.config.get("starting_king_seat", 0)
        return self.player_names[king_seat]
