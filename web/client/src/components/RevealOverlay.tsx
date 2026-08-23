import { motion } from "framer-motion";
import CardComponent from "./CardComponent";
import { describeResolveEvent } from "../eventText";
import type { CardData } from "../store/gameStore";

type Props = {
  card: CardData;
  playerName: string;
  targetName?: string | null;
  index: number;
  total: number;
  effectLines: string[];
  effects: Record<string, unknown>[];
  seatName: (seat: unknown) => string;
  selectedChoice?: string | null;
  youAcked: boolean;
  waitingNames: string[];
  onContinue: () => void;
};

export default function RevealOverlay({
  card,
  playerName,
  targetName,
  index,
  total,
  effectLines,
  effects,
  seatName,
  selectedChoice,
  youAcked,
  waitingNames,
  onContinue,
}: Props) {
  const results = effects
    .map((e) => describeResolveEvent(e, seatName))
    .filter((line): line is string => Boolean(line));

  const goldLines = effects.flatMap((e) => {
    if (e.type === "gold_gain") return [`+${e.amount}g  ${seatName(e.seat)}`];
    if (e.type === "gold_loss") return [`−${e.amount}g  ${seatName(e.seat)}`];
    if (e.type === "gold_transfer") return [`${e.amount}g  ${seatName(e.from_seat)} → ${seatName(e.to_seat)}`];
    return [];
  });

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-royal-darker/80 backdrop-blur-sm p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.94, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        className="panel-parchment w-full max-w-3xl p-6 md:p-8"
      >
        <p className="font-display text-[11px] tracking-[0.25em] text-royal-dark/55 uppercase text-center">
          Reveal · Card {index} of {total}
        </p>
        <h2 className="font-display text-2xl text-center text-royal-dark mt-1">
          {playerName} plays {card.name}
        </h2>
        {targetName && (
          <p className="text-center text-sm text-royal-dark/70 mt-1">Aimed at {targetName}</p>
        )}

        <div className="mt-5 grid md:grid-cols-[auto_1fr] gap-6 items-start">
          <div className="flex justify-center">
            <CardComponent card={card} large previewable />
          </div>
          <div>
            {selectedChoice && (
              <p className="text-sm mb-3">
                Path chosen: <strong>{selectedChoice.replace(/_/g, " ")}</strong>
              </p>
            )}
            {goldLines.length > 0 && (
              <div className="mb-3 rounded-lg bg-royal-dark/8 border border-royal-gold/40 px-3 py-2">
                {goldLines.map((line) => (
                  <p
                    key={line}
                    className={`font-display text-lg ${
                      line.startsWith("+")
                        ? "text-emerald-800"
                        : line.startsWith("−") || line.startsWith("-")
                          ? "text-red-800"
                          : "text-royal-dark"
                    }`}
                  >
                    {line}
                  </p>
                ))}
              </div>
            )}
            <p className="font-display text-[11px] uppercase tracking-wide text-royal-dark/55 mb-1">
              {results.length ? "What happened" : "What this card does"}
            </p>
            <ul className="text-sm space-y-1.5 text-royal-dark/90">
              {(results.length ? results : effectLines.length ? effectLines : ["See the card text."]).map((line) => (
                <li key={line} className="whitespace-pre-wrap leading-snug">• {line}</li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-6">
          {youAcked ? (
            <p className="text-center text-sm text-royal-dark/70 italic">
              Waiting for {waitingNames.length ? waitingNames.join(", ") : "the table"}…
            </p>
          ) : (
            <button className="btn-royal w-full text-lg py-3" onClick={onContinue}>
              Continue
            </button>
          )}
        </div>
      </motion.div>
    </div>
  );
}
