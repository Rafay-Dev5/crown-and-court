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
    return "Trade gold for cards, cards for gold, or cards for cards — then pass.";
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
  const max = Math.max(1, ...seats.map((s) => s.gold));
  const leader = [...seats].sort((a, b) => b.gold - a.gold)[0];
  return (
    <div>
      <p className="text-[10px] uppercase tracking-[0.2em] text-parchment/45 text-center mb-1.5">
        Crown race · total gold
      </p>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 px-1">
        {seats.map((s) => {
          const pct = Math.round((s.gold / max) * 100);
          const isKing = s.seat_id === kingSeat;
          const isTurn = s.seat_id === activeSeat;
          const isLead = leader && s.seat_id === leader.seat_id && s.gold > 0;
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
                <span className="gold-chip shrink-0">{s.gold}</span>
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
  const [autoPlay, setAutoPlay] = useState(false);
  const [showSuccession, setShowSuccession] = useState(false);
  const [acceptingProposalId, setAcceptingProposalId] = useState<string | null>(null);
  const [fulfillmentTokens, setFulfillmentTokens] = useState<string[]>([]);
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
  const isTarget = decision?.dtype === "target";
  const isDiscard = decision?.dtype === "discard";
  const isMyTurn = !isReveal && decision?.seat === yourSeat;
  const discardCount =
    typeof decision?.context?.count === "number" ? (decision.context.count as number) : 1;
  const discardHand =
    privateState?.discard_choice?.hand ?? privateState?.hand ?? [];
  const mySeat = publicState?.seats.find((s) => s.seat_id === yourSeat);
  const myRole = mySeat?.role ?? "noble";
  const nPlay =
    typeof decision?.context?.n_play === "number"
      ? (decision.context.n_play as number)
      : myRole === "king"
        ? 3
        : 2;
  const legalTargets = Array.isArray(decision?.context?.legal_targets)
    ? (decision.context.legal_targets as number[])
    : [];

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
      } else if (decision.dtype === "target") {
        const targets = Array.isArray(decision.context.legal_targets)
          ? (decision.context.legal_targets as number[])
          : [];
        if (targets.length) sendAction("choose_target", { target_seat: targets[0] });
      } else if (decision.dtype === "choice") {
        sendAction("choice", { choice_index: 0 });
      } else if (decision.dtype === "discard") {
        const count = typeof decision.context.count === "number" ? decision.context.count : 1;
        sendAction("discard", {
          card_indices: Array.from({ length: count }, (_, i) => i),
        });
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
    const status = String(p.status ?? "pending");
    if (status === "pending_confirm" && p.proposer === yourSeat) return true;
    if (status !== "pending") return false;
    if (p.target === yourSeat) return true;
    const targets = p.targets;
    return Array.isArray(targets) && targets.includes(yourSeat);
  });

  const youAreOathbreaker = (mySeat?.statuses ?? []).some(
    (s) => normalizeStatus(s).name === "oathbreaker"
  );

  const asTradeCards = (raw: unknown): CardData[] => {
    if (!Array.isArray(raw)) return [];
    const out: CardData[] = [];
    for (const c of raw) {
      if (!c || typeof c !== "object") continue;
      const card = c as Record<string, unknown>;
      if (typeof card.name !== "string" && typeof card.id !== "string") continue;
      out.push({
        id: String(card.id ?? card.name ?? "unknown"),
        name: String(card.name ?? card.id ?? "Unknown"),
        category: typeof card.category === "string" ? card.category : undefined,
        rarity: typeof card.rarity === "string" ? card.rarity : undefined,
        effect: (card.effect as CardData["effect"]) ?? undefined,
        flavor_text: typeof card.flavor_text === "string" ? card.flavor_text : undefined,
      });
    }
    return out;
  };

  const describeProposal = (p: Record<string, unknown>) => {
    const from = seatName(p.proposer);
    const to = seatName(p.target);
    const awaitingConfirm = p.status === "pending_confirm";
    if (p.type === "trade") {
      const offer =
        (p.offer as {
          gold?: number;
          cards?: string[];
          card_details?: unknown;
        } | undefined) ?? {};
      const request =
        (p.request as {
          gold?: number;
          card_count?: number;
          cards?: string[];
          card_details?: unknown;
        } | undefined) ?? {};
      const offerG = offer.gold ?? 0;
      const requestG = request.gold ?? 0;
      const offerCards = asTradeCards(offer.card_details);
      const requestCards = asTradeCards(request.card_details);
      const offerC = offerCards.length || (Array.isArray(offer.cards) ? offer.cards.length : 0);
      const requestC =
        requestCards.length ||
        (Array.isArray(request.cards) ? request.cards.length : 0) ||
        (request.card_count ?? 0);
      const kind = String(p.kind ?? "");
      let summary = "";
      if (awaitingConfirm && p.proposer === yourSeat) {
        summary = `${to} selected cards for your trade — confirm to finish`;
      } else if (kind === "gold_for_cards" || (offerG > 0 && requestC > 0)) {
        summary = `gives you ${offerG}g for ${requestC} of your card${requestC === 1 ? "" : "s"}`;
      } else if (kind === "cards_for_gold" || (offerC > 0 && requestG > 0)) {
        summary = `gives you ${offerC} card${offerC === 1 ? "" : "s"} for ${requestG}g`;
      } else if (kind === "cards_for_cards" || (offerC > 0 && requestC > 0)) {
        summary = `gives you ${offerC} card${offerC === 1 ? "" : "s"} for ${requestC} of yours`;
      } else {
        summary = `offers a trade (${offerG}g / ${offerC} cards ↔ ${requestG}g / ${requestC} cards)`;
      }
      const cardsYouReceive =
        awaitingConfirm && p.proposer === yourSeat
          ? requestCards
          : p.target === yourSeat
            ? offerCards
            : [];
      return (
        <div className="text-sm w-full">
          <p>
            <strong>{awaitingConfirm && p.proposer === yourSeat ? to : from}</strong> {summary}
          </p>
          {!awaitingConfirm && requestC > 0 && p.target === yourSeat && requestCards.length === 0 && (
            <p className="text-xs text-royal-dark/65 mt-0.5">
              Accepting requires choosing {requestC} card{requestC === 1 ? "" : "s"} from your hand.
              The other player will see them before the trade finishes.
            </p>
          )}
          {cardsYouReceive.length > 0 && (
            <div className="mt-2">
              <p className="font-display text-[11px] uppercase tracking-wide text-royal-dark/55 mb-1">
                Cards you will receive
              </p>
              <div className="flex flex-wrap gap-2 justify-center">
                {cardsYouReceive.map((c, i) => (
                  <CardComponent key={`${c.id}-${i}`} card={c} previewable />
                ))}
              </div>
            </div>
          )}
        </div>
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
  const choiceCard = isChoice || isTarget ? (decision?.context.card as CardData | undefined) : undefined;
  const youAcked = Boolean(playerId && revealAcks.includes(playerId));
  const waitingNames = players
    .filter((p) => !p.is_bot && p.connected && playerId && !revealAcks.includes(p.id) && p.id !== playerId)
    .map((p) => p.name);
  const actorName = decision
    ? publicState.seats.find((s) => s.seat_id === decision.seat)?.player_name
    : null;
  const cardOwnerName =
    typeof decision?.context.card_seat === "number"
      ? seatName(decision.context.card_seat)
      : actorName;
  const isTargetedChoice =
    isChoice &&
    typeof decision?.context.card_seat === "number" &&
    decision.context.card_seat !== decision.seat;

  const renderSeat = (seat: PublicSeat | undefined, compact = true, dense = false) => {
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
        dense={dense}
      />
    );
  };

  return (
    <div className="min-h-screen min-h-[100dvh] flex flex-col pb-[env(safe-area-inset-bottom,0)]">
      <header className="hud-bar px-3 sm:px-4 py-2 sm:py-2.5 sticky top-0 z-30">
        <div className="max-w-6xl mx-auto flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
          <div className="flex items-center gap-2 sm:gap-4 min-w-0">
            <span className="font-display text-royal-gold text-sm sm:text-base shrink-0">
              Match {matchNumber}/4
            </span>
            <span className="text-xs sm:text-sm text-parchment/75 shrink-0">
              R{publicState.current_round}/{publicState.n_rounds}
            </span>
            {meta && (
              <span className="text-xs sm:text-sm text-parchment/70 truncate">
                You: {meta.total_points[playerId ?? ""] ?? 0} pts
              </span>
            )}
          </div>
          <div className="text-center order-last sm:order-none basis-full sm:basis-auto">
            <p className="font-display text-sm sm:text-base text-parchment">
              {phaseLabel}
              {phaseDetail ? ` · ${phaseDetail}` : ""}
            </p>
            <p className="text-[10px] sm:text-[11px] text-parchment/50 hidden xs:block sm:block">
              {phaseHelp(publicState.phase)}
            </p>
          </div>
          <div className="flex items-center gap-2 sm:gap-3 ml-auto sm:ml-0">
            <span className="text-[10px] sm:text-xs text-parchment/55 hidden md:inline">
              {publicState.turn_direction === 1 ? "Clockwise" : "Counter-clockwise"}
            </span>
            {vsBots && (
              <label className="text-[10px] sm:text-[11px] text-parchment/70 flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  className="accent-royal-gold"
                  checked={autoPlay}
                  onChange={(e) => setAutoPlay(e.target.checked)}
                />
                <span className="hidden sm:inline">Bots play my turns</span>
                <span className="sm:hidden">Autopilot</span>
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
        <div className="bg-red-950/70 border-b border-red-500/40 text-center text-xs sm:text-sm py-1.5 px-3">
          You are <strong>{getStatusInfo("oathbreaker").label}</strong> — others cannot gift you gold or cards.
        </div>
      )}

      <div
        className={`border-b text-center text-xs sm:text-sm py-1.5 px-3 ${
          allianceLines.length > 0
            ? "bg-sky-950/50 border-sky-500/30 text-sky-100"
            : "bg-royal-darker/60 border-parchment/10 text-parchment/55"
        }`}
      >
        <span className="font-display text-[10px] sm:text-[11px] tracking-wide text-sky-300">Alliances</span>
        <span className="mx-2 text-parchment/30">·</span>
        <span className="break-words">
          {allianceLines.length > 0 ? allianceLines.join(" · ") : "None declared yet"}
        </span>
      </div>

      {/* Mobile table: opponents strip → felt → you */}
      <div className="flex-1 max-w-6xl mx-auto w-full px-2 sm:px-3 py-2 sm:py-3 flex flex-col gap-2 sm:gap-3 md:hidden">
        <div className="grid grid-cols-3 gap-1.5 sm:gap-2">
          {renderSeat(byPos.left, true, true)}
          {renderSeat(byPos.top, true, true)}
          {renderSeat(byPos.right, true, true)}
        </div>

        <div className="felt-table flex flex-col items-center justify-center px-3 py-3 min-h-[160px]">
          <p className="font-display text-xs sm:text-sm text-center text-parchment mb-2 px-1">
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
            <div className="flex justify-center gap-2 sm:gap-3 mb-2 flex-wrap">
              {publicState.seats.map((s) => {
                const n = s.role === "king" ? 3 : 2;
                const locked = (publicState.locked_seats ?? []).includes(s.seat_id);
                return (
                  <div key={s.seat_id} className="text-center">
                    <div className="flex -space-x-1.5 justify-center">
                      {Array.from({ length: n }).map((_, i) => (
                        <div
                          key={i}
                          className={`w-5 h-7 rounded-sm border ${
                            locked
                              ? "card-back"
                              : "border-dashed border-parchment/25 bg-black/20"
                          }`}
                        />
                      ))}
                    </div>
                    <p className="text-[8px] text-parchment/55 mt-0.5 truncate max-w-[3.5rem]">
                      {s.player_name.replace(/^The\s+/i, "")}
                      {locked ? " · in" : ""}
                    </p>
                  </div>
                );
              })}
            </div>
          )}
          <img src="/assets/crown.svg" alt="" className="w-6 h-6 mb-2 opacity-35" />
          <div className="w-full max-w-md bg-royal-dark/55 rounded-xl px-3 py-2 border border-royal-gold/25">
            <EventLog events={events} />
          </div>
        </div>

        <div>{renderSeat(byPos.bottom, false)}</div>
      </div>

      {/* Desktop table */}
      <div className="hidden md:grid flex-1 max-w-6xl mx-auto w-full px-3 py-3 grid-rows-[auto_minmax(220px,1fr)_auto] gap-3">
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
        <div className="panel-parchment p-3 sm:p-4 max-w-3xl mx-auto mb-3 w-[calc(100%-1rem)] sm:w-[calc(100%-1.5rem)]">
          <p className="font-display text-sm mb-2">Incoming proposals</p>
          {pendingForMe.map((p) => {
            const pid = p.id as string;
            const awaitingConfirm = p.status === "pending_confirm";
            const request = (p.request as { card_count?: number; cards?: string[] } | undefined) ?? {};
            const needed = awaitingConfirm
              ? 0
              : Number(request.card_count ?? (Array.isArray(request.cards) ? request.cards.length : 0));
            const isPicking = acceptingProposalId === pid;
            const hand = privateState?.hand ?? [];
            const selectedIds = fulfillmentTokens.map((t) => t.split(":").slice(1).join(":"));
            return (
              <div
                key={pid}
                className="flex flex-col gap-2 mb-3 pb-3 border-b border-royal-gold/20 last:border-0 last:mb-0 last:pb-0"
              >
                {describeProposal(p)}
                {isPicking && needed > 0 && (
                  <div>
                    <p className="text-xs mb-1">
                      Select {needed} card{needed === 1 ? "" : "s"} to give ({selectedIds.length}/{needed})
                    </p>
                    <div className="card-row mb-2">
                      {hand.map((card, i) => {
                        const token = `${i}:${card.id}`;
                        return (
                          <CardComponent
                            key={token}
                            card={card}
                            selected={fulfillmentTokens.includes(token)}
                            onClick={() => {
                              setFulfillmentTokens((prev) => {
                                if (prev.includes(token)) return prev.filter((t) => t !== token);
                                if (prev.length >= needed) return prev;
                                return [...prev, token];
                              });
                            }}
                          />
                        );
                      })}
                    </div>
                    <div className="flex gap-2 justify-center">
                      <button
                        className="btn-royal text-xs py-1 px-3"
                        disabled={selectedIds.length !== needed}
                        onClick={() => {
                          acceptProposal(pid, selectedIds);
                          setAcceptingProposalId(null);
                          setFulfillmentTokens([]);
                        }}
                      >
                        Offer these cards
                      </button>
                      <button
                        className="btn-outline text-xs py-1 px-3"
                        onClick={() => {
                          setAcceptingProposalId(null);
                          setFulfillmentTokens([]);
                        }}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
                {!isPicking && (
                  <div className="flex gap-2 sm:ml-auto shrink-0">
                    <button
                      className="btn-royal text-xs py-1 px-3"
                      onClick={() => {
                        if (awaitingConfirm) {
                          acceptProposal(pid);
                          return;
                        }
                        if (needed > 0) {
                          setAcceptingProposalId(pid);
                          setFulfillmentTokens([]);
                        } else {
                          acceptProposal(pid);
                        }
                      }}
                    >
                      {awaitingConfirm ? "Confirm trade" : "Accept"}
                    </button>
                    <button
                      className="btn-outline text-xs py-1 px-3"
                      onClick={() => rejectProposal(pid)}
                    >
                      {awaitingConfirm ? "Decline cards" : "Reject"}
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {isMyTurn && decision?.dtype === "negotiation" && (
        <div className="max-w-3xl mx-auto mb-3 w-[calc(100%-1rem)] sm:w-[calc(100%-1.5rem)]">
          <NegotiationPanel
            onPass={() => sendAction("pass")}
            onTrade={(proposal) =>
              sendAction("propose_trade", {
                target: proposal.target,
                offer: proposal.offer,
                request: proposal.request,
              })
            }
            onAlliance={(targets) =>
              sendAction("propose_alliance", { targets, terms: "mutual support" })
            }
          />
        </div>
      )}

      {isMyTurn && decision?.dtype === "play" && privateState && (
        <div className="max-w-4xl mx-auto mb-3 w-[calc(100%-1rem)] sm:w-[calc(100%-1.5rem)]">
          <PlayPanel
            hand={privateState.hand}
            nPlay={nPlay}
            onSubmit={(indices) => sendAction("play", { card_indices: indices })}
          />
        </div>
      )}

      {isMyTurn && isTarget && (
        <div className="panel-parchment p-3 sm:p-4 max-w-3xl mx-auto mb-3 w-[calc(100%-1rem)] sm:w-[calc(100%-1.5rem)]">
          <p className="font-display text-sm mb-1">
            {choiceCard?.name ? `${choiceCard.name} — choose your target` : "Choose your target"}
          </p>
          <p className="text-xs text-royal-dark/65 mb-3">
            Pick which opponent this card hits. Nothing resolves until you choose.
          </p>
          {choiceCard && (
            <div className="flex justify-center my-3">
              <CardComponent card={choiceCard} />
            </div>
          )}
          <div className="flex flex-wrap gap-2 justify-center">
            {legalTargets.map((seatId) => (
              <button
                key={seatId}
                className="btn-royal text-sm"
                onClick={() => sendAction("choose_target", { target_seat: seatId })}
              >
                {seatName(seatId)}
              </button>
            ))}
          </div>
        </div>
      )}

      {isMyTurn && isChoice && (
        <div className="panel-parchment p-3 sm:p-4 max-w-3xl mx-auto mb-3 w-[calc(100%-1rem)] sm:w-[calc(100%-1.5rem)]">
          <p className="font-display text-sm mb-1">
            {isTargetedChoice
              ? `${cardOwnerName} played ${choiceCard?.name ?? "a card"} — you must choose a path`
              : choiceCard?.name
                ? `${choiceCard.name} — choose a path`
                : "Make a choice"}
          </p>
          {isTargetedChoice && (
            <p className="text-xs text-royal-dark/65 mb-2">
              This card targets you. The path you pick decides what happens.
            </p>
          )}
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

      {isMyTurn && isDiscard && (
        <div className="max-w-4xl mx-auto mb-3 w-[calc(100%-1rem)] sm:w-[calc(100%-1.5rem)]">
          <PlayPanel
            hand={discardHand}
            nPlay={Math.min(discardCount, discardHand.length)}
            title={`Choose ${discardCount} card${discardCount > 1 ? "s" : ""} to discard`}
            hint="You pick which card(s) leave your hand. Everyone will see what you discarded when the reveal continues."
            submitLabel="Discard"
            onSubmit={(indices) => sendAction("discard", { card_indices: indices })}
          />
        </div>
      )}

      {!isMyTurn && !isReveal && decision && (
        <motion.p
          animate={{ opacity: [0.55, 1, 0.55] }}
          transition={{ repeat: Infinity, duration: 2 }}
          className="text-center text-parchment/70 mb-2 italic text-sm"
        >
          {isTarget
            ? `${actorName} is choosing a target${choiceCard?.name ? ` for ${choiceCard.name}` : ""}…`
            : isChoice
              ? isTargetedChoice
                ? `${actorName} is choosing a path for ${choiceCard?.name ?? "the card"}…`
                : `${actorName} is choosing a path${choiceCard?.name ? ` for ${choiceCard.name}` : ""}…`
              : isDiscard
                ? `${actorName} is choosing which card${discardCount > 1 ? "s" : ""} to discard…`
                : `Waiting for ${actorName}…`}
        </motion.p>
      )}

      {privateState && decision?.dtype !== "play" && decision?.dtype !== "discard" && (
        <div className="pb-4 px-2 sm:px-3">
          <p className="text-xs text-parchment/50 mb-2 text-center">
            Your hand · tap & hold a card to read it
          </p>
          <div className="card-row px-1">
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
          privatePeek={
            privateState?.peek?.card
              ? {
                  fromSeat: Number(privateState.peek.from_seat),
                  card: privateState.peek.card,
                }
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
