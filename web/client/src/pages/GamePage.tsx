import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import CardComponent from "../components/CardComponent";
import EventLog from "../components/EventLog";
import NegotiationPanel from "../components/NegotiationPanel";
import PlayPanel from "../components/PlayPanel";
import PlayerSeat from "../components/PlayerSeat";
import SuccessionOverlay from "../components/SuccessionOverlay";
import { useGameSocket } from "../hooks/useGameSocket";
import { useGameStore } from "../store";

function seatPosition(mySeat: number, targetSeat: number): "top" | "left" | "right" | "bottom" {
  const diff = (targetSeat - mySeat + 4) % 4;
  if (diff === 0) return "bottom";
  if (diff === 1) return "left";
  if (diff === 2) return "top";
  return "right";
}

export default function GamePage() {
  const { sendAction, acceptProposal, rejectProposal } = useGameSocket();
  const {
    publicState, privateState, yourSeat, decision, playerId,
    events, meta, matchNumber, lastSuccession,
  } = useGameStore();

  const [showSuccession, setShowSuccession] = useState(false);

  useEffect(() => {
    if (lastSuccession) {
      setShowSuccession(true);
      const t = setTimeout(() => setShowSuccession(false), 4000);
      return () => clearTimeout(t);
    }
  }, [lastSuccession]);

  if (!publicState || yourSeat === null) {
    return <div className="min-h-screen flex items-center justify-center">Loading game...</div>;
  }

  const isMyTurn = decision?.seat === yourSeat;
  const myRole = publicState.seats.find((s) => s.seat_id === yourSeat)?.role ?? "noble";
  // Prefer engine n_play (statuses / hand size); fall back to role defaults.
  const nPlay =
    typeof decision?.context?.n_play === "number"
      ? (decision.context.n_play as number)
      : myRole === "king"
        ? 3
        : 2;

  const phaseLabel = publicState.phase.toUpperCase();
  const negInfo = publicState.negotiation_tick != null
    ? `Pass ${(publicState.negotiation_tick ?? 0) + 1} of ${publicState.negotiation_ticks ?? 4}`
    : "";

  const seatName = (seatId: unknown) => {
    if (typeof seatId !== "number") return "?";
    return publicState.seats.find((s) => s.seat_id === seatId)?.player_name ?? `Seat ${seatId}`;
  };

  const pendingForMe = publicState.pending_proposals.filter((p) => {
    if (p.status && p.status !== "pending") return false;
    if (p.target === yourSeat) return true;
    const targets = p.targets;
    return Array.isArray(targets) && targets.includes(yourSeat);
  });

  const describeProposal = (p: Record<string, unknown>) => {
    const from = seatName(p.proposer);
    if (p.type === "trade") {
      const offer = (p.offer as { gold?: number } | undefined)?.gold ?? 0;
      const request = (p.request as { gold?: number } | undefined)?.gold ?? 0;
      return (
        <span className="text-sm">
          <strong>{from}</strong> offers you a trade: they give{" "}
          <strong className="text-royal-gold">{offer}g</strong>, ask for{" "}
          <strong className="text-royal-gold">{request}g</strong>
          {offer > 0 && (
            <span className="block text-xs text-amber-800 mt-0.5">
              Received gold counts as gifted (does not help succession).
            </span>
          )}
        </span>
      );
    }
    if (p.type === "alliance") {
      return (
        <span className="text-sm">
          <strong>{from}</strong> proposes an alliance
          {p.terms ? `: “${String(p.terms)}”` : ""}
        </span>
      );
    }
    return (
      <span className="text-sm">
        <strong>{from}</strong> sent a {String(p.type)} proposal
      </span>
    );
  };

  return (
    <div className="min-h-screen flex flex-col p-4">
      {/* Header */}
      <div className="flex justify-between items-center mb-4 px-2">
        <div>
          <span className="font-display text-royal-gold">Match {matchNumber}/4</span>
          {meta && (
            <span className="ml-4 text-sm text-parchment/70">
              Your score: {meta.total_points[playerId ?? ""] ?? 0} pts
            </span>
          )}
        </div>
        <div className="text-center">
          <p className="font-display text-lg">Round {publicState.current_round} / {publicState.n_rounds}</p>
          <p className="text-sm text-parchment/70">{phaseLabel} {negInfo && `· ${negInfo}`}</p>
        </div>
        <div className="text-sm text-parchment/60">
          Turn: {publicState.turn_direction === 1 ? "Clockwise" : "Counter-clockwise"}
        </div>
      </div>

      {/* Game table */}
      <div className="relative flex-1 min-h-[400px] max-w-4xl mx-auto w-full">
        <div className="felt-table absolute inset-8 md:inset-16 flex items-center justify-center">
          <div className="text-center z-0 px-4">
            <img src="/assets/crown.svg" alt="" className="w-10 h-10 mx-auto mb-2 opacity-40" />
            <EventLog events={events} />
          </div>
        </div>

        {publicState.seats.map((seat) => (
          <PlayerSeat
            key={seat.seat_id}
            seat={seat}
            isYou={seat.seat_id === yourSeat}
            position={seatPosition(yourSeat, seat.seat_id)}
            isActive={decision?.seat === seat.seat_id}
          />
        ))}
      </div>

      {/* Pending proposals — respond anytime in negotiation; does not spend your turn */}
      {pendingForMe.length > 0 && publicState.phase === "negotiation" && (
        <div className="panel-parchment p-4 max-w-2xl mx-auto mt-4">
          <p className="font-display text-sm mb-2">Incoming proposals</p>
          <p className="text-xs text-royal-dark/60 mb-3">
            Accept or reject without ending your negotiation turn — you can still trade afterward.
          </p>
          {pendingForMe.map((p) => (
            <div
              key={p.id as string}
              className="flex flex-col sm:flex-row sm:items-center gap-2 mb-3 pb-3 border-b border-royal-gold/20 last:border-0 last:mb-0 last:pb-0"
            >
              {describeProposal(p)}
              <div className="flex gap-2 sm:ml-auto shrink-0">
                <button
                  className="btn-royal text-xs py-1 px-3"
                  onClick={() => acceptProposal(p.id as string)}
                >
                  Accept
                </button>
                <button
                  className="btn-outline text-xs py-1 px-3"
                  onClick={() => rejectProposal(p.id as string)}
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Action panels */}
      {isMyTurn && decision?.dtype === "negotiation" && (
        <div className="max-w-2xl mx-auto mt-4">
          <NegotiationPanel
            onPass={() => sendAction("pass")}
            onTrade={(target, offer, request) =>
              sendAction("propose_trade", {
                target,
                offer: { gold: offer },
                request: { gold: request },
              })
            }
            onAlliance={(targets) =>
              sendAction("propose_alliance", { targets, terms: "mutual support" })
            }
          />
        </div>
      )}

      {isMyTurn && decision?.dtype === "play" && privateState && (
        <div className="max-w-3xl mx-auto mt-4">
          <PlayPanel
            hand={privateState.hand}
            nPlay={nPlay}
            onSubmit={(indices) => sendAction("play", { card_indices: indices })}
          />
        </div>
      )}

      {isMyTurn && decision?.dtype === "choice" && (
        <div className="panel-parchment p-4 max-w-2xl mx-auto mt-4">
          <p className="font-display text-sm mb-3">Make a choice:</p>
          <div className="flex flex-wrap gap-2">
            {((decision.context.options as { id: string; label: string }[]) ?? []).map((opt, i) => (
              <button key={opt.id} className="btn-royal text-sm" onClick={() => sendAction("choice", { choice_index: i })}>
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {!isMyTurn && decision && (
        <motion.p
          animate={{ opacity: [0.5, 1, 0.5] }}
          transition={{ repeat: Infinity, duration: 2 }}
          className="text-center text-parchment/70 mt-4 italic"
        >
          Waiting for {publicState.seats.find((s) => s.seat_id === decision.seat)?.player_name}...
        </motion.p>
      )}

      {/* Your hand (when not playing) */}
      {privateState && decision?.dtype !== "play" && (
        <div className="mt-4 max-w-4xl mx-auto">
          <p className="text-sm text-parchment/60 mb-2 text-center">Your hand ({privateState.hand.length} cards)</p>
          <div className="flex gap-1 justify-center overflow-x-auto pb-2">
            {privateState.hand.map((card, i) => (
              <CardComponent key={`${card.id}-${i}`} card={card} small />
            ))}
          </div>
        </div>
      )}

      <SuccessionOverlay
        event={showSuccession ? lastSuccession : null}
        onDismiss={() => setShowSuccession(false)}
      />
    </div>
  );
}
