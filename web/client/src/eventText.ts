import { cardNoun } from "./copy";

type SeatName = (seat: unknown) => string;

export function describeResolveEvent(e: Record<string, unknown>, seatName: SeatName): string | null {
  const type = e.type as string;
  switch (type) {
    case "gold_gain":
      return `${seatName(e.seat)} gains ${e.amount} gold`;
    case "gold_loss":
      return `${seatName(e.seat)} loses ${e.amount} gold`;
    case "gold_transfer":
      return `${e.amount}g moves from ${seatName(e.from_seat)} to ${seatName(e.to_seat)}`;
    case "gold_gifted":
      return `${seatName(e.from_seat)} gifts ${e.amount}g to ${seatName(e.to_seat)} (does not help succession)`;
    case "mark_status": {
      const status = String(e.status ?? "a status");
      if (e.reason === "negotiation_gift_received") {
        return `${seatName(e.seat)} accepted a one-way gift and is now ${status} — they cannot receive more gifts for ${e.duration ?? 2} rounds`;
      }
      return `${seatName(e.seat)} becomes ${status} for ${e.duration ?? "?"} rounds`;
    }
    case "gift_blocked_by_status":
      return `Gift to ${seatName(e.to_seat)} blocked — they are ${e.status}`;
    case "alliance_bonus":
      return `Alliance bonus: +${e.amount}g to allied players`;
    case "force_discard":
      return `${seatName(e.seat)} discards ${cardNoun(e.count)}`;
    case "steal_card":
      return `${seatName(e.to_seat)} steals ${cardNoun(e.count)} from ${seatName(e.from_seat)}`;
    case "draw_extra":
      return `${seatName(e.seat)} draws ${cardNoun(e.count)}`;
    case "protect_gold":
      return `${seatName(e.seat)} protects gold`;
    case "protection_hit":
      return "Protection hits — the guess was right";
    case "protection_whiff":
      return "Protection misses — the guess was wrong";
    case "block_succession":
      return `${seatName(e.seat)} blocks the next succession check`;
    case "skip_next_play":
      return `${seatName(e.seat)} will play one fewer card next round`;
    case "extra_play":
      return `${seatName(e.seat)} will play an extra card next round`;
    case "swap_hands":
      return `${seatName(e.seat_a)} and ${seatName(e.seat_b)} swap hands`;
    case "reveal_hand":
      return `${seatName(e.seat)}'s hand is revealed`;
    case "choice_made":
      return `${seatName(e.seat)} chooses ${String(e.choice_id ?? "").replace(/_/g, " ")}`;
    case "dice_roll":
    case "dice_swing":
      return e.success
        ? `Dice: ${e.roll} — success`
        : `Dice: ${e.roll} — failure`;
    case "card_revealed":
      return `${seatName(e.seat)} reveals ${e.name}`;
    case "card_precondition_failed":
      return `${e.name ? `${e.name}: ` : ""}The card's requirement was not met — it fizzles`;
    case "succession":
    case "seat_swap":
      return `Succession: ${seatName(e.new_king_seat ?? e.ascending_seat)} takes the crown`;
    case "shield_registered":
      return `${seatName(e.seat)} sets a protection`;
    case "succession_check_complete":
      return e.ascending ? "A noble is about to take the crown" : "The King holds the crown";
    case "succession_blocked":
      return "Succession is blocked this check";
    case "negotiation_complete":
      return "Negotiation ends";
    case "peek_card":
      return `${seatName(e.seat)} peeks at a hidden card`;
    case "gain_legitimacy":
      return `${seatName(e.seat)} gains legitimacy`;
    default:
      return null;
  }
}

export function describeEvent(e: Record<string, unknown>, seatName: SeatName): string {
  const resolved = describeResolveEvent(e, seatName);
  if (resolved) return resolved;

  const type = e.type as string;
  switch (type) {
    case "negotiation_pass":
      return `${seatName(e.seat)} passed`;
    case "propose_trade": {
      const offer = e.offer_gold ?? 0;
      const request = e.request_gold ?? 0;
      return `${seatName(e.proposer)} offers ${offer}g to ${seatName(e.target)} (asks ${request}g)`;
    }
    case "trade_executed":
      return `Trade completed (${seatName(e.proposer)} ↔ ${seatName(e.target)})`;
    case "alliance_formed": {
      const members = Array.isArray(e.members)
        ? (e.members as number[]).map(seatName).join(" ↔ ")
        : "players";
      return `Alliance formed: ${members}`;
    }
    case "propose_alliance": {
      const targets = Array.isArray(e.targets)
        ? (e.targets as number[]).map(seatName).join(", ")
        : "?";
      return `${seatName(e.proposer)} proposed an alliance with ${targets}`;
    }
    case "proposal_accepted":
      return `Proposal accepted by ${seatName(e.accepter)}`;
    case "proposal_rejected":
      return `Proposal rejected by ${seatName(e.rejecter)}`;
    case "game_end":
      return `Match over — ${seatName(e.winner_seat)} wins`;
    case "round_start":
      return `Round ${e.round} begins`;
    case "game_setup":
      return "The court is seated";
    default:
      return type.replace(/_/g, " ");
  }
}
