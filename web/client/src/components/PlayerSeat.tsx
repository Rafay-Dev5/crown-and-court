import { motion } from "framer-motion";
import type { PublicSeat } from "../store/gameStore";
import StatusBadge from "./StatusBadge";

type Props = {
  seat: PublicSeat;
  isYou: boolean;
  isActive: boolean;
  allyNames: string[];
  compact?: boolean;
  /** Extra-small seat for mobile opponent strip */
  dense?: boolean;
};

export default function PlayerSeat({ seat, isYou, isActive, allyNames, compact, dense }: Props) {
  const isKing = seat.role === "king";

  const sizeClass = dense
    ? "p-2 w-full min-w-0"
    : compact
      ? "p-2 sm:p-2.5 w-full min-w-0 md:min-w-[11.5rem] md:max-w-[14rem]"
      : "p-3 w-full";

  return (
    <motion.div
      animate={isActive ? { scale: [1, 1.03, 1] } : { scale: 1 }}
      transition={{ repeat: isActive ? Infinity : 0, duration: 1.6 }}
      className={`rounded-xl backdrop-blur-sm ${sizeClass} ${
        isKing ? "gold-glow bg-royal-dark/95 border-2 border-royal-gold" : "silver-trim bg-royal-dark/90 border border-noble-silver/40"
      } ${isYou ? "ring-2 ring-parchment/40" : ""} ${isActive ? "ring-2 ring-emerald-400" : ""} ${
        allyNames.length > 0 ? "border-l-4 border-l-sky-400" : ""
      }`}
    >
      <div className="flex items-center gap-1.5 sm:gap-2 min-w-0">
        {isKing && <img src="/assets/crown.svg" alt="" className={`${dense ? "w-3.5 h-3.5" : "w-5 h-5"} shrink-0`} />}
        <span className={`font-display font-semibold truncate ${dense ? "text-[11px]" : "text-sm"}`}>
          {seat.player_name}
          {isYou ? " (You)" : ""}
        </span>
        <span
          className={`ml-auto uppercase tracking-wider shrink-0 ${dense ? "text-[9px]" : "text-[10px]"} ${
            isKing ? "text-royal-gold" : "text-noble-silver"
          }`}
        >
          {isKing ? "King" : "Noble"}
        </span>
      </div>
      {isActive && (
        <p className={`uppercase tracking-[0.18em] text-emerald-300 mt-1 ${dense ? "text-[8px]" : "text-[10px]"}`}>
          Acting now
        </p>
      )}

      <div className="mt-1.5 sm:mt-2">
        <p className={dense ? "text-xs" : "text-sm"}>
          <span className={`gold-chip font-bold ${dense ? "text-sm" : ""}`}>{seat.gold}</span>
          <span className="text-parchment/45 text-[10px] ml-1">gold</span>
        </p>
      </div>

      {!dense && (
        <p className="text-[11px] text-parchment/50 mt-1">
          {seat.hand_size} in hand · {seat.deck_size} in deck
        </p>
      )}
      {dense && (
        <p className="text-[9px] text-parchment/50 mt-0.5">{seat.hand_size} cards</p>
      )}

      {allyNames.length > 0 && !dense && (
        <p className="text-[11px] text-sky-300 mt-1 leading-snug">
          Allied with {allyNames.join(", ")}
        </p>
      )}

      {seat.statuses.length > 0 && (
        <div className={`flex flex-wrap gap-1 ${dense ? "mt-1" : "mt-1.5"}`}>
          {seat.statuses.map((s) => {
            const name = typeof s === "string" ? s : s.name;
            return <StatusBadge key={name} status={s} />;
          })}
        </div>
      )}

      {!isYou && !dense && (
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
