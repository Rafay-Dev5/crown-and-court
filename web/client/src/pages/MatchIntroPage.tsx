import { motion } from "framer-motion";
import { RulesButton } from "../components/RulesModal";
import { useGameSocket } from "../hooks/useGameSocket";
import { useGameStore } from "../store";

export default function MatchIntroPage() {
  const { beginMatch } = useGameSocket();
  const { matchNumber, matchIntro, meta, playerId, hostId, players } = useGameStore();

  const kingName = matchIntro?.kingName ?? "Unknown";
  const nameFor = (id: string) =>
    meta?.player_names?.[id] || players.find((p) => p.id === id)?.name || "Player";

  return (
    <div className="min-h-screen min-h-[100dvh] flex items-center justify-center p-4 sm:p-6">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="text-center max-w-lg w-full"
      >
        <p className="text-royal-gold font-display text-xl tracking-widest mb-4">
          MATCH {matchNumber} OF {meta?.total_matches ?? 4}
        </p>

        <motion.div
          initial={{ y: -50, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.3, type: "spring" }}
          className="panel-parchment p-5 sm:p-8 mb-6 sm:mb-8"
        >
          <motion.img
            src="/assets/crown.svg"
            alt="Crown"
            className="w-20 h-20 mx-auto mb-4"
            animate={{ rotate: [0, -5, 5, 0] }}
            transition={{ repeat: Infinity, duration: 3 }}
          />
          <h2 className="text-2xl font-display text-royal-dark">
            {kingName} is Starting King
          </h2>
          <p className="text-royal-dark/70 mt-2 italic">
            Round 1 · Turn direction: clockwise
          </p>
          {meta && Object.keys(meta.total_points).length > 0 && (
            <div className="mt-5 text-left text-sm space-y-1.5">
              <p className="font-display text-[11px] uppercase tracking-wider text-royal-dark/50">
                Session score
              </p>
              {Object.entries(meta.total_points)
                .sort((a, b) => b[1] - a[1])
                .map(([id, pts]) => (
                  <div key={id} className="flex justify-between">
                    <span>{nameFor(id)}</span>
                    <span className="font-semibold">{pts} pts</span>
                  </div>
                ))}
            </div>
          )}
          <p className="text-sm text-royal-dark/70 mt-4 leading-relaxed">
            4 rounds. Total gold takes the crown. Cards reveal one by one so the whole table
            can read what happened.
          </p>
        </motion.div>

        {playerId === hostId || !hostId ? (
          <button
            className="btn-royal px-12"
            onClick={() => beginMatch(matchNumber)}
          >
            Begin Match
          </button>
        ) : (
          <p className="text-parchment/70 italic">Waiting for the host to begin…</p>
        )}
        <div className="mt-4">
          <RulesButton />
        </div>
      </motion.div>
    </div>
  );
}
