import { motion, AnimatePresence } from "framer-motion";
import { useGameStore } from "../store";

type Props = {
  event: Record<string, unknown> | null;
  onDismiss: () => void;
};

export default function SuccessionOverlay({ event, onDismiss }: Props) {
  const seats = useGameStore((s) => s.publicState?.seats);
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
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
        onClick={onDismiss}
      >
        <motion.div
          initial={{ scale: 0.8, y: 20 }}
          animate={{ scale: 1, y: 0 }}
          className="panel-parchment p-8 text-center max-w-md mx-4"
          onClick={(e) => e.stopPropagation()}
        >
          <p className="font-display text-xl text-royal-dark tracking-widest mb-4">
            SUCCESSION
          </p>
          <motion.img
            src="/assets/crown.svg"
            alt=""
            className="w-16 h-16 mx-auto mb-4"
            animate={{ rotate: [0, 10, -10, 0], scale: [1, 1.2, 1] }}
            transition={{ duration: 1.5 }}
          />
          <p className="text-lg font-display text-royal-dark">
            {newKing ? `${newKing} takes the crown!` : "The crown changes hands!"}
          </p>
          {formerKing && newKing && (
            <p className="text-sm text-royal-dark/70 mt-2">
              {formerKing} becomes a Noble
            </p>
          )}
          <p className="text-sm text-royal-dark/70 mt-2 italic">
            Decks & hands swap · Gold stays with each player
          </p>
          <button className="btn-royal mt-6" onClick={onDismiss}>Continue</button>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
