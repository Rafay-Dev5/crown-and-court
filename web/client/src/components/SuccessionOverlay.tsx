import { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useGameStore } from "../store";
import { playSuccessionFanfare } from "../audio";

type Props = {
  event: Record<string, unknown> | null;
  onDismiss: () => void;
};

const SPARKS = [
  { x: -140, y: 30, delay: 0.35 },
  { x: -90, y: -20, delay: 0.5 },
  { x: -40, y: 50, delay: 0.42 },
  { x: 20, y: -36, delay: 0.58 },
  { x: 70, y: 24, delay: 0.46 },
  { x: 120, y: -8, delay: 0.64 },
  { x: 150, y: 46, delay: 0.4 },
  { x: -160, y: -12, delay: 0.7 },
];

export default function SuccessionOverlay({ event, onDismiss }: Props) {
  const seats = useGameStore((s) => s.publicState?.seats);

  useEffect(() => {
    if (!event) return;
    playSuccessionFanfare();
  }, [event]);

  if (!event) return null;

  const newKingSeat = (event.new_king_seat ?? event.ascending_seat) as number | undefined;
  const formerSeat = event.former_king_seat as number | undefined;
  const nameFor = (seat: number | undefined) => {
    if (typeof seat !== "number") return null;
    return seats?.find((s) => s.seat_id === seat)?.player_name ?? `Seat ${seat}`;
  };
  const newKing = nameFor(newKingSeat);
  const formerKing = nameFor(formerSeat);

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-end md:items-center justify-center bg-black/75 p-0 md:p-4 overflow-hidden"
        onClick={onDismiss}
      >
        <motion.div
          className="pointer-events-none absolute inset-0"
          initial={{ opacity: 0 }}
          animate={{ opacity: [0, 0.85, 0.55] }}
          transition={{ duration: 1.4 }}
          style={{
            background:
              "radial-gradient(circle at 50% 42%, rgba(232,197,71,0.45) 0%, rgba(201,162,39,0.12) 28%, transparent 58%)",
          }}
        />
        <motion.div
          className="pointer-events-none absolute left-1/2 top-[38%] h-40 w-40 -translate-x-1/2 -translate-y-1/2 rounded-full border border-royal-gold/70"
          initial={{ scale: 0.2, opacity: 0.9 }}
          animate={{ scale: 3.2, opacity: 0 }}
          transition={{ duration: 1.6, ease: "easeOut" }}
        />

        <motion.div
          initial={{ scale: 0.86, y: 48, opacity: 0 }}
          animate={{ scale: 1, y: 0, opacity: 1 }}
          exit={{ opacity: 0, y: 24 }}
          transition={{ type: "spring", stiffness: 220, damping: 22 }}
          className="panel-parchment relative p-6 md:p-8 text-center w-full max-w-md rounded-t-2xl md:rounded-xl overflow-hidden"
          onClick={(e) => e.stopPropagation()}
        >
          <motion.div
            className="pointer-events-none absolute inset-y-0 w-1/3 bg-gradient-to-r from-transparent via-white/50 to-transparent"
            initial={{ x: "-120%" }}
            animate={{ x: "320%" }}
            transition={{ duration: 1.1, delay: 0.35, ease: "easeInOut" }}
          />

          <motion.p
            className="font-display text-xs sm:text-sm tracking-[0.45em] text-royal-gold mb-3"
            initial={{ letterSpacing: "0.2em", opacity: 0 }}
            animate={{ letterSpacing: "0.45em", opacity: 1 }}
            transition={{ duration: 0.7 }}
          >
            THE CROWN PASSES
          </motion.p>

          <div className="relative mx-auto mb-4 h-24 w-24">
            {SPARKS.map((spark) => (
              <motion.span
                key={`${spark.x}-${spark.y}`}
                className="absolute left-1/2 top-1/2 h-1.5 w-1.5 rounded-full bg-royal-gold-light shadow-[0_0_8px_#e8c547]"
                initial={{ x: 0, y: 8, opacity: 0, scale: 0.4 }}
                animate={{ x: spark.x * 0.35, y: spark.y - 28, opacity: [0, 1, 0], scale: 1 }}
                transition={{ duration: 1.35, delay: spark.delay, ease: "easeOut" }}
              />
            ))}
            <motion.img
              src="/assets/crown.svg"
              alt=""
              className="relative z-10 mx-auto h-20 w-20 drop-shadow-[0_8px_16px_rgba(201,162,39,0.55)]"
              initial={{ y: -160, scale: 0.4, opacity: 0, rotate: -16 }}
              animate={{ y: 0, scale: 1, opacity: 1, rotate: 0 }}
              transition={{ type: "spring", stiffness: 220, damping: 14, delay: 0.15 }}
            />
          </div>

          <motion.p
            className="text-xl sm:text-2xl font-display text-royal-dark"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.55, duration: 0.45 }}
          >
            {newKing ? `${newKing} takes the crown!` : "The crown changes hands!"}
          </motion.p>
          {formerKing && newKing && (
            <motion.p
              className="text-sm text-royal-dark/70 mt-2"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.85 }}
            >
              {formerKing} becomes a Noble
            </motion.p>
          )}
          <p className="text-sm text-royal-dark/70 mt-2 italic">
            Decks and hands swap. Gold stays with each player.
          </p>
          <button className="btn-royal mt-6" onClick={onDismiss}>
            Continue
          </button>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
