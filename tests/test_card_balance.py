import json

from analytics.card_balance import (
    card_content_hash,
    detect_changed_card_ids,
    diagnose_card,
    tune_single_card,
)


def test_card_content_hash_changes_with_amount():
    a = {"id": "x", "effect": {"params": {"amount": 10}}}
    b = {"id": "x", "effect": {"params": {"amount": 11}}}
    assert card_content_hash(a) != card_content_hash(b)


def test_detect_changed_card_ids(monkeypatch):
    card = {"id": "test_card_001", "name": "T", "owner_type": "noble", "category": "economy"}
    edited = dict(card)
    edited["effect"] = {"params": {"amount": 99}}

    monkeypatch.setattr(
        "analytics.card_balance.load_all_cards",
        lambda: [card],
    )
    baseline = {"cards": {"test_card_001": {"content_hash": card_content_hash(card)}}}
    assert detect_changed_card_ids(baseline) == []

    monkeypatch.setattr(
        "analytics.card_balance.load_all_cards",
        lambda: [edited],
    )
    assert detect_changed_card_ids(baseline) == ["test_card_001"]


def test_diagnose_card_overperformer_with_card(monkeypatch):
    card = {
        "id": "king_test_001",
        "name": "Test",
        "owner_type": "king",
        "category": "economy",
    }
    monkeypatch.setattr("analytics.card_balance.load_all_cards", lambda: [card])
    metrics = {
        "total_games": 100,
        "card_pick_counts": {"king_test_001": 40},
        "card_win_contribution": {
            "king_test_001": {
                "games_with_card": 40,
                "wins_when_played": 30,
                "win_rate_when_played": 0.75,
                "delta_vs_fair": 0.58,
            }
        },
        "card_win_contribution_by_role": {},
        "win_rates_by_seat": {str(i): 1 / 6 for i in range(6)},
        "assisted_win_rate": 0.1,
        "shield_hit_rate": 0.35,
        "role_win_rate": {"started_as_king": 0.4, "started_as_noble": 0.6},
    }
    d = diagnose_card("king_test_001", metrics)
    assert d["verdict"] == "overperformer"
    assert d["tune_action"] == "nerf"


def test_tune_single_card_only_mutates_target(monkeypatch, tmp_path):
    king_dir = tmp_path / "cards" / "king_deck"
    noble_dir = tmp_path / "cards" / "noble_deck"
    king_dir.mkdir(parents=True)
    noble_dir.mkdir(parents=True)

    target = {
        "id": "king_tune_target_001",
        "name": "Target",
        "owner_type": "king",
        "category": "economy",
        "effect": {"primitive": "gold_gain", "params": {"target": "self", "amount": 100}},
    }
    other = {
        "id": "king_other_001",
        "name": "Other",
        "owner_type": "king",
        "category": "economy",
        "effect": {"primitive": "gold_gain", "params": {"target": "self", "amount": 50}},
    }
    (king_dir / "target.json").write_text(json.dumps(target), encoding="utf-8")
    (king_dir / "other.json").write_text(json.dumps(other), encoding="utf-8")

    cards = [target, other]

    monkeypatch.setattr("analytics.card_balance.CARDS_DIR", tmp_path / "cards")
    monkeypatch.setattr("analytics.auto_tune.CARDS_DIR", tmp_path / "cards")
    monkeypatch.setattr("analytics.card_balance.load_all_cards", lambda: cards)
    monkeypatch.setattr("engine.cards.load_all_cards", lambda: cards)

    diagnosis = {"tune_action": "nerf"}
    out = tune_single_card("king_tune_target_001", diagnosis, dry_run=False)
    assert out["changes_applied"]

    new_target = json.loads((king_dir / "target.json").read_text(encoding="utf-8"))
    new_other = json.loads((king_dir / "other.json").read_text(encoding="utf-8"))
    assert new_target["effect"]["params"]["amount"] < 100
    assert new_other["effect"]["params"]["amount"] == 50
