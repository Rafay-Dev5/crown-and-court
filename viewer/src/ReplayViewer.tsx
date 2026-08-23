import { useEffect, useState } from "react";

type ReplayEvent = Record<string, unknown>;

const EVENT_LABELS: Record<string, string> = {
  game_setup: "Game begins",
  round_start: "New round",
  negotiation_complete: "Negotiation ends",
  card_revealed: "Card played",
  gold_gifted: "Gold gifted in trade",
  trade_executed: "Trade completed",
  succession: "Throne changes hands",
  game_end: "Game over",
  protection_hit: "Protection blocked an attack",
  protection_whiff: "Protection guessed wrong",
  dice_roll: "Dice rolled",
  choice_made: "Player chose a branch",
};

function describeEvent(e: ReplayEvent): string {
  const t = String(e.type || "event");
  const label = EVENT_LABELS[t] || t.replace(/_/g, " ");
  const parts: string[] = [label];
  if (e.name) parts.push(`“${e.name}”`);
  if (e.seat !== undefined) parts.push(`seat ${e.seat}`);
  if (e.amount !== undefined) parts.push(`${e.amount} gold`);
  if (e.from_seat !== undefined && e.to_seat !== undefined) {
    parts.push(`${e.from_seat} → ${e.to_seat}`);
  }
  if (e.winner_seat !== undefined) parts.push(`winner seat ${e.winner_seat}`);
  return parts.join(" · ");
}

export default function ReplayViewer() {
  const [events, setEvents] = useState<ReplayEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/replay/sample.json?t=${Date.now()}`)
      .then((r) => (r.ok ? r.json() : Promise.reject("missing")))
      .then(setEvents)
      .catch(() => {
        setEvents([]);
        setError("No replay yet — run a balance sweep first.");
      });
  }, []);

  if (error) {
    return (
      <div className="detail-panel" style={{ marginTop: 0 }}>
        <h2>Game Replay</h2>
        <p>{error}</p>
        <pre className="effect-tree">{`python -m analytics.sweeps --games 100`}</pre>
      </div>
    );
  }

  return (
    <div className="detail-panel" style={{ marginTop: 0 }}>
      <h2>Sample Game Replay</h2>
      <p className="section-intro">
        Plain-language timeline from the last simulated game. Useful for debugging odd balance results.
      </p>
      <ol className="replay-list">
        {events.map((e, i) => (
          <li key={i}>
            <span className="replay-type">{String(e.type)}</span>
            <span>{describeEvent(e)}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
