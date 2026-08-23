import { motion, AnimatePresence } from "framer-motion";

type Props = {
  event: Record<string, unknown> | null;
  onDismiss: () => void;
};

export default function SuccessionOverlay({ event, onDismiss }: Props) {
  if (!event) return null;

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
            ⚔ SUCCESSION CHECK ⚔
          </p>
          <motion.img
            src="/assets/crown.svg"
            alt=""
            className="w-16 h-16 mx-auto mb-4"
            animate={{ rotate: [0, 10, -10, 0], scale: [1, 1.2, 1] }}
            transition={{ duration: 1.5 }}
          />
          <p className="text-lg font-display text-royal-dark">
            The crown changes hands!
          </p>
          <p className="text-sm text-royal-dark/70 mt-2 italic">
            Decks & hands swap · Gold stays with the player
          </p>
          <button className="btn-royal mt-6" onClick={onDismiss}>Continue</button>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
