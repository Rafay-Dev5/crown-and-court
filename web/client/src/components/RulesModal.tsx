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
              The King starts with <strong>8</strong> cards. Each Noble starts with <strong>7</strong>.
              After every card has resolved, each player draws again (King 3, Noble 2). Then anyone
              over their limit chooses cards to discard. The King may keep <strong>8</strong>. Each
              Noble discards down to <strong>7</strong>.
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
          <p className="text-sm leading-relaxed mb-2">
            You do not pick a target. A gold shield protects only you. It stops the next two gold
            thefts revealed after it, then it is used up. A third theft in the same round gets
            through. A theft revealed before the shield still stands, and the gold is not returned.
            That earlier theft still counts as a hit, so you do not pay the miss cost.
          </p>
          <p className="text-sm leading-relaxed">
            Diplomatic Immunity and Loyal Guard are the succession blocks. Their guess is whether
            any Noble has more gold than the King when the guess is scored. A hit keeps the block,
            so the following succession check does not change the crown. A miss removes the block
            and costs half your gold. They do not stop theft. Every other protection card stops
            gold theft, not a crown change.
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
              For one card, a price from <strong>21 to 79</strong> gold brands nobody.{" "}
              <strong>20</strong> brands the buyer. <strong>80</strong> brands the seller.
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
            You can hold several different statuses at once. A second copy of the same status does
            not stack; it keeps the longer time remaining. <strong>Corrupt</strong> moves{" "}
            <strong>100 gold</strong> from you to the current King at the end of each round, or
            whatever you have left.
          </p>
        </section>

        <section className="mb-5">
          <h3 className="font-display text-lg mb-1">Targets, peeks, and discards</h3>
          <p className="text-sm leading-relaxed">
            When a card needs an opponent, the player who played it chooses the target. Protection
            cards do not. If a card forces a discard, that player chooses which cards to lose. If
            they are asked for more cards than they hold, they discard what they have and play
            continues. A peek shows one card only to the peeker — not the whole table.
          </p>
        </section>

        <section className="mb-5">
          <h3 className="font-display text-lg mb-1">Alliances and betrayal</h3>
          <p className="text-sm leading-relaxed">
            A declared alliance is public. Each player can be in only one at a time. Forming a new
            pact ends any other alliance either player already has. Some cards pay only if you are
            still allied with the target. A betrayal card can be played only while you have an
            alliance, and only against that ally. If both allies play a betrayal in the same round,
            both cards resolve, because the alliance stays up until every card has been revealed.
            It then ends once, before succession and before the renewal question. A shield stops a
            theft only for the player who played that shield. The card’s extra cost — shown when
            you hover it — is still paid if a shield stops the theft. An alliance or betrayal card
            that cannot legally resolve is discarded.
          </p>
        </section>

        <section className="mb-5">
          <h3 className="font-display text-lg mb-1">The ledger</h3>
          <p className="text-sm leading-relaxed">
            The Ledger button lists every gold change for one player at a time: the amount, the
            round, and why (a card, a trade, corrupt upkeep, a protection miss, and so on).
          </p>
        </section>

        <section>
          <h3 className="font-display text-lg mb-2">FAQ</h3>
          <dl className="text-sm space-y-3 leading-relaxed">
            <div>
              <dt className="font-semibold">My shield was up. Why was gold still stolen?</dt>
              <dd>
                A shield stops only a theft revealed after it, and only the next two. Anything
                revealed earlier is not undone. A third theft after the shield is used also gets
                through. Your own shield does not protect the player you are stealing from.
              </dd>
            </div>
            <div>
              <dt className="font-semibold">Do I aim a protection card at someone?</dt>
              <dd>
                No. Gold shields and succession blocks protect you. You do not name an attacker.
              </dd>
            </div>
            <div>
              <dt className="font-semibold">What is the succession-block guess?</dt>
              <dd>
                It is not “was I attacked.” Diplomatic Immunity and Loyal Guard guess that a Noble
                has more gold than the King. That is checked after the reveals and the redraw,
                before the crown can change. A hit keeps the block. A miss removes it and costs
                half your gold.
              </dd>
            </div>
            <div>
              <dt className="font-semibold">What is the gold-shield guess?</dt>
              <dd>
                That you suffered a gold theft this phase. The miss cost is paid only at the end,
                and only if nothing stole from you. A theft the shield stopped still counts as a
                hit, so you pay no miss cost. Each theft it stops uses one charge, and the shield
                is gone after the second. A theft from before the shield also counts as a hit, and
                that unused shield is not removed for a miss.
              </dd>
            </div>
            <div>
              <dt className="font-semibold">Two people stole from me and I had one shield. What happens?</dt>
              <dd>
                If both thefts are revealed after the shield, both are stopped. The shield is used
                up after the second. A third theft gets through.
              </dd>
            </div>
            <div>
              <dt className="font-semibold">We are allied and we both play a betrayal. Do both work?</dt>
              <dd>
                Yes. The alliance stays through the whole playing phase, so each betrayal still
                sees an ally and resolves. The alliance ends once, after every card is revealed.
                If you play two betrayals yourself against that same ally, both resolve as well.
              </dd>
            </div>
            <div>
              <dt className="font-semibold">When can I play a betrayal card?</dt>
              <dd>
                Only while you have an alliance, and only against that ally. If you have no ally,
                those cards stay locked. A betrayal that cannot legally resolve is discarded, not
                returned to your hand.
              </dd>
            </div>
            <div>
              <dt className="font-semibold">Can I play fewer cards than my maximum?</dt>
              <dd>
                Yes, including none. The King may play up to 3. Each Noble may play up to 2.
              </dd>
            </div>
            <div>
              <dt className="font-semibold">How many cards can I hold?</dt>
              <dd>
                The King starts with 8 and may keep 8 after the redraw. Each Noble starts with 7
                and discards down to 7. If a discard asks for more cards than you hold, you discard
                the cards you have.
              </dd>
            </div>
            <div>
              <dt className="font-semibold">What price can I sell one card for without becoming Oathbreaker?</dt>
              <dd>
                21 to 79 gold. A card counts as 40 gold. At 20 the buyer is Oathbreaker. At 80 the
                seller is. The person who received more becomes Oathbreaker only when the other
                side got half or less of that higher value.
              </dd>
            </div>
            <div>
              <dt className="font-semibold">What do Marked and Discredited do?</dt>
              <dd>
                Marked: every gold theft against you takes 20% more. A shield that is already up
                stops the whole amount. Discredited: every forced discard against you asks for one
                extra card. You can have both at once. The same status does not stack; it keeps
                the longer duration. Sealed Warrant and Royal Census are ordinary cards. They do
                not have a private bonus on top of these rules.
              </dd>
            </div>
            <div>
              <dt className="font-semibold">Where do I see why my gold changed?</dt>
              <dd>
                Open the Ledger and pick one player. Each row is one gold change, the round, and
                the reason.
              </dd>
            </div>
          </dl>
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
