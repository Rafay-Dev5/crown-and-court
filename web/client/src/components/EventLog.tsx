import { describeEvent } from "../eventText";
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

const HIDDEN_TYPES = new Set(["shield_registered", "negotiation_complete"]);

export default function EventLog({ events }: Props) {
  const seatName = useSeatName();
  const recent = events.filter((e) => !HIDDEN_TYPES.has(String(e.type))).slice(-8).reverse();

  return (
    <div className="w-full max-h-28 sm:max-h-36 overflow-y-auto scrollbar-thin text-left">
      {recent.length === 0 ? (
        <p className="text-parchment/40 italic text-center text-sm">The table is quiet…</p>
      ) : (
        recent.map((e, i) => (
          <p
            key={`${String(e.type)}-${i}-${String(e.seat ?? e.name ?? "")}`}
            className={`py-1 border-b border-parchment/10 last:border-0 ${
              i === 0 ? "text-parchment text-sm" : "text-parchment/65 text-xs"
            }`}
          >
            {describeEvent(e, seatName)}
          </p>
        ))
      )}
    </div>
  );
}
