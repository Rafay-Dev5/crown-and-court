from agents.heuristic.choices import smart_choice_policy
from engine.phases import setup_game
from engine.rng import GameRNG


def test_hoard_prefers_public_investment():
    config = {"num_players": 4, "n_rounds": 1, "hand_size": 4, "king_start_gold": 1000, "noble_start_gold": 600}
    state = setup_game(config, GameRNG(seed=1))
    options = [
        {"id": "invest_public", "label": "Public Works"},
        {"id": "invest_private", "label": "Private Enrichment"},
    ]
    choice = smart_choice_policy(state, 1, options, "hoard")
    assert choice == "invest_public"


def test_aggressive_prefers_private_investment():
    config = {"num_players": 4, "n_rounds": 1, "hand_size": 4, "king_start_gold": 1000, "noble_start_gold": 600}
    state = setup_game(config, GameRNG(seed=1))
    options = [
        {"id": "invest_public", "label": "Public Works"},
        {"id": "invest_private", "label": "Private Enrichment"},
    ]
    choice = smart_choice_policy(state, 1, options, "aggressive")
    assert choice == "invest_private"
