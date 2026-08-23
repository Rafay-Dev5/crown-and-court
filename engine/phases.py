from __future__ import annotations

from typing import Any, Callable

from engine.cards import build_deck, compute_card_set_version, load_all_cards
from engine.effects.interpreter import resolve_card
from engine.negotiation import run_negotiation_phase
from engine.protection import finalize_protection_bets
from engine.rng import GameRNG
from engine.state import GameState, Phase, PlayerState, Role, SeatState
from engine.status_ticks import apply_status_tick_effects
from engine.succession import perform_seat_swap, resolve_succession


def draw_to_hand(
    state: GameState, seat: int, count: int, rng: GameRNG, hand_size: int = 8
) -> None:
    seat_state = state.seats[seat]
    while len(seat_state.hand) < hand_size and count > 0:
        if not seat_state.deck:
            if not seat_state.discard:
                break
            seat_state.deck = seat_state.discard[:]
            seat_state.discard = []
            rng.shuffle(seat_state.deck)
        card = seat_state.deck.pop()
        seat_state.hand.append(card)
        count -= 1
    while count > 0:
        if not seat_state.deck:
            if not seat_state.discard:
                break
            seat_state.deck = seat_state.discard[:]
            seat_state.discard = []
            rng.shuffle(seat_state.deck)
        if not seat_state.deck:
            break
        seat_state.hand.append(seat_state.deck.pop())
        count -= 1


def setup_game(config: dict[str, Any], rng: GameRNG) -> GameState:
    num_players = int(config["num_players"])
    all_cards = load_all_cards()
    king_size = config.get("king_deck_size")
    noble_size = config.get("noble_deck_size")
    king_deck = build_deck(all_cards, "king", int(king_size) if king_size else None)
    noble_deck = build_deck(all_cards, "noble", int(noble_size) if noble_size else None)
    rng.shuffle(king_deck)
    rng.shuffle(noble_deck)

    if "starting_king_seat" in config:
        king_seat = int(config["starting_king_seat"]) % num_players
    elif config.get("random_starting_king_seat", False):
        king_seat = rng.randint(0, num_players - 1)
    else:
        king_seat = 0

    players = [
        PlayerState(
            person_id=i,
            gold=config["king_start_gold"] if i == king_seat else config["noble_start_gold"],
            earned_gold=config["king_start_gold"] if i == king_seat else config["noble_start_gold"],
        )
        for i in range(num_players)
    ]

    seats: list[SeatState] = []
    for i in range(num_players):
        role = Role.KING if i == king_seat else Role.NOBLE
        deck = king_deck[:] if role == Role.KING else noble_deck[:]
        rng.shuffle(deck)
        seats.append(
            SeatState(seat_id=i, role=role, deck=deck, person_id=i)
        )

    state = GameState(
        num_players=num_players,
        n_rounds=int(config["n_rounds"]),
        current_round=0,
        phase=Phase.SETUP,
        king_seat=king_seat,
        players=players,
        seats=seats,
        config=config,
        card_set_version=compute_card_set_version(all_cards),
    )

    hand_size = int(config.get("hand_size", 8))
    for seat in range(num_players):
        draw_to_hand(state, seat, hand_size, rng, hand_size)

    state.current_round = 1
    state.phase = Phase.NEGOTIATION
    state.log_event(
        "game_setup",
        num_players=num_players,
        starting_king_seat=king_seat,
        starting_king_person=king_seat,
        seed=getattr(rng, "seed", None),
    )
    return state


def run_succession_check(state: GameState, checker_name: str | None = None) -> None:
    state.phase = Phase.SUCCESSION
    checker = checker_name or state.config.get("succession_checker", "gold_only")
    ascending = resolve_succession(state, checker)
    if ascending is not None:
        perform_seat_swap(state, ascending)
    state.log_event("succession_check_complete", ascending=ascending)


def _cards_to_play(state: GameState, seat: int) -> int:
    if seat == state.king_seat:
        base = int(state.config.get("king_plays_per_round", 3))
    else:
        base = int(state.config.get("noble_plays_per_round", 2))
    if state.has_status(seat, "skip_next_play"):
        base = max(0, base - 1)
    if state.has_status(seat, "extra_play"):
        base += 1
    return min(base, len(state.seats[seat].hand))


def run_playing_phase(
    state: GameState,
    rng: GameRNG,
    action_provider: Callable[[GameState, int, list[dict]], list[int]] | None = None,
    choice_provider: Callable[[GameState, int, list[dict]], str] | None = None,
) -> None:
    state.phase = Phase.PLAYING
    state.phase_attacks = []
    hand_size = int(state.config.get("hand_size", 8))
    play_order = [state.king_seat] + state.noble_play_order()

    played: list[tuple[int, dict[str, Any], int]] = []

    for seat in play_order:
        hand = state.seats[seat].hand
        n_play = _cards_to_play(state, seat)
        if n_play == 0 or not hand:
            continue
        if action_provider:
            indices = action_provider(state, seat, hand)
        else:
            indices = list(range(min(n_play, len(hand))))
        indices = indices[:n_play]
        selected_cards = [state.seats[seat].hand[i] for i in indices if i < len(state.seats[seat].hand)]
        for idx in sorted([i for i in indices if i < len(state.seats[seat].hand)], reverse=True):
            state.seats[seat].hand.pop(idx)
        for card in selected_cards:
            played.append((seat, card, len(played)))

    for seat, card, _ in played:
        state.log_event("card_revealed", seat=seat, card_id=card.get("id"), name=card.get("name"))
        target = _default_target(state, seat, card)
        choice = None
        while True:
            if state.pending_choice:
                choice_seat = state.pending_choice.seat
                if choice_provider:
                    choice = choice_provider(state, choice_seat, state.pending_choice.options)
                else:
                    choice = random_choice_policy(state, choice_seat, state.pending_choice.options)
                state.pending_choice = None
            done = resolve_card(
                state, card, seat, rng, target_seat=target, selected_choice=choice
            )
            if done:
                break
            if state.pending_choice:
                continue
            break
        state.seats[seat].discard.append(card)

    finalize_protection_bets(state, rng)

    king_redraw = int(state.config.get("king_redraw", 3))
    noble_redraw = int(state.config.get("noble_redraw", 2))
    for seat in range(state.num_players):
        redraw = king_redraw if seat == state.king_seat else noble_redraw
        draw_to_hand(state, seat, redraw, rng, hand_size)

    apply_status_tick_effects(state, rng)
    state.tick_statuses()


_TARGET_PARAM_KEYS = ("target", "from", "to", "choice_seat", "new_target")


def _effect_references_chosen_target(effect: dict | None) -> bool:
    """True if an effect block (recursively) refers to the chosen-opponent role."""
    if not effect:
        return False
    params = effect.get("params") or {}
    for key in _TARGET_PARAM_KEYS:
        if params.get(key) == "target":
            return True
    for branch in (params.get("branches") or {}).values():
        if not isinstance(branch, dict):
            continue
        if _effect_references_chosen_target(branch.get("on_success")):
            return True
        if _effect_references_chosen_target(branch.get("on_failure")):
            return True
        ofs = branch.get("on_failure_status") or {}
        if isinstance(ofs, dict) and ofs.get("target") == "target":
            return True
    if _effect_references_chosen_target(params.get("effect_if_true")):
        return True
    if _effect_references_chosen_target(params.get("effect_if_false")):
        return True
    if _effect_references_chosen_target(effect.get("secondary_effect")):
        return True
    return False


def card_requires_chosen_target(card: dict) -> bool:
    """Whether the card player must pick an opposing seat before resolve."""
    requires = card.get("requires_state") or {}
    if "target_seat" in requires:
        return False
    if requires.get("alliance_declared_with_target") or "target_prior_choice" in requires:
        return True
    return _effect_references_chosen_target(card.get("effect"))


def legal_card_targets(state: GameState, seat: int) -> list[int]:
    return [s for s in range(state.num_players) if s != seat]


def _default_target(state: GameState, seat: int, card: dict) -> int:
    requires = card.get("requires_state") or {}
    if "target_seat" in requires:
        return int(requires["target_seat"])
    legal = legal_card_targets(state, seat)
    if not legal:
        return seat
    nobles = state.noble_seats()
    if nobles and seat == state.king_seat:
        play_nobles = state.noble_play_order()
        if play_nobles:
            return play_nobles[0]
        return nobles[0]
    return state.king_seat if seat != state.king_seat else legal[0]


def run_round(
    state: GameState,
    rng: GameRNG,
    negotiation_policy: Callable | None = None,
    play_policy: Callable | None = None,
    choice_policy: Callable | None = None,
) -> None:
    if state.config.get("alternate_turn_direction", True):
        state.turn_direction = 1 if state.current_round % 2 == 1 else -1

    state.phase = Phase.NEGOTIATION
    run_negotiation_phase(state, rng, negotiation_policy)

    run_succession_check(state)
    run_playing_phase(state, rng, play_policy, choice_policy)
    run_succession_check(state)


def run_game(
    config: dict[str, Any],
    rng: GameRNG,
    negotiation_policy: Callable | None = None,
    play_policy: Callable | None = None,
    choice_policy: Callable | None = None,
) -> GameState:
    state = setup_game(config, rng)
    if choice_policy is None:
        choice_policy = random_choice_policy
    while state.current_round <= state.n_rounds:
        state.log_event("round_start", round=state.current_round)
        run_round(state, rng, negotiation_policy, play_policy, choice_policy)
        state.current_round += 1
    state.phase = Phase.GAME_END
    state.log_event("game_end", winner_seat=state.king_seat, winner_person=state.seats[state.king_seat].person_id)
    return state


def random_play_policy(state: GameState, seat: int, hand: list[dict]) -> list[int]:
    n = _cards_to_play(state, seat)
    if n <= 0:
        return []
    indices = list(range(len(hand)))
    rng = GameRNG(seed=hash((seat, state.current_round, len(hand))) % (2**31))
    rng.shuffle(indices)
    return sorted(indices[:n])


def random_choice_policy(state: GameState, seat: int, options: list[dict]) -> str:
    rng = GameRNG(seed=hash((seat, state.current_round, len(options))) % (2**31))
    return rng.choice(options)["id"]
