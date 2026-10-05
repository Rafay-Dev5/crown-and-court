from engine.cards import load_config
from engine.effects.interpreter import resolve_card
from engine.phases import setup_game
from engine.protection import finalize_protection_bets
from engine.rng import GameRNG


def test_ward_whiff_applies_penalty():
    config = load_config()
    state = setup_game(config, GameRNG(seed=1))
    seat = 1
    gold_before = state.person_at_seat(seat).gold
    card = {
        "id": "noble_ward_001",
        "name": "Ward",
        "category": "protection",
        "timing": "reactive",
        "effect": {
            "primitive": "protect_gold",
            "params": {
                "target": "self",
                "amount": 100,
                "duration_rounds": 1,
                "specificity": "generic",
                "trigger": {"type": "attacked_this_phase", "target": "self"},
            },
        },
        "on_whiff_penalty": {"primitive": "gold_loss", "params": {"target": "self", "amount": 25}},
    }
    resolve_card(state, card, seat, GameRNG(seed=2))
    finalize_protection_bets(state, GameRNG(seed=2))
    assert state.person_at_seat(seat).gold < gold_before
    assert any(e["type"] == "protection_whiff" for e in state.event_log)


def test_succession_block_whiff_drops_the_block_and_charges_half_gold():
    config = load_config()
    state = setup_game(config, GameRNG(seed=4))
    king = state.king_seat
    person = state.person_at_seat(king)
    person.gold = 1000
    card = {
        "id": "king_diplomatic_immunity_001",
        "name": "Diplomatic Immunity",
        "category": "protection",
        "timing": "reactive",
        "effect": {
            "primitive": "block_succession",
            "params": {
                "duration_rounds": 1,
                "trigger": {"type": "succession_imminent"},
            },
        },
        "on_whiff_penalty": {
            "primitive": "gold_loss",
            "params": {"target": "self", "fraction_of_wealth": 0.5},
        },
    }
    resolve_card(state, card, king, GameRNG(seed=1))
    assert state.has_status(king, "block_succession")
    finalize_protection_bets(state, GameRNG(seed=2))
    assert not state.has_status(king, "block_succession")
    assert person.gold == 500


def test_king_ward_hits_when_attacked_later_in_phase():
    config = load_config()
    state = setup_game(config, GameRNG(seed=10))
    king = state.king_seat
    noble = state.noble_seats()[0]
    card = {
        "id": "king_treasury_shield_001",
        "category": "protection",
        "effect": {
            "primitive": "protect_gold",
            "params": {
                "target": "self",
                "amount": 150,
                "duration_rounds": 1,
                "trigger": {"type": "attacked_this_phase", "target": "self", "attack_type": "gold_theft"},
            },
        },
        "on_whiff_penalty": {"primitive": "gold_loss", "params": {"target": "self", "amount": 25}},
    }
    resolve_card(state, card, king, GameRNG(seed=1))
    from engine.effects.primitives import gold_transfer

    ctx = {
        "seat": noble,
        "target_seat": king,
        "card_id": "noble_blackmail_001",
        "params": {"from": "king", "to": "self", "amount": 50, "as_theft": True},
    }
    gold_transfer(state, ctx, GameRNG(seed=2))
    finalize_protection_bets(state, GameRNG(seed=3))
    assert any(e["type"] == "protection_hit" for e in state.event_log)
    assert any(e["type"] == "shield_blocked" for e in state.event_log)


def test_shield_stops_a_theft_larger_than_its_printed_amount():
    config = load_config()
    state = setup_game(config, GameRNG(seed=11))
    king = state.king_seat
    noble = state.noble_seats()[0]
    king_gold = state.person_at_seat(king).gold
    noble_gold = state.person_at_seat(noble).gold
    card = {
        "id": "king_expand_bastion_wall_010",
        "name": "Bastion Wall",
        "category": "protection",
        "effect": {
            "primitive": "protect_gold",
            "params": {
                "target": "self",
                "amount": 90,
                "duration_rounds": 1,
                "blocks": "gold_theft",
                "trigger": {"type": "attacked_this_phase", "target": "self", "attack_type": "gold_theft"},
            },
        },
        "on_whiff_penalty": {"primitive": "gold_loss", "params": {"target": "self", "amount": 80}},
    }
    resolve_card(state, card, king, GameRNG(seed=1))
    from engine.effects.primitives import gold_transfer

    gold_transfer(
        state,
        {
            "seat": noble,
            "target_seat": king,
            "card": {"category": "disruption", "name": "Assassin's Blade"},
            "params": {"from": "king", "to": "self", "amount": 235, "as_theft": True},
        },
        GameRNG(seed=2),
    )
    assert state.person_at_seat(king).gold == king_gold
    assert state.person_at_seat(noble).gold == noble_gold
    assert state.active_shields and state.active_shields[0].consumed
    assert state.active_shields[0].charges == 0

    gold_transfer(
        state,
        {
            "seat": noble,
            "target_seat": king,
            "card": {"category": "disruption", "name": "Second Theft"},
            "params": {"from": "king", "to": "self", "amount": 40, "as_theft": True},
        },
        GameRNG(seed=3),
    )
    assert state.person_at_seat(king).gold == king_gold - 40
    assert state.person_at_seat(noble).gold == noble_gold + 40
    assert all(s.consumed for s in state.active_shields)
    blocked = [e for e in state.event_log if e["type"] == "shield_blocked"]
    assert blocked[0]["used_up"] is True
    assert blocked[0]["attack_type"] == "gold_theft"


def test_lock_order_is_reveal_order_so_the_first_theft_hits_the_shield():
    """A later click must not jump ahead just because it sits earlier in the hand."""
    from web.server.game_session import GameSession, HumanAction

    def theft(card_id: str, amount: int) -> dict:
        return {
            "id": card_id,
            "name": card_id,
            "category": "disruption",
            "effect": {
                "primitive": "gold_transfer",
                "params": {"from": "king", "to": "self", "amount": amount, "as_theft": True},
            },
        }

    shield = {
        "id": "test_shield",
        "name": "Shield",
        "category": "protection",
        "effect": {
            "primitive": "protect_gold",
            "params": {
                "target": "self",
                "amount": 100,
                "duration_rounds": 1,
                "blocks": "gold_theft",
            },
        },
    }
    quiet = {
        "id": "test_quiet",
        "name": "Quiet",
        "category": "economy",
        "effect": {"primitive": "gold_gain", "params": {"target": "self", "amount": 1}},
    }

    session = GameSession(["a", "b", "c", "d"], ["A", "B", "C", "D"], starting_king_seat=0, seed=1)
    while session.current_decision() and session.current_decision().dtype.value == "negotiation":
        session.apply_action(HumanAction(action_type="pass"))

    king_turn = session.current_decision()
    assert king_turn is not None and king_turn.dtype.value == "play"
    king = king_turn.seat
    session.state.seats[king].hand = [shield, quiet, quiet]
    session.apply_action(HumanAction(action_type="play", payload={"card_indices": [0]}))

    thief_turn = session.current_decision()
    assert thief_turn is not None and thief_turn.dtype.value == "play"
    thief = thief_turn.seat
    # 138 sits earlier in the hand, but 120 is locked first.
    session.state.seats[thief].hand = [quiet, theft("steal_138", 138), theft("steal_120", 120)]
    session.apply_action(HumanAction(action_type="play", payload={"card_indices": [2, 1]}))

    assert [card["id"] for _seat, card in session.engine._played_buffer] == [
        "test_shield",
        "steal_120",
        "steal_138",
    ]

    while session.current_decision() and session.current_decision().dtype.value == "play":
        seat = session.current_decision().seat
        session.state.seats[seat].hand = [quiet]
        session.apply_action(HumanAction(action_type="play", payload={"card_indices": [0]}))

    blocked = None
    moved = []
    for _ in range(12):
        dec = session.current_decision()
        if dec is None or dec.dtype.value != "reveal":
            break
        for event in dec.context.get("effects") or []:
            if event.get("type") == "shield_blocked" and event.get("attack_type") == "gold_theft":
                blocked = event
            if event.get("type") == "gold_transfer":
                moved.append(event.get("amount"))
        session.apply_action(HumanAction(action_type="continue_reveal"))

    assert blocked is not None
    assert blocked["amount"] == 120
    assert blocked["used_up"] is True
    assert moved == [138]
