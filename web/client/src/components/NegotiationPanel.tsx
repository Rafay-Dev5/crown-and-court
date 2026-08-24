import { useEffect, useMemo, useState } from "react";
import CardComponent from "./CardComponent";
import { useGameStore } from "../store";
import type { CardData } from "../store/gameStore";

const CARD_VALUE = 40;
const MAX_CARD_GIFTS = 5;

type TradeKind = "gold_for_cards" | "cards_for_gold" | "cards_for_cards";

export type TradeProposal = {
  target: number;
  offer: { gold: number; cards: string[] };
  request: { gold: number; card_count: number };
};

type Props = {
  onPass: () => void;
  onTrade: (proposal: TradeProposal) => void;
  onAlliance: (targets: number[]) => void;
};

export default function NegotiationPanel({ onPass, onTrade, onAlliance }: Props) {
  const { publicState, privateState, yourSeat } = useGameStore();
  const [mode, setMode] = useState<"menu" | "trade" | "alliance">("menu");
  const others = publicState?.seats.filter((s) => s.seat_id !== yourSeat) ?? [];
  const [targetSeat, setTargetSeat] = useState<number>(-1);
  const [kind, setKind] = useState<TradeKind>("gold_for_cards");
  const [goldAmount, setGoldAmount] = useState(40);
  const [cardCount, setCardCount] = useState(1);
  const [selectedCardIds, setSelectedCardIds] = useState<string[]>([]);

  const hand = privateState?.hand ?? [];

  useEffect(() => {
    if (others.length === 0) return;
    if (!others.some((s) => s.seat_id === targetSeat)) {
      setTargetSeat(others[0].seat_id);
    }
  }, [others, targetSeat]);

  useEffect(() => {
    setSelectedCardIds([]);
    setGoldAmount(kind === "cards_for_gold" ? 20 : 40);
    setCardCount(1);
  }, [kind]);

  const target = others.find((s) => s.seat_id === targetSeat);
  const targetIsOathbreaker = (target?.statuses ?? []).some(
    (s) => (typeof s === "string" ? s : s.name) === "oathbreaker"
  );
  const maxGift = publicState?.max_negotiation_gift_per_phase ?? 120;
  const you = publicState?.seats.find((s) => s.seat_id === yourSeat);
  const giftLeft = Math.max(0, maxGift - (you?.gift_sent ?? 0));
  const cardsGiftLeft = Math.max(0, MAX_CARD_GIFTS - (you?.cards_sent ?? 0));

  const toggleCard = (card: CardData, idx: number) => {
    setSelectedCardIds((prev) => {
      const token = `${idx}:${card.id}`;
      if (prev.includes(token)) return prev.filter((t) => t !== token);
      const limit =
        kind === "cards_for_cards" ? Math.min(MAX_CARD_GIFTS, cardsGiftLeft) : hand.length;
      if (prev.length >= limit) return prev;
      return [...prev, token];
    });
  };

  const selectedTokens = selectedCardIds;
  const selectedIds = selectedTokens.map((t) => t.split(":").slice(1).join(":"));

  const imbalanceHint = useMemo(() => {
    if (kind === "gold_for_cards" || kind === "cards_for_gold") {
      const yourValue =
        kind === "gold_for_cards"
          ? cardCount * CARD_VALUE
          : goldAmount;
      const theirValue =
        kind === "gold_for_cards"
          ? goldAmount
          : selectedIds.length * CARD_VALUE;
      const high = Math.max(yourValue, theirValue);
      const low = Math.min(yourValue, theirValue);
      if (high > low && low <= 0.5 * high) {
        if (yourValue > theirValue) {
          return "You may become Oathbreaker (you get more than twice their value).";
        }
        return "They may become Oathbreaker (they get more than twice your value).";
      }
      return "Values are close enough — neither side should get Oathbreaker from this deal.";
    }
    // cards for cards
    if (cardCount > 3 * selectedIds.length) {
      return "You may become Oathbreaker (you would receive more than 3 cards per card you give).";
    }
    if (selectedIds.length > 3 * cardCount) {
      return "They may become Oathbreaker (they would receive more than 3 cards per card they give).";
    }
    return "Card swap looks within the 3∶1 Oathbreaker limit.";
  }, [kind, goldAmount, cardCount, selectedIds.length]);

  const canSend = (() => {
    if (targetSeat < 0 || targetSeat === yourSeat) return false;
    if (kind === "gold_for_cards") {
      return goldAmount > 0 && cardCount > 0 && goldAmount <= giftLeft;
    }
    if (kind === "cards_for_gold") {
      return selectedIds.length > 0 && goldAmount > 0;
    }
    return (
      selectedIds.length > 0 &&
      cardCount > 0 &&
      selectedIds.length <= cardsGiftLeft
    );
  })();

  const submitTrade = () => {
    if (!canSend) return;
    let offer: TradeProposal["offer"];
    let request: TradeProposal["request"];
    if (kind === "gold_for_cards") {
      offer = { gold: goldAmount, cards: [] };
      request = { gold: 0, card_count: cardCount };
    } else if (kind === "cards_for_gold") {
      offer = { gold: 0, cards: selectedIds };
      request = { gold: goldAmount, card_count: 0 };
    } else {
      offer = { gold: 0, cards: selectedIds };
      request = { gold: 0, card_count: cardCount };
    }
    onTrade({ target: targetSeat, offer, request });
    setMode("menu");
    setSelectedCardIds([]);
  };

  if (mode === "trade") {
  return (
    <div className="panel-parchment p-3 sm:p-4">
      <h4 className="font-display text-sm mb-2">Propose Trade</h4>
        <p className="text-xs text-royal-dark/65 mb-3">
          No gold-for-gold. Each card is worth {CARD_VALUE}g for Oathbreaker checks. Gold gifts
          still capped at {maxGift}g/phase; card-for-card gifts capped at {MAX_CARD_GIFTS}/phase.
        </p>

        <div className="flex flex-wrap gap-2 mb-3">
          {(
            [
              ["gold_for_cards", "Gold for cards"],
              ["cards_for_gold", "Cards for gold"],
              ["cards_for_cards", "Cards for cards"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={`text-sm py-1.5 px-3 rounded border ${
                kind === id
                  ? "bg-royal-dark text-parchment border-royal-gold"
                  : "border-royal-dark/25"
              }`}
              onClick={() => setKind(id)}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap gap-3 items-end mb-3">
          <label className="text-sm">
            To
            <select
              value={targetSeat}
              onChange={(e) => setTargetSeat(Number(e.target.value))}
              className="block mt-1 px-2 py-1 rounded border"
            >
              {others.map((s) => (
                <option key={s.seat_id} value={s.seat_id}>
                  {s.player_name}
                </option>
              ))}
            </select>
          </label>

          {(kind === "gold_for_cards" || kind === "cards_for_gold") && (
            <label className="text-sm">
              {kind === "gold_for_cards" ? "Gold you give" : "Gold you request"}
              <input
                type="number"
                min={1}
                max={120}
                value={goldAmount}
                onChange={(e) => setGoldAmount(Math.max(0, Number(e.target.value)))}
                className="block mt-1 px-2 py-1 rounded border w-24"
              />
            </label>
          )}

          {(kind === "gold_for_cards" || kind === "cards_for_cards") && (
            <label className="text-sm">
              Cards you request
              <input
                type="number"
                min={1}
                max={kind === "cards_for_cards" ? MAX_CARD_GIFTS : 8}
                value={cardCount}
                onChange={(e) => setCardCount(Math.max(1, Number(e.target.value)))}
                className="block mt-1 px-2 py-1 rounded border w-20"
              />
            </label>
          )}
        </div>

        {(kind === "cards_for_gold" || kind === "cards_for_cards") && (
          <div className="mb-3">
            <p className="text-sm mb-1">
              Cards you give ({selectedIds.length}
              {kind === "cards_for_cards" ? ` / max ${cardsGiftLeft} left this phase` : ""})
            </p>
            <div className="card-row mb-3">
              {hand.map((card, i) => {
                const token = `${i}:${card.id}`;
                return (
                  <CardComponent
                    key={token}
                    card={card}
                    selected={selectedTokens.includes(token)}
                    onClick={() => toggleCard(card, i)}
                  />
                );
              })}
            </div>
          </div>
        )}

        <p className="text-xs text-amber-900 mb-2">{imbalanceHint}</p>
        {targetIsOathbreaker && (
          <p className="text-xs text-red-800 mb-2">
            {target?.player_name} is Oathbreaker — they cannot receive gold or cards. This trade
            will not go through to them.
          </p>
        )}

        <div className="flex flex-wrap gap-2">
          <button className="btn-royal text-sm py-2" disabled={!canSend} onClick={submitTrade}>
            Send
          </button>
          <button className="btn-outline text-sm py-2" onClick={() => setMode("menu")}>
            Cancel
          </button>
        </div>
        <p className="text-xs text-royal-dark/60 mt-2">
          Gold budget left: {giftLeft}g · Card-for-card gifts left: {cardsGiftLeft}
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
            <option key={s.seat_id} value={s.seat_id}>
              {s.player_name}
            </option>
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
        <button className="btn-outline text-sm py-2" onClick={() => setMode("menu")}>
          Cancel
        </button>
      </div>
    );
  }

  return (
    <div className="panel-parchment p-4 flex flex-wrap gap-2 items-center">
      <span className="font-display text-sm mr-2">Your turn — Negotiate:</span>
      <button className="btn-royal text-sm py-2" onClick={() => setMode("trade")}>
        Trade
      </button>
      <button className="btn-royal text-sm py-2" onClick={() => setMode("alliance")}>
        Alliance
      </button>
      <button className="btn-outline text-sm py-2" onClick={onPass}>
        Pass
      </button>
      <p className="basis-full text-xs text-royal-dark/60 mt-1">
        Gold budget {giftLeft}g · Card-for-card gifts left {cardsGiftLeft}. Total gold races for
        the crown.
      </p>
    </div>
  );
}
