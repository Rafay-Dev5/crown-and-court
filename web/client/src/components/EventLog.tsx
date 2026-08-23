import { useGameStore } from "../store";

type Props = {
  events: Record<string, unknown>[];
};

function useSeatName() {
  const seats = useGameStore((s) => s.publicState?.seats);
  return (seat: unknown) => {
    if (typeof seat !== "number") return String(seat ?? "?");
    return seats?.find((s) => s.seat_id === seat)?.player_name ?? `Seat ${seat}`;
  };
}

export default function EventLog({ events }: Props) {
  const seatName = useSeatName();
  const recent = events.slice(-8).reverse();

  const formatEvent = (e: Record<string, unknown>) => {
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
      case "gold_gifted":
        return `${e.amount}g gifted (${seatName(e.from_seat)} → ${seatName(e.to_seat)})`;
      case "alliance_formed":
        return "Alliance formed";
      case "propose_alliance":
        return `${seatName(e.proposer)} proposed an alliance`;
      case "proposal_accepted":
        return `Proposal accepted by ${seatName(e.accepter)}`;
      case "proposal_rejected":
        return `Proposal rejected by ${seatName(e.rejecter)}`;
      case "card_revealed":
        return `${e.name} played`;
      case "succession":
      case "seat_swap":
        return `👑 Succession! ${seatName(e.new_king_seat ?? e.ascending_seat)} ascends`;
      case "game_end":
        return `Match over — ${seatName(e.winner_seat)} wins`;
      case "round_start":
        return `— Round ${e.round} begins —`;
      default:
        return type.replace(/_/g, " ");
    }
  };

  return (
    <div className="bg-royal-dark/60 rounded-lg p-3 max-h-32 overflow-y-auto scrollbar-thin text-xs">
      {recent.length === 0 ? (
        <p className="text-parchment/40 italic">Event log...</p>
      ) : (
        recent.map((e, i) => (
          <p key={i} className="text-parchment/80 py-0.5 border-b border-parchment/10 last:border-0">
            {formatEvent(e)}
          </p>
        ))
      )}
    </div>
  );
}
