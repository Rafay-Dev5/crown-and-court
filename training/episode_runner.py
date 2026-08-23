from __future__ import annotations

from typing import Any

from agents.heuristic.seat_policies import build_seat_bot_fns
from agents.heuristic.observation import ACTOR_INPUT_DIM, actor_observation, global_observation
from engine.negotiation import (
    accept_proposal,
    pass_action,
    propose_alliance,
    propose_trade,
    reject_proposal,
)
from engine.phases import run_game
from engine.rng import GameRNG
from training.policy_factory import build_policy
from training.league import LeaguePool
from training.ppo import PPOConfig, PPOPolicy, Transition, train_step

NEGOTIATION_ACTIONS = 6


def apply_negotiation_action(state, seat: int, action: int, rng: GameRNG) -> None:
    others = [s for s in range(state.num_players) if s != seat]
    act = action % NEGOTIATION_ACTIONS
    if act == 0 or not others:
        pass_action(state, seat)
    elif act == 1:
        target = others[action % len(others)]
        cap = int(state.config.get("max_negotiation_gift", 100))
        try:
            propose_trade(
                state,
                seat,
                target,
                {"gold": min(cap, 50), "cards": []},
                {"gold": 0, "card_count": 1},
            )
        except ValueError:
            pass_action(state, seat)
    elif act == 2:
        target = others[action % len(others)]
        propose_alliance(state, seat, [target], terms="policy pact")
    elif act == 3:
        pending = [p for p in state.pending_proposals if p.get("status") == "pending" and p.get("target") == seat]
        if pending:
            from engine.negotiation import _card_count_request

            prop = pending[0]
            needed = _card_count_request(prop.get("request"))
            fulfillment = None
            if needed > 0:
                hand = state.seats[seat].hand
                if len(hand) < needed:
                    pass_action(state, seat)
                    return
                fulfillment = [c["id"] for c in hand[:needed]]
            accept_proposal(state, seat, prop["id"], fulfillment_cards=fulfillment)
        else:
            pass_action(state, seat)
    elif act == 4:
        pending = [p for p in state.pending_proposals if p.get("status") == "pending" and p.get("target") == seat]
        if pending:
            reject_proposal(state, seat, pending[0]["id"])
        else:
            pass_action(state, seat)
    else:
        pass_action(state, seat)


def _opponent_fns(
    config: dict[str, Any],
    seat: int,
    train_seat: int,
    game_index: int,
    league: LeaguePool | None,
    bot_fns: list,
):
    if seat == train_seat:
        return None
    if league and league.should_use_checkpoint(game_index):
        cp = league.pick_checkpoint(game_index)
        if cp is not None:
            return league.make_policy_opponent_fns(cp.policy, seat)
    return bot_fns[seat]


def run_shared_episode(
    config: dict[str, Any],
    rng: GameRNG,
    train_seat: int,
    policy: Any,
    league: LeaguePool | None = None,
    game_index: int = 0,
    *,
    train: bool = True,
    opponent_mode: str | None = None,
    defer_update: bool = False,
) -> dict[str, Any]:
    """CTDE episode: shared policy at train_seat, league/heuristic opponents elsewhere."""
    bot_fns = build_seat_bot_fns(config, opponent_mode=opponent_mode)
    if league:
        league.set_seed(int(rng.randint(0, 2**31)))
    trajectory: list[Transition] = []
    use_policy_neg = bool(config.get("policy_negotiation", True))
    reward_shaping = bool(config.get("reward_shaping", False))
    earned_weight = float(config.get("reward_shaping_earned_gold_weight", 0.0))
    succession_weight = float(config.get("reward_shaping_succession_weight", 0.0))
    gift_penalty = float(config.get("reward_shaping_gift_penalty", 0.0))
    prev_earned: int | None = None
    prev_gifted: int | None = None
    policy.reset_hidden(train_seat)

    def _step_shaping(state, seat: int) -> float:
        nonlocal prev_earned, prev_gifted
        if not reward_shaping:
            return 0.0
        person = state.person_at_seat(seat)
        reward = 0.0
        if prev_earned is not None:
            reward += earned_weight * (person.earned_gold - prev_earned) / 2000.0
        if prev_gifted is not None and gift_penalty:
            reward -= gift_penalty * max(0, person.gifted_gold - prev_gifted) / 2000.0
        prev_earned = person.earned_gold
        prev_gifted = person.gifted_gold
        for event in reversed(state.event_log[-8:]):
            if event["type"] == "succession" and event.get("new_king_seat") == seat:
                reward += succession_weight
                break
        return reward

    def record_step(ao, go, action, log_prob, value, reward=0.0, done=False):
        trajectory.append(
            Transition(
                obs=ao.copy(),
                global_obs=go.copy(),
                seat=train_seat,
                action=action,
                log_prob=log_prob,
                value=value,
                reward=reward,
                done=done,
            )
        )

    def negotiation_policy(state, seat, rng_inner):
        if seat == train_seat and use_policy_neg and train:
            ao = actor_observation(state, seat)
            go = global_observation(state, seat)
            action, log_prob, value = policy.act_with_value(ao, go, seat)
            shaping = _step_shaping(state, seat)
            record_step(ao, go, action, log_prob, value, reward=shaping)
            apply_negotiation_action(state, seat, action, rng_inner)
            return
        opp = _opponent_fns(config, seat, train_seat, game_index, league, bot_fns)
        fns = opp or bot_fns[seat]
        fns[0](state, seat, rng_inner)

    def play_policy(state, seat, hand):
        if seat == train_seat and train:
            ao = actor_observation(state, seat)
            go = global_observation(state, seat)
            action, log_prob, value = policy.act_with_value(ao, go, seat)
            shaping = _step_shaping(state, seat)
            record_step(ao, go, action, log_prob, value, reward=shaping)
            n = 3 if seat == state.king_seat else 2
            n = min(n, len(hand))
            indices = list(range(len(hand)))
            rng_local = GameRNG(seed=hash((seat, state.current_round, action)) % (2**31))
            rng_local.shuffle(indices)
            return sorted(indices[:n])
        opp = _opponent_fns(config, seat, train_seat, game_index, league, bot_fns)
        fns = opp or bot_fns[seat]
        return fns[1](state, seat, hand)

    def choice_policy(state, seat, options):
        if seat == train_seat and train:
            ao = actor_observation(state, seat)
            go = global_observation(state, seat)
            action, log_prob, value = policy.act_with_value(ao, go, seat)
            shaping = _step_shaping(state, seat)
            record_step(ao, go, action, log_prob, value, reward=shaping)
            return options[action % len(options)]["id"]
        opp = _opponent_fns(config, seat, train_seat, game_index, league, bot_fns)
        fns = opp or bot_fns[seat]
        return fns[2](state, seat, options)

    state = run_game(config, rng, negotiation_policy, play_policy, choice_policy)
    winner_person = state.seats[state.king_seat].person_id
    train_person = state.seats[train_seat].person_id
    won = winner_person == train_person
    reward = 1.0 if won else -0.1

    if trajectory and train:
        trajectory[-1].reward += reward
        trajectory[-1].done = True

    loss = 0.0
    if train and trajectory and not defer_update:
        if hasattr(policy, "update"):
            stats = policy.update(trajectory)
            loss = stats.get("policy_loss", 0.0) + stats.get("value_loss", 0.0)
        else:
            from training.ctde_policy import train_shared_step

            loss = train_shared_step(policy, trajectory)

    out = {
        "won": won,
        "reward": reward,
        "loss": loss,
        "winner_seat": state.king_seat,
        "train_seat": train_seat,
        "assisted_win": _assisted_win(state),
        "rounds": state.n_rounds,
        "trajectory_len": len(trajectory),
        "actor_input_dim": ACTOR_INPUT_DIM,
    }
    if defer_update:
        out["trajectory"] = trajectory
    return out


def run_episode(
    config: dict[str, Any],
    rng: GameRNG,
    train_seat: int,
    policy: PPOPolicy | SharedGRUPolicy,
    opponent_bots: list[str] | None = None,
    league: LeaguePool | None = None,
    game_index: int = 0,
) -> dict[str, Any]:
    if hasattr(policy, "act_with_value") and hasattr(policy, "global_obs_dim"):
        return run_shared_episode(
            config, rng, train_seat, policy, league=league, game_index=game_index
        )
    return _run_legacy_episode(config, rng, train_seat, policy, opponent_bots)


def _run_legacy_episode(
    config: dict[str, Any],
    rng: GameRNG,
    train_seat: int,
    policy: PPOPolicy,
    opponent_bots: list[str] | None = None,
) -> dict[str, Any]:
    from agents.heuristic.observation import OBS_DIM, seat_observation

    bot_fns = build_seat_bot_fns(config, seat_bots=opponent_bots)
    trajectory: list[Transition] = []
    use_policy_neg = bool(config.get("policy_negotiation", True))
    if hasattr(policy, "reset_hidden"):
        policy.reset_hidden()

    def record_step(obs, action, log_prob, value, reward=0.0, done=False):
        trajectory.append(
            Transition(obs=obs.copy(), action=action, log_prob=log_prob, value=value, reward=reward, done=done)
        )

    def policy_negotiation(state, seat, rng_inner):
        obs = seat_observation(state, seat)
        action, log_prob, value = policy.act_with_value(obs)
        record_step(obs, action, log_prob, value)
        apply_negotiation_action(state, seat, action, rng_inner)

    def negotiation_policy(state, seat, rng_inner):
        if seat == train_seat and use_policy_neg:
            policy_negotiation(state, seat, rng_inner)
        else:
            bot_fns[seat][0](state, seat, rng_inner)

    def play_policy(state, seat, hand):
        if seat == train_seat:
            obs = seat_observation(state, seat)
            action, log_prob, value = policy.act_with_value(obs)
            record_step(obs, action, log_prob, value)
            n = 3 if seat == state.king_seat else 2
            n = min(n, len(hand))
            indices = list(range(len(hand)))
            rng_local = GameRNG(seed=hash((seat, state.current_round, action)) % (2**31))
            rng_local.shuffle(indices)
            return sorted(indices[:n])
        return bot_fns[seat][1](state, seat, hand)

    def choice_policy(state, seat, options):
        if seat == train_seat:
            obs = seat_observation(state, seat)
            action, log_prob, value = policy.act_with_value(obs)
            record_step(obs, action, log_prob, value)
            return options[action % len(options)]["id"]
        return bot_fns[seat][2](state, seat, options)

    state = run_game(config, rng, negotiation_policy, play_policy, choice_policy)
    winner_person = state.seats[state.king_seat].person_id
    train_person = state.seats[train_seat].person_id
    won = winner_person == train_person
    reward = 1.0 if won else -0.1

    if trajectory:
        trajectory[-1].reward = reward
        trajectory[-1].done = True

    loss = train_step(policy, trajectory, PPOConfig()) if trajectory else 0.0
    return {
        "won": won,
        "reward": reward,
        "loss": loss,
        "winner_seat": state.king_seat,
        "train_seat": train_seat,
        "assisted_win": _assisted_win(state),
        "rounds": state.n_rounds,
        "trajectory_len": len(trajectory),
        "obs_dim": OBS_DIM,
    }


def _assisted_win(state) -> bool:
    winner_person = None
    for event in state.event_log:
        if event.get("type") == "game_end":
            winner_person = event.get("winner_person")
            break
    if winner_person is None:
        return False
    for event in state.event_log:
        if event.get("type") == "gold_gifted" and event.get("to_person") == winner_person:
            return True
    return False
