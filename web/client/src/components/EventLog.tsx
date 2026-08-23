type Props = {
  events: Record<string, unknown>[];
};

export default function EventLog({ events }: Props) {
  const recent = events.slice(-8).reverse();

  const formatEvent = (e: Record<string, unknown>) => {
    const type = e.type as string;
    switch (type) {
      case "negotiation_pass":
        return `Seat ${e.seat} passed`;
      case "propose_trade":
        return `Trade proposed (${e.proposer} → ${e.target})`;
      case "trade_executed":
        return "Trade completed";
      case "gold_gifted":
        return `${e.amount}g gifted`;
      case "alliance_formed":
        return "Alliance formed";
      case "card_revealed":
        return `${e.name} played`;
      case "succession":
      case "seat_swap":
        return `👑 Succession! Seat ${e.new_king_seat ?? e.ascending_seat ?? "?"} ascends`;
      case "game_end":
        return `Match over — King seat ${e.winner_seat} wins`;
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
