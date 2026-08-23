import { describeCardSummary } from "../cardText";
import type { CardData } from "../store/gameStore";

type Props = {
  card: CardData;
  selected?: boolean;
  onClick?: () => void;
  faceDown?: boolean;
  small?: boolean;
};

export default function CardComponent({ card, selected, onClick, faceDown, small }: Props) {
  if (faceDown) {
    return (
      <div
        className={`card-back flex-shrink-0 ${small ? "w-14 h-20" : "w-24 h-36"} flex items-center justify-center`}
      >
        <img src="/assets/card-back.svg" alt="" className="w-8 h-8 opacity-60" />
      </div>
    );
  }

  const categoryColors: Record<string, string> = {
    economy: "border-emerald-600",
    alliance: "border-blue-600",
    betrayal: "border-red-700",
    disruption: "border-orange-600",
    protection: "border-purple-600",
    tempo: "border-cyan-600",
    information: "border-indigo-600",
    supercard: "border-yellow-600",
  };

  const borderClass = categoryColors[card.category ?? ""] ?? "border-royal-gold";

  return (
    <button
      type="button"
      onClick={onClick}
      className={`card-face flex-shrink-0 text-left transition-all duration-200 ${small ? "w-14 h-20 p-1" : "w-24 h-36 p-2"} ${borderClass} border-l-4 ${selected ? "ring-2 ring-royal-gold scale-105 -translate-y-2" : "hover:-translate-y-1"} ${onClick ? "cursor-pointer" : "cursor-default"}`}
    >
      {!small && (
        <>
          <p className="text-[10px] uppercase tracking-wide opacity-60">{card.category}</p>
          <p className="font-display text-xs font-bold leading-tight mt-1">{card.name}</p>
          <p className="text-[9px] mt-1 line-clamp-3 opacity-80">
            {describeCardSummary(card)}
          </p>
        </>
      )}
      {small && (
        <p className="text-[8px] font-bold truncate">{card.name}</p>
      )}
    </button>
  );
}
