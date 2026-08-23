"""Tests for signoff metrics accumulator."""

from analytics.metrics_accumulator import SignoffMetricsAccumulator, extract_game_summary


def test_extract_game_summary_succession():
    log = [
        {"type": "game_setup", "starting_king_person": 0, "starting_king_seat": 0},
        {"type": "succession", "new_king_seat": 2, "round": 2},
        {"type": "game_end", "winner_seat": 2, "winner_person": 2},
    ]
    s = extract_game_summary(log)
    assert s["succession_count"] == 1
    assert s["starting_king_won"] is False


def test_accumulator_role_rates():
    acc = SignoffMetricsAccumulator()
    acc.add({"winner_seat": 0, "assisted_win": False, "shield_hits": 1, "shield_whiffs": 1,
             "shield_blocks": 0, "starting_king_won": True, "succession_count": 0, "succession_by_round": {}})
    acc.add({"winner_seat": 1, "assisted_win": True, "shield_hits": 0, "shield_whiffs": 0,
             "shield_blocks": 0, "starting_king_won": False, "succession_count": 1, "succession_by_round": {2: 1}})
    m = acc.to_metrics()
    assert m["assisted_win_rate"] == 0.5
    assert m["role_win_rate"]["started_as_king"] == 0.5
    assert m["succession_rate"] == 0.5
