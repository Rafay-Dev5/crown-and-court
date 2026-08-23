import { useState } from "react";
import { STATUS_HELP } from "../statusInfo";

type Props = {
  onClose: () => void;
};

export default function RulesModal({ onClose }: Props) {
  return (
    <div
      className="fixed inset-0 z-[80] flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        className="panel-parchment w-full max-w-2xl max-h-[88vh] overflow-y-auto scrollbar-thin p-6"
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
          <h3 className="font-display text-lg mb-1">Earned gold vs gifted gold</h3>
          <p className="text-sm leading-relaxed">
            Only <strong>earned gold</strong> counts toward taking the crown. Gold you receive in a
            negotiation trade is <strong>gifted</strong> — you can spend it, but it will not help
            you become King. Card effects (theft, taxes) follow the card, not the gift rule.
          </p>
        </section>

        <section className="mb-5">
          <h3 className="font-display text-lg mb-1">Each round</h3>
          <ol className="text-sm list-decimal pl-5 space-y-1 leading-relaxed">
            <li>
              <strong>Negotiate</strong> — 4 passes around the table. Trade gold, propose an
              alliance, or pass. Gift cap is 120g per gift and per phase.
            </li>
            <li>
              <strong>Succession</strong> — if a Noble has more <em>earned</em> gold than the King,
              they take the crown. Decks and hands swap; gold stays with the person.
            </li>
            <li>
              <strong>Play cards</strong> — King plays 3, each Noble plays 2, face-down. Cards then
              reveal one at a time. Everyone sees what each card does and clicks Continue.
            </li>
            <li>
              <strong>Succession again</strong>, then the next round.
            </li>
          </ol>
        </section>

        <section className="mb-5">
          <h3 className="font-display text-lg mb-1">Why Oathbreaker appears</h3>
          <p className="text-sm leading-relaxed">
            It is not random. If someone gives you gold and you give nothing back (a one-way gift),
            you become <strong>Oathbreaker</strong> for 2 rounds and cannot receive more gifted gold.
            Even trades (gold both ways) do not apply it. Some cards also apply it. Hover the badge
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
        </section>

        <section>
          <h3 className="font-display text-lg mb-1">Alliances</h3>
          <p className="text-sm leading-relaxed">
            A declared alliance is public. Some cards only pay out if you still have one with your
            target. Betrayal cards often need an alliance first.
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
