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
  privatePeek?: { fromSeat: number; card: CardData } | null;
  youAcked: boolean;
  waitingNames: string[];
  onContinue: () => void;
};

function asCardData(raw: unknown): CardData | null {
  if (!raw || typeof raw !== "object") return null;
  const c = raw as Record<string, unknown>;
  if (typeof c.name !== "string" && typeof c.id !== "string") return null;
  return {
    id: String(c.id ?? c.name ?? "unknown"),
    name: String(c.name ?? c.id ?? "Unknown"),
    category: typeof c.category === "string" ? c.category : undefined,
    rarity: typeof c.rarity === "string" ? c.rarity : undefined,
    effect: (c.effect as CardData["effect"]) ?? undefined,
    flavor_text: typeof c.flavor_text === "string" ? c.flavor_text : undefined,
  };
}

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
  privatePeek,
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

  const revealedHands = effects.flatMap((e) => {
    if (e.type !== "reveal_hand") return [];
    const cards = Array.isArray(e.cards)
      ? (e.cards as unknown[]).map(asCardData).filter((c): c is CardData => Boolean(c))
      : [];
    if (!cards.length) return [];
    return [{ seat: e.seat, cards }];
  });

  const discardedPiles = effects.flatMap((e) => {
    if (e.type !== "force_discard") return [];
    const cards = Array.isArray(e.discarded)
      ? (e.discarded as unknown[]).map(asCardData).filter((c): c is CardData => Boolean(c))
      : [];
    if (!cards.length) return [];
    return [{ seat: e.seat, cards }];
  });

  return (
    <div className="fixed inset-0 z-40 flex items-end sm:items-center justify-center bg-royal-darker/80 backdrop-blur-sm p-0 sm:p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.94, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        className="panel-parchment w-full max-w-4xl p-4 sm:p-6 md:p-8 max-h-[92dvh] sm:max-h-[92vh] overflow-y-auto rounded-t-2xl sm:rounded-xl"
      >
        <p className="font-display text-[11px] tracking-[0.25em] text-royal-dark/55 uppercase text-center">
          Reveal · Card {index} of {total}
        </p>
        <h2 className="font-display text-xl sm:text-2xl text-center text-royal-dark mt-1 px-1">
          {playerName} plays {card.name}
        </h2>
        {targetName && (
          <p className="text-center text-sm text-royal-dark/70 mt-1">Aimed at {targetName}</p>
        )}

        <div className="mt-4 sm:mt-5 grid md:grid-cols-[auto_1fr] gap-4 sm:gap-6 items-start">
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

        {privatePeek && (
          <div className="mt-5 rounded-lg border border-royal-gold/50 bg-royal-dark/6 px-3 py-3">
            <p className="font-display text-[11px] uppercase tracking-wide text-royal-dark/55 mb-2 text-center">
              Only you see this — peeked from {seatName(privatePeek.fromSeat)}&apos;s hand
            </p>
            <div className="flex justify-center">
              <CardComponent card={privatePeek.card} previewable />
            </div>
          </div>
        )}

        {discardedPiles.map((pile) => (
          <div key={`discard-${String(pile.seat)}`} className="mt-5">
            <p className="font-display text-[11px] uppercase tracking-wide text-royal-dark/55 mb-2 text-center">
              {seatName(pile.seat)} discarded
            </p>
            <div className="card-row">
              {pile.cards.map((c, i) => (
                <CardComponent key={`${c.id}-d-${i}`} card={c} previewable />
              ))}
            </div>
          </div>
        ))}

        {revealedHands.map((hand) => (
          <div key={String(hand.seat)} className="mt-5">
            <p className="font-display text-[11px] uppercase tracking-wide text-royal-dark/55 mb-2 text-center">
              {seatName(hand.seat)}&apos;s hand — visible to everyone
            </p>
            <div className="card-row">
              {hand.cards.map((c, i) => (
                <CardComponent key={`${c.id}-${i}`} card={c} previewable />
              ))}
            </div>
          </div>
        ))}

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
