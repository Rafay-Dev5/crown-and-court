import { motion } from "framer-motion";
import type { PublicSeat } from "../store/gameStore";

type Props = {
  seat: PublicSeat;
  isYou: boolean;
  position: "top" | "left" | "right" | "bottom";
  isActive: boolean;
};

export default function PlayerSeat({ seat, isYou, position, isActive }: Props) {
  const isKing = seat.role === "king";

  const positionClasses: Record<string, string> = {
    top: "top-4 left-1/2 -translate-x-1/2",
    bottom: "bottom-4 left-1/2 -translate-x-1/2",
    left: "left-4 top-1/2 -translate-y-1/2",
    right: "right-4 top-1/2 -translate-y-1/2",
  };

  return (
    <motion.div
      className={`absolute ${positionClasses[position]} z-10`}
      animate={isActive ? { scale: [1, 1.05, 1] } : {}}
      transition={{ repeat: isActive ? Infinity : 0, duration: 1.5 }}
    >
      <div
        className={`rounded-xl p-3 min-w-[140px] backdrop-blur-sm ${
          isKing ? "gold-glow bg-royal-dark/90 border-2 border-royal-gold" : "silver-trim bg-royal-dark/80 border border-noble-silver/50"
        } ${isYou ? "ring-2 ring-parchment/50" : ""} ${isActive ? "ring-2 ring-green-400" : ""}`}
      >
        <div className="flex items-center gap-2 mb-1">
          {isKing && <img src="/assets/crown.svg" alt="" className="w-5 h-5" />}
          <span className="font-display font-semibold text-sm truncate">{seat.player_name}{isYou ? " (You)" : ""}</span>
        </div>
        <p className={`text-xs uppercase tracking-wide ${isKing ? "text-royal-gold" : "text-noble-silver"}`}>
          {isKing ? "King" : "Noble"}
        </p>
        <p className="text-sm mt-1">
          <span className="text-royal-gold font-bold">{seat.gold}g</span>
          <span className="text-parchment/60 text-xs ml-1">({seat.earned_gold} earned)</span>
        </p>
        <p className="text-xs text-parchment/50 mt-1">
          {seat.hand_size} cards · {seat.deck_size} in deck
        </p>
        {seat.statuses.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
            {seat.statuses.map((s) => (
              <span key={s} className="text-[10px] bg-red-900/50 px-1 rounded">{s}</span>
            ))}
          </div>
        )}
        {!isYou && (
          <div className="flex gap-0.5 mt-2 justify-center">
            {Array.from({ length: Math.min(seat.hand_size, 5) }).map((_, i) => (
              <div key={i} className="card-back w-4 h-6" />
            ))}
            {seat.hand_size > 5 && <span className="text-xs text-parchment/50">+{seat.hand_size - 5}</span>}
          </div>
        )}
      </div>
    </motion.div>
  );
}
