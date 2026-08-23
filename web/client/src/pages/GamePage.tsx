import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import CardComponent from "../components/CardComponent";
import EventLog from "../components/EventLog";
import NegotiationPanel from "../components/NegotiationPanel";
import PlayPanel from "../components/PlayPanel";
import PlayerSeat from "../components/PlayerSeat";
import RevealOverlay from "../components/RevealOverlay";
import { RulesButton } from "../components/RulesModal";
import SuccessionOverlay from "../components/SuccessionOverlay";
import { useGameSocket } from "../hooks/useGameSocket";
import { useGameStore } from "../store";
import type { CardData, PublicSeat } from "../store/gameStore";
import { getStatusInfo, normalizeStatus } from "../statusInfo";

function seatPosition(mySeat: number, targetSeat: number): "top" | "left" | "right" | "bottom" {
  const diff = (targetSeat - mySeat + 4) % 4;
  if (diff === 0) return "bottom";
  if (diff === 1) return "left";
  if (diff === 2) return "top";
  return "right";
}

function phaseHelp(phase: string): string {
  if (phase === "negotiation") {
    return "Deal or pass. Only earned gold races for the crown.";
  }
  if (phase === "playing") {
    return "Lock cards face-down. They reveal one at a time.";
  }
  return "";
}

function GoldRace({
  seats,
  kingSeat,
  activeSeat,
}: {
  seats: PublicSeat[];
  kingSeat: number;
  activeSeat?: number | null;
}) {
  const max = Math.max(1, ...seats.map((s) => s.earned_gold));
  const leader = [...seats].sort((a, b) => b.earned_gold - a.earned_gold)[0];
  return (
    <div>
      <p className="text-[10px] uppercase tracking-[0.2em] text-parchment/45 text-center mb-1.5">
        Crown race · earned gold only
      </p>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 px-1">
        {seats.map((s) => {
          const pct = Math.round((s.earned_gold / max) * 100);
          const isKing = s.seat_id === kingSeat;
          const isTurn = s.seat_id === activeSeat;
          const isLead = leader && s.seat_id === leader.seat_id && s.earned_gold > 0;
          return (
            <div
              key={s.seat_id}
              className={`rounded-lg px-2 py-1.5 ${
                isTurn ? "bg-emerald-400/15 ring-1 ring-emerald-400/70" : "bg-parchment/5"
              }`}
            >
              <div className="flex justify-between items-center gap-1 text-[11px] mb-1">
                <span className="truncate text-parchment/85">
                  {isKing ? "👑 " : ""}
                  {s.player_name}
                </span>
                <span className="gold-chip shrink-0">{s.earned_gold}</span>
              </div>
              <div className="h-1.5 rounded-full bg-parchment/15 overflow-hidden">
                <div
                  className={`h-full rounded-full ${isKing ? "bg-royal-gold" : "bg-parchment/55"}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <p className="text-[9px] text-parchment/45 mt-0.5 h-3">
                {isTurn ? "Acting now" : isLead ? "Leading" : ""}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function GamePage() {
  const { sendAction, acceptProposal, rejectProposal } = useGameSocket();
  const {
    publicState, privateState, yourSeat, decision, playerId, players,
    events, meta, matchNumber, lastSuccession, revealAcks,
  } = useGameStore();

  const vsBots = players.filter((p) => p.is_bot).length >= 2;
  const [autoPlay, setAutoPlay] = useState(vsBots);
  const [showSuccession, setShowSuccession] = useState(false);
  const sentRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (lastSuccession) {
      setShowSuccession(true);
      const t = setTimeout(() => setShowSuccession(false), 4000);
      return () => clearTimeout(t);
    }
  }, [lastSuccession]);

  const isReveal = decision?.dtype === "reveal";
  const isChoice = decision?.dtype === "choice";
  const isMyTurn = !isReveal && decision?.seat === yourSeat;
  const mySeat = publicState?.seats.find((s) => s.seat_id === yourSeat);
  const myRole = mySeat?.role ?? "noble";
  const nPlay =
    typeof decision?.context?.n_play === "number"
      ? (decision.context.n_play as number)
      : myRole === "king"
        ? 3
        : 2;

  useEffect(() => {
    if (!autoPlay || !decision || !isMyTurn) return;
    const id = `${decision.decision_id}:turn`;
    if (sentRef.current.has(id)) return;
    const t = setTimeout(() => {
      if (sentRef.current.has(id)) return;
      sentRef.current.add(id);
      if (decision.dtype === "negotiation") sendAction("pass");
      else if (decision.dtype === "play") {
        sendAction("play", { card_indices: Array.from({ length: nPlay }, (_, i) => i) });
      } else if (decision.dtype === "choice") {
        sendAction("choice", { choice_index: 0 });
      }
    }, 500);
    return () => clearTimeout(t);
  }, [autoPlay, isMyTurn, decision, nPlay, sendAction]);

  useEffect(() => {
    if (!autoPlay || !isReveal || !decision) return;
    if (playerId && revealAcks.includes(playerId)) return;
    const id = `${decision.decision_id}:reveal`;
    if (sentRef.current.has(id)) return;
    const t = setTimeout(() => {
      if (sentRef.current.has(id)) return;
      sentRef.current.add(id);
      sendAction("continue_reveal");
    }, 2400);
    return () => clearTimeout(t);
  }, [autoPlay, isReveal, decision?.decision_id, playerId, revealAcks, sendAction]);

  if (!publicState || yourSeat === null) {
    return <div className="min-h-screen flex items-center justify-center">Loading game...</div>;
  }

  const isNegotiating = publicState.phase === "negotiation";
  const phaseLabel = isNegotiating ? "Negotiation" : publicState.phase === "playing" ? "Play" : publicState.phase;
  const phaseDetail = isNegotiating && publicState.negotiation_tick != null
    ? `Pass ${(publicState.negotiation_tick ?? 0) + 1} of ${publicState.negotiation_ticks ?? 4}`
    : isReveal
      ? `Reveal ${Number(decision?.context.index ?? 1)} of ${Number(decision?.context.total ?? 1)}`
      : "";

  const seatName = (seatId: unknown) => {
    if (typeof seatId !== "number") return "?";
    return publicState.seats.find((s) => s.seat_id === seatId)?.player_name ?? `Seat ${seatId}`;
  };

  const alliesOf = (seatId: number): string[] => {
    const names = new Set<string>();
    for (const members of publicState.alliances ?? []) {
      if (!members.includes(seatId)) continue;
      for (const other of members) {
        if (other !== seatId) names.add(seatName(other));
      }
    }
    return [...names];
  };

  const allianceLines = [
    ...new Set(
      (publicState.alliances ?? [])
        .filter((m) => m.length >= 2)
        .map((members) => members.map(seatName).join(" ↔ "))
    ),
  ];

  const pendingForMe = publicState.pending_proposals.filter((p) => {
    if (p.status && p.status !== "pending") return false;
    if (p.target === yourSeat) return true;
    const targets = p.targets;
    return Array.isArray(targets) && targets.includes(yourSeat);
  });

  const youAreOathbreaker = (mySeat?.statuses ?? []).some(
    (s) => normalizeStatus(s).name === "oathbreaker"
  );

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
          {offer > 0 && request === 0 && (
            <span className="block text-xs text-amber-800 mt-0.5">
              One-way gift — accepting brands you Oathbreaker.
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

  const byPos = {
    top: publicState.seats.find((s) => seatPosition(yourSeat, s.seat_id) === "top"),
    left: publicState.seats.find((s) => seatPosition(yourSeat, s.seat_id) === "left"),
    right: publicState.seats.find((s) => seatPosition(yourSeat, s.seat_id) === "right"),
    bottom: publicState.seats.find((s) => seatPosition(yourSeat, s.seat_id) === "bottom"),
  };

  const revealCard = isReveal ? (decision?.context.card as CardData | undefined) : undefined;
  const choiceCard = isChoice ? (decision?.context.card as CardData | undefined) : undefined;
  const youAcked = Boolean(playerId && revealAcks.includes(playerId));
  const waitingNames = players
    .filter((p) => !p.is_bot && p.connected && playerId && !revealAcks.includes(p.id) && p.id !== playerId)
    .map((p) => p.name);
  const actorName = decision
    ? publicState.seats.find((s) => s.seat_id === decision.seat)?.player_name
    : null;

  const renderSeat = (seat: PublicSeat | undefined, compact = true) => {
    if (!seat) return null;
    return (
      <PlayerSeat
        seat={seat}
        isYou={seat.seat_id === yourSeat}
        isActive={
          isReveal
            ? seat.seat_id === Number(decision?.context.card_seat ?? decision?.seat)
            : decision?.seat === seat.seat_id
        }
        allyNames={alliesOf(seat.seat_id)}
        compact={compact}
      />
    );
  };

  return (
    <div className="min-h-screen flex flex-col">
      <header className="hud-bar px-4 py-2.5">
        <div className="max-w-6xl mx-auto flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-4">
            <span className="font-display text-royal-gold">Match {matchNumber}/4</span>
            <span className="text-sm text-parchment/75">
              Round {publicState.current_round}/{publicState.n_rounds}
            </span>
            {meta && (
              <span className="text-sm text-parchment/70">
                You: {meta.total_points[playerId ?? ""] ?? 0} pts
              </span>
            )}
          </div>
          <div className="text-center">
            <p className="font-display text-base text-parchment">
              {phaseLabel}
              {phaseDetail ? ` · ${phaseDetail}` : ""}
            </p>
            <p className="text-[11px] text-parchment/50">{phaseHelp(publicState.phase)}</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-parchment/55">
              {publicState.turn_direction === 1 ? "Clockwise" : "Counter-clockwise"}
            </span>
            {vsBots && (
              <label className="text-[11px] text-parchment/70 flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoPlay}
                  onChange={(e) => setAutoPlay(e.target.checked)}
                />
                Bots play my turns
              </label>
            )}
            <RulesButton />
          </div>
        </div>
        <div className="max-w-6xl mx-auto mt-2">
          <GoldRace
            seats={publicState.seats}
            kingSeat={publicState.king_seat}
            activeSeat={isReveal ? Number(decision?.context.card_seat ?? decision?.seat) : decision?.seat}
          />
        </div>
      </header>

      {youAreOathbreaker && publicState.phase === "negotiation" && (
        <div className="bg-red-950/70 border-b border-red-500/40 text-center text-sm py-1.5 px-3">
          You are <strong>{getStatusInfo("oathbreaker").label}</strong> — others cannot gift you gold. Hover the badge for why.
        </div>
      )}

      <div
        className={`border-b text-center text-sm py-1.5 px-3 ${
          allianceLines.length > 0
            ? "bg-sky-950/50 border-sky-500/30 text-sky-100"
            : "bg-royal-darker/60 border-parchment/10 text-parchment/55"
        }`}
      >
        <span className="font-display text-[11px] tracking-wide text-sky-300">Alliances</span>
        <span className="mx-2 text-parchment/30">·</span>
        {allianceLines.length > 0 ? allianceLines.join("   ·   ") : "None declared yet — propose one during negotiation."}
      </div>

      <div className="flex-1 max-w-6xl mx-auto w-full px-3 py-3 grid grid-rows-[auto_minmax(220px,1fr)_auto] gap-3">
        <div className="flex justify-center">{renderSeat(byPos.top)}</div>

        <div className="grid grid-cols-[auto_1fr_auto] gap-3 items-center min-h-[220px]">
          <div className="flex justify-end">{renderSeat(byPos.left)}</div>
          <div className="felt-table h-full min-h-[220px] flex flex-col items-center justify-center px-5 py-4">
            <p className="font-display text-sm text-center text-parchment mb-2">
              {isReveal && revealCard
                ? `${seatName(decision.context.card_seat ?? decision.seat)} reveals ${revealCard.name}`
                : isMyTurn && decision?.dtype === "negotiation"
                  ? "Your turn — trade, ally, or pass"
                  : isMyTurn && decision?.dtype === "play"
                    ? `Lock in ${nPlay} face-down cards`
                    : isMyTurn && isChoice
                      ? "Choose a path for this card"
                      : actorName
                        ? `Waiting for ${actorName}`
                        : "The court waits"}
            </p>
            {publicState.phase === "playing" && !isReveal && (
              <div className="flex justify-center gap-4 mb-3">
                {publicState.seats.map((s) => {
                  const n = s.role === "king" ? 3 : 2;
                  const locked = (publicState.locked_seats ?? []).includes(s.seat_id);
                  return (
                    <div key={s.seat_id} className="text-center">
                      <div className="flex -space-x-2 justify-center">
                        {Array.from({ length: n }).map((_, i) => (
                          <div
                            key={i}
                            className={`w-6 h-8 rounded-sm border ${
                              locked
                                ? "card-back"
                                : "border-dashed border-parchment/25 bg-black/20"
                            }`}
                          />
                        ))}
                      </div>
                      <p className="text-[9px] text-parchment/55 mt-1 truncate max-w-[4.5rem]">
                        {s.player_name.replace(/^The\s+/i, "")}
                        {locked ? " · in" : ""}
                      </p>
                    </div>
                  );
                })}
              </div>
            )}
            <img src="/assets/crown.svg" alt="" className="w-8 h-8 mb-2 opacity-35" />
            <div className="w-full max-w-md bg-royal-dark/55 rounded-xl px-4 py-3 border border-royal-gold/25">
              <EventLog events={events} />
            </div>
          </div>
          <div className="flex justify-start">{renderSeat(byPos.right)}</div>
        </div>

        <div>{renderSeat(byPos.bottom, false)}</div>
      </div>

      {pendingForMe.length > 0 && publicState.phase === "negotiation" && (
        <div className="panel-parchment p-4 max-w-3xl mx-auto mb-3 w-[calc(100%-1.5rem)]">
          <p className="font-display text-sm mb-2">Incoming proposals</p>
          {pendingForMe.map((p) => (
            <div
              key={p.id as string}
              className="flex flex-col sm:flex-row sm:items-center gap-2 mb-3 pb-3 border-b border-royal-gold/20 last:border-0 last:mb-0 last:pb-0"
            >
              {describeProposal(p)}
              <div className="flex gap-2 sm:ml-auto shrink-0">
                <button className="btn-royal text-xs py-1 px-3" onClick={() => acceptProposal(p.id as string)}>
                  Accept
                </button>
                <button className="btn-outline text-xs py-1 px-3" onClick={() => rejectProposal(p.id as string)}>
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {isMyTurn && decision?.dtype === "negotiation" && (
        <div className="max-w-3xl mx-auto mb-3 w-[calc(100%-1.5rem)]">
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
        <div className="max-w-4xl mx-auto mb-3 w-[calc(100%-1.5rem)]">
          <PlayPanel
            hand={privateState.hand}
            nPlay={nPlay}
            onSubmit={(indices) => sendAction("play", { card_indices: indices })}
          />
        </div>
      )}

      {isMyTurn && isChoice && (
        <div className="panel-parchment p-4 max-w-3xl mx-auto mb-3 w-[calc(100%-1.5rem)]">
          <p className="font-display text-sm mb-1">
            {choiceCard?.name ? `${choiceCard.name} — make a choice` : "Make a choice"}
          </p>
          {choiceCard && (
            <div className="flex justify-center my-3">
              <CardComponent card={choiceCard} />
            </div>
          )}
          <div className="flex flex-wrap gap-2 justify-center">
            {((decision.context.options as { id: string; label: string }[]) ?? []).map((opt, i) => (
              <button key={opt.id} className="btn-royal text-sm" onClick={() => sendAction("choice", { choice_index: i })}>
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {!isMyTurn && !isReveal && decision && (
        <motion.p
          animate={{ opacity: [0.55, 1, 0.55] }}
          transition={{ repeat: Infinity, duration: 2 }}
          className="text-center text-parchment/70 mb-2 italic text-sm"
        >
          {isChoice
            ? `${actorName} is choosing a path${choiceCard?.name ? ` for ${choiceCard.name}` : ""}…`
            : `Waiting for ${actorName}…`}
        </motion.p>
      )}

      {privateState && decision?.dtype !== "play" && (
        <div className="pb-4 px-3">
          <p className="text-xs text-parchment/50 mb-2 text-center">Your hand · hover a card to read it</p>
          <div className="flex gap-2 justify-center overflow-x-auto pb-2">
            {privateState.hand.map((card, i) => (
              <CardComponent key={`${card.id}-${i}`} card={card} />
            ))}
          </div>
        </div>
      )}

      {isReveal && revealCard && (
        <RevealOverlay
          card={revealCard}
          playerName={seatName(decision.context.card_seat ?? decision.seat)}
          targetName={
            typeof decision.context.target_seat === "number"
              ? seatName(decision.context.target_seat)
              : null
          }
          index={Number(decision.context.index ?? 1)}
          total={Number(decision.context.total ?? 1)}
          effectLines={Array.isArray(decision.context.effect_lines) ? (decision.context.effect_lines as string[]) : []}
          effects={Array.isArray(decision.context.effects) ? (decision.context.effects as Record<string, unknown>[]) : []}
          seatName={seatName}
          selectedChoice={
            typeof decision.context.selected_choice === "string"
              ? decision.context.selected_choice
              : null
          }
          youAcked={youAcked}
          waitingNames={waitingNames}
          onContinue={() => sendAction("continue_reveal")}
        />
      )}

      <SuccessionOverlay
        event={showSuccession ? lastSuccession : null}
        onDismiss={() => setShowSuccession(false)}
      />
    </div>
  );
}
