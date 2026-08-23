import { useEffect, useState } from "react";
import { useGameStore } from "../store";

type Props = {
  onPass: () => void;
  onTrade: (target: number, offerGold: number, requestGold: number) => void;
  onAlliance: (targets: number[]) => void;
};

export default function NegotiationPanel({ onPass, onTrade, onAlliance }: Props) {
  const { publicState, yourSeat } = useGameStore();
  const [mode, setMode] = useState<"menu" | "trade" | "alliance">("menu");
  const others = publicState?.seats.filter((s) => s.seat_id !== yourSeat) ?? [];
  const [targetSeat, setTargetSeat] = useState<number>(-1);
  const [offerGold, setOfferGold] = useState(0);
  const [requestGold, setRequestGold] = useState(0);

  // Never default to seat 0 — that is often yourself (King) and silently self-trades.
  useEffect(() => {
    if (others.length === 0) return;
    if (!others.some((s) => s.seat_id === targetSeat)) {
      setTargetSeat(others[0].seat_id);
    }
  }, [others, targetSeat]);

  if (mode === "trade") {
    return (
      <div className="panel-parchment p-4">
        <h4 className="font-display text-sm mb-3">Propose Trade</h4>
        <div className="flex flex-wrap gap-3 items-end">
          <label className="text-sm">
            To
            <select
              value={targetSeat}
              onChange={(e) => setTargetSeat(Number(e.target.value))}
              className="block mt-1 px-2 py-1 rounded border"
            >
              {others.map((s) => (
                <option key={s.seat_id} value={s.seat_id}>{s.player_name}</option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            Give gold
            <input type="number" min={0} max={120} value={offerGold}
              onChange={(e) => setOfferGold(Number(e.target.value))}
              className="block mt-1 px-2 py-1 rounded border w-20" />
          </label>
          <label className="text-sm">
            Request gold
            <input type="number" min={0} max={120} value={requestGold}
              onChange={(e) => setRequestGold(Number(e.target.value))}
              className="block mt-1 px-2 py-1 rounded border w-20" />
          </label>
          <button
            className="btn-royal text-sm py-2"
            disabled={targetSeat < 0 || targetSeat === yourSeat}
            onClick={() => {
              onTrade(targetSeat, offerGold, requestGold);
              setMode("menu");
              setOfferGold(0);
              setRequestGold(0);
            }}
          >
            Send
          </button>
          <button className="btn-outline text-sm py-2" onClick={() => setMode("menu")}>Cancel</button>
        </div>
        <p className="text-xs text-amber-800 mt-2">
          Gift limit: 120g per phase/trade. Gifted gold does not count for succession.
        </p>
      </div>
    );
  }

  if (mode === "alliance") {
    return (
      <div className="panel-parchment p-4">
        <h4 className="font-display text-sm mb-3">Propose Alliance</h4>
        <select
          value={targetSeat}
          onChange={(e) => setTargetSeat(Number(e.target.value))}
          className="px-2 py-1 rounded border mr-2"
        >
          {others.map((s) => (
            <option key={s.seat_id} value={s.seat_id}>{s.player_name}</option>
          ))}
        </select>
        <button
          className="btn-royal text-sm py-2 mr-2"
          disabled={targetSeat < 0 || targetSeat === yourSeat}
          onClick={() => {
            onAlliance([targetSeat]);
            setMode("menu");
          }}
        >
          Propose
        </button>
        <button className="btn-outline text-sm py-2" onClick={() => setMode("menu")}>Cancel</button>
      </div>
    );
  }

  return (
    <div className="panel-parchment p-4 flex flex-wrap gap-2 items-center">
      <span className="font-display text-sm mr-2">Your turn — Negotiate:</span>
      <button className="btn-royal text-sm py-2" onClick={() => setMode("trade")}>Trade</button>
      <button className="btn-royal text-sm py-2" onClick={() => setMode("alliance")}>Alliance</button>
      <button className="btn-outline text-sm py-2" onClick={onPass}>Pass</button>
    </div>
  );
}
