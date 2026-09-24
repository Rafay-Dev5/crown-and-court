import { useState } from "react";
import type { PublicSeat } from "../store/gameStore";

type Row = { seat: number; delta: number; reason: string; round: number };

type Props = {
  seats: PublicSeat[];
  ledger: Row[];
  yourSeat?: number | null;
};

export function LedgerButton({ seats, ledger, yourSeat }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" className="btn-outline text-xs py-1.5 px-3" onClick={() => setOpen(true)}>
        Ledger
      </button>
      {open && (
        <LedgerModal
          seats={seats}
          ledger={ledger}
          yourSeat={yourSeat}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}

function LedgerModal({
  seats,
  ledger,
  yourSeat,
  onClose,
}: Props & { onClose: () => void }) {
  const [seatId, setSeatId] = useState(
    yourSeat != null && seats.some((s) => s.seat_id === yourSeat) ? yourSeat : seats[0]?.seat_id ?? 0
  );
  const seat = seats.find((s) => s.seat_id === seatId) ?? seats[0];
  const rows = ledger.filter((row) => row.seat === seat?.seat_id);

  return (
    <div
      className="fixed inset-0 z-[80] flex items-end sm:items-center justify-center bg-black/70 p-0 sm:p-4"
      onClick={onClose}
    >
      <div
        className="panel-parchment w-full max-w-lg max-h-[88dvh] sm:max-h-[88vh] overflow-y-auto scrollbar-thin p-5 sm:p-6 rounded-t-2xl sm:rounded-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 mb-4">
          <h2 className="font-display text-2xl text-royal-dark">Ledger</h2>
          <button className="btn-outline text-sm py-1 px-3" onClick={onClose}>
            Close
          </button>
        </div>

        <div className="flex flex-wrap gap-2 mb-4">
          {seats.map((s) => (
            <button
              key={s.seat_id}
              type="button"
              className={`text-xs py-1.5 px-3 rounded-full border ${
                s.seat_id === seat?.seat_id
                  ? "bg-royal-dark text-parchment border-royal-dark"
                  : "border-royal-gold/50 text-royal-dark"
              }`}
              onClick={() => setSeatId(s.seat_id)}
            >
              {s.player_name}
            </button>
          ))}
        </div>

        {seat && (
          <>
            <p className="text-sm mb-3">
              {seat.player_name} · <strong>{seat.gold}g</strong>
            </p>
            {rows.length === 0 ? (
              <p className="text-sm text-royal-dark/50 italic">No gold has moved yet.</p>
            ) : (
              <ul className="text-sm">
                {rows.map((row, i) => (
                  <li key={`${seat.seat_id}-${i}`} className="flex justify-between gap-3 py-1 border-b border-royal-gold/15">
                    <span>
                      R{row.round} · {row.reason}
                    </span>
                    <span className={row.delta > 0 ? "text-emerald-800 font-semibold" : "text-red-800 font-semibold"}>
                      {row.delta > 0 ? `+${row.delta}` : row.delta}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </div>
    </div>
  );
}
