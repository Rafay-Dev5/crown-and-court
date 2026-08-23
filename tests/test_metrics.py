from analytics.metrics import compute_metrics


def test_card_win_contribution_tracks_winner():
    logs = [
        [
            {"type": "card_revealed", "seat": 2, "card_id": "noble_test_001"},
            {"type": "game_end", "winner_seat": 2, "winner_person": 2},
        ],
        [
            {"type": "card_revealed", "seat": 0, "card_id": "noble_test_001"},
            {"type": "game_end", "winner_seat": 3, "winner_person": 3},
        ],
    ]
    m = compute_metrics(logs)
    contrib = m["card_win_contribution"]["noble_test_001"]
    assert contrib["games_with_card"] == 2
    assert contrib["wins_when_played"] == 1
    assert contrib["win_rate_when_played"] == 0.5


def test_role_win_rate():
    logs = [
        [
            {"type": "game_setup", "starting_king_person": 0, "starting_king_seat": 0},
            {"type": "game_end", "winner_seat": 0, "winner_person": 0},
        ],
        [
            {"type": "game_setup", "starting_king_person": 2, "starting_king_seat": 2},
            {"type": "game_end", "winner_seat": 1, "winner_person": 1},
        ],
    ]
    m = compute_metrics(logs)
    assert m["role_win_rate"]["started_as_king"] == 0.5
    assert m["role_win_rate"]["started_as_noble"] == 0.5


def test_role_normalized_card_contribution():
    logs = [
        [
            {"type": "game_setup", "starting_king_seat": 0},
            {"type": "card_revealed", "seat": 0, "card_id": "king_test_001"},
            {"type": "game_end", "winner_seat": 0, "winner_person": 0},
        ],
        [
            {"type": "game_setup", "starting_king_seat": 1},
            {"type": "card_revealed", "seat": 1, "card_id": "king_test_001"},
            {"type": "succession", "new_king_seat": 2},
            {"type": "card_revealed", "seat": 2, "card_id": "king_test_001"},
            {"type": "game_end", "winner_seat": 2, "winner_person": 2},
        ],
    ]
    m = compute_metrics(logs)
    by_role = m["card_win_contribution_by_role"]["king_test_001"]
    assert by_role["king"]["games_with_card"] == 2
    assert by_role["king"]["wins_when_played"] == 2
    assert "diagnostics" in m
    assert "assisted_win_modes" in m
