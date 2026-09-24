import { useState } from "react";
import { STATUS_HELP } from "../statusInfo";

type Props = {
  onClose: () => void;
};

export default function RulesModal({ onClose }: Props) {
  return (
    <div
      className="fixed inset-0 z-[80] flex items-end sm:items-center justify-center bg-black/70 p-0 sm:p-4"
      onClick={onClose}
    >
      <div
        className="panel-parchment w-full max-w-2xl max-h-[88dvh] sm:max-h-[88vh] overflow-y-auto scrollbar-thin p-5 sm:p-6 rounded-t-2xl sm:rounded-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 mb-4">
          <h2 className="font-display text-2xl text-royal-dark">How to play</h2>
          <button className="btn-outline text-sm py-1 px-3" onClick={onClose}>
            Close
          </button>
        </div>

        <section className="mb-5">
          <h3 className="font-display text-lg mb-1">The goal</h3>
          <p className="text-sm leading-relaxed">
            This session is <strong>4 matches</strong>, each <strong>4 rounds</strong>.
            Whoever sits as King when a match ends scores. First to <strong>10 points</strong> wins
            the table. Everyone starts as King once.
          </p>
        </section>

        <section className="mb-5">
          <h3 className="font-display text-lg mb-1">Gold</h3>
          <p className="text-sm leading-relaxed">
            All gold counts the same — there is no earned vs gifted split. A Noble with more gold
            than the King takes the crown. The <strong>120g</strong> negotiation cap limits how much
            gold you can move through trades each phase.
          </p>
        </section>

        <section className="mb-5">
          <h3 className="font-display text-lg mb-1">Each round</h3>
          <ol className="text-sm list-decimal pl-5 space-y-1 leading-relaxed">
            <li>
              <strong>Negotiate</strong> — 4 passes around the table. Propose trades or alliances,
              or pass. Gold gifts: max <strong>120g</strong> per phase.
            </li>
            <li>
              <strong>Succession</strong> — if a Noble has more gold than the King, they take the
              crown. Decks and hands swap; gold stays with the person.
            </li>
            <li>
              <strong>Play cards</strong> — the King may play up to <strong>3</strong>, each Noble
              up to <strong>2</strong>, face-down. Playing fewer, or none, is allowed. Cards then
              reveal one at a time. The King reveals first.
            </li>
            <li>
              After every card has resolved, each player draws again (King 3, Noble 2). If anyone
              then holds <strong>more than 7 cards</strong>, they choose which extras to discard
              until they have 7.
            </li>
            <li>
              <strong>Succession again</strong>. Then each allied player is asked whether to keep
              that one alliance. It continues only if both members agree. Then the next round.
            </li>
          </ol>
        </section>

        <section className="mb-5">
          <h3 className="font-display text-lg mb-1">Protection cards</h3>
          <p className="text-sm leading-relaxed mb-2">
            A protection card arms the moment it is revealed and stays up through the rest of that
            reveal. The guess is scored only after every card has been revealed, before succession.
            A hit keeps the shield. A miss removes it, and then you pay the miss cost printed on
            the card (often 60 or 80 gold; succession guesses cost half your gold).
          </p>
          <p className="text-sm leading-relaxed">
            Every protection card except the succession blocks (Diplomatic Immunity and Loyal Guard)
            stops a <strong>gold theft</strong> revealed after it, up to the amount on the card. A
            theft revealed earlier in the round still counts and is not undone. Succession cards
            stop a crown change, not a theft.
          </p>
        </section>

        <section className="mb-5">
          <h3 className="font-display text-lg mb-1">The die</h3>
          <p className="text-sm leading-relaxed">
            Some cards roll a die. The face is shown to the table before the result is applied.
            Read the card for which faces help you.
          </p>
        </section>

        <section className="mb-5">
          <h3 className="font-display text-lg mb-1">Trades</h3>
          <p className="text-sm leading-relaxed mb-2">
            Allowed: <strong>gold for cards</strong>, <strong>cards for gold</strong>, or{" "}
            <strong>cards for cards</strong>. Gold-for-gold is not allowed. Each card is valued at{" "}
            <strong>40 gold</strong> for fairness checks. Card-for-card gifts are capped at{" "}
            <strong>5 cards</strong> per player per negotiation phase.
          </p>
          <ul className="text-sm list-disc pl-5 space-y-1 leading-relaxed">
            <li>
              <strong>Gold ↔ cards:</strong> each card counts as <strong>40 gold</strong>. Compare
              what each side receives. Whoever gets the <strong>higher</strong> value becomes
              Oathbreaker if the other side got <strong>half or less</strong> of that higher value.
            </li>
            <li>
              <strong>Cards for cards:</strong> if someone receives more than 3 cards per card they
              give, they become Oathbreaker.
            </li>
          </ul>
        </section>

        <section className="mb-5">
          <h3 className="font-display text-lg mb-1">Oathbreaker</h3>
          <p className="text-sm leading-relaxed">
            While Oathbreaker, you cannot be gifted <strong>gold or cards</strong> in negotiation.
            It lasts 2 rounds from an unbalanced trade (or longer from some cards). Hover the badge
            any time to reread this.
          </p>
        </section>

        <section className="mb-5">
          <h3 className="font-display text-lg mb-2">Statuses</h3>
          <ul className="text-sm space-y-2">
            {Object.entries(STATUS_HELP).map(([key, val]) => (
              <li key={key}>
                <strong>{val.label}.</strong> {val.description}
              </li>
            ))}
          </ul>
          <p className="text-sm leading-relaxed mt-3">
            <strong>Corrupt</strong> specifically: <strong>100 gold</strong> moves from you to the
            current King at the end of each round (or less if you cannot pay).
          </p>
        </section>

        <section className="mb-5">
          <h3 className="font-display text-lg mb-1">Targets, peeks, and discards</h3>
          <p className="text-sm leading-relaxed">
            When a card needs an opponent, the player who played it chooses the target. If a card
            forces a discard, that player chooses which card(s) to lose. A peek shows one card only
            to the peeker — not the whole table.
          </p>
        </section>

        <section className="mb-5">
          <h3 className="font-display text-lg mb-1">Alliances and betrayal</h3>
          <p className="text-sm leading-relaxed">
            A declared alliance is public. Each player can be in only one at a time. Forming a new
            pact ends any other alliance either player already has. Some cards pay only if you are
            still allied with the target. Playing a betrayal card against your ally ends that
            alliance immediately, even if a shield later stops the theft. An alliance or betrayal
            card that cannot legally resolve is discarded, not returned to your hand.
          </p>
        </section>

        <section>
          <h3 className="font-display text-lg mb-1">The ledger</h3>
          <p className="text-sm leading-relaxed">
            The Ledger button lists every gold change for one player at a time: the amount, the
            round, and why (a card, a trade, corrupt upkeep, a protection miss, and so on).
          </p>
        </section>
      </div>
    </div>
  );
}

export function RulesButton({ className = "" }: { className?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        className={`btn-outline text-xs py-1.5 px-3 ${className}`}
        onClick={() => setOpen(true)}
      >
        Rules
      </button>
      {open && <RulesModal onClose={() => setOpen(false)} />}
    </>
  );
}
