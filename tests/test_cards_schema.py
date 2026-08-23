from engine.cards import load_all_cards, load_schema, validate_card
from engine.effects.registry import VALID_PRIMITIVES
from engine.validate import validate_all


def test_schema_validation_all_cards():
    schema = load_schema()
    cards = load_all_cards()
    assert cards
    for card in cards:
        errors = validate_card(card, schema)
        assert errors == [], f"{card['id']}: {errors}"


def test_validate_all_command():
    count, errors = validate_all()
    assert count == 0, errors


def test_dice_primitives_registered():
    for prim in ("prompt_choice", "roll_die", "dice_swing", "conditional_on_choice", "conditional_on_status"):
        assert prim in VALID_PRIMITIVES
