import { motion } from "framer-motion";
import type { PublicSeat } from "../store/gameStore";
import StatusBadge from "./StatusBadge";

type Props = {
  seat: PublicSeat;
  isYou: boolean;
  isActive: boolean;
  allyNames: string[];
  compact?: boolean;
};

export default function PlayerSeat({ seat, isYou, isActive, allyNames, compact }: Props) {
  const isKing = seat.role === "king";

  return (
    <motion.div
      animate={isActive ? { scale: [1, 1.03, 1] } : { scale: 1 }}
      transition={{ repeat: isActive ? Infinity : 0, duration: 1.6 }}
      className={`rounded-xl backdrop-blur-sm ${compact ? "p-2.5 min-w-[11.5rem] max-w-[14rem]" : "p-3 w-full"} ${
        isKing ? "gold-glow bg-royal-dark/95 border-2 border-royal-gold" : "silver-trim bg-royal-dark/90 border border-noble-silver/40"
      } ${isYou ? "ring-2 ring-parchment/40" : ""} ${isActive ? "ring-2 ring-emerald-400" : ""} ${
        allyNames.length > 0 ? "border-l-4 border-l-sky-400" : ""
      }`}
    >
      <div className="flex items-center gap-2">
        {isKing && <img src="/assets/crown.svg" alt="" className="w-5 h-5 shrink-0" />}
        <span className="font-display font-semibold text-sm truncate">
          {seat.player_name}{isYou ? " (You)" : ""}
        </span>
        <span className={`ml-auto text-[10px] uppercase tracking-wider shrink-0 ${isKing ? "text-royal-gold" : "text-noble-silver"}`}>
          {isKing ? "King" : "Noble"}
        </span>
      </div>
      {isActive && (
        <p className="text-[10px] uppercase tracking-[0.18em] text-emerald-300 mt-1">Acting now</p>
      )}

      <div className={`mt-2 grid gap-x-3 ${compact ? "grid-cols-1" : "grid-cols-3"}`}>
        <p className="text-sm">
          <span className="gold-chip font-bold">{seat.gold}</span>
          <span className="text-parchment/45 text-[10px] ml-1">total</span>
        </p>
        <p className="text-sm">
          <span className="text-parchment font-semibold">{seat.earned_gold}</span>
          <span className="text-parchment/45 text-[10px] ml-1">earned</span>
        </p>
        <p className="text-sm">
          <span className="text-parchment/80">{seat.gifted_gold}</span>
          <span className="text-parchment/45 text-[10px] ml-1">gifted</span>
        </p>
      </div>

      <p className="text-[11px] text-parchment/50 mt-1">
        {seat.hand_size} in hand · {seat.deck_size} in deck
      </p>

      {allyNames.length > 0 && (
        <p className="text-[11px] text-sky-300 mt-1 leading-snug">
          Allied with {allyNames.join(", ")}
        </p>
      )}

      {seat.statuses.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-1.5">
          {seat.statuses.map((s) => {
            const name = typeof s === "string" ? s : s.name;
            return <StatusBadge key={name} status={s} />;
          })}
        </div>
      )}

      {!isYou && (
        <div className="flex gap-0.5 mt-2">
          {Array.from({ length: Math.min(seat.hand_size, 6) }).map((_, i) => (
            <div key={i} className="w-3.5 h-5 rounded-sm border border-royal-gold/50 bg-royal-darker" />
          ))}
          {seat.hand_size > 6 && <span className="text-[10px] text-parchment/50">+{seat.hand_size - 6}</span>}
        </div>
      )}
    </motion.div>
  );
}
