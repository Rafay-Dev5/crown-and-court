import { motion } from "framer-motion";
import { RulesButton } from "../components/RulesModal";
import { useGameSocket } from "../hooks/useGameSocket";
import { useGameStore } from "../store";

export default function MatchEndPage() {
  const { nextMatch } = useGameSocket();
  const { matchEnd, meta, players } = useGameStore();

  if (!matchEnd) return null;

  const upcoming = matchEnd.match_number + 1;
  const gameOver = meta && Object.values(meta.total_points).some((p) => p >= 10);
  const allMatchesDone = matchEnd.match_number >= (meta?.total_matches ?? 4);

  const winnerName =
    players.find((p) => p.id === matchEnd.winner_player_id)?.name ??
    meta?.player_names?.[matchEnd.winner_player_id] ??
    "Unknown";

  return (
    <div className="min-h-screen min-h-[100dvh] flex items-center justify-center p-4 sm:p-6">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="panel-parchment p-5 sm:p-8 w-full max-w-xl"
      >
        <p className="font-display text-xs tracking-[0.25em] text-center text-royal-dark/50 uppercase">
          Match {matchEnd.match_number} of 4
        </p>
        <h2 className="text-2xl sm:text-3xl font-display text-center text-royal-dark mb-2 mt-1">
          The crown is decided
        </h2>
        <p className="text-center text-royal-dark/80 mb-2">
          Winner: <strong>{winnerName}</strong>
          {matchEnd.winner_started_as_king ? " (defended as King)" : " (rose from Noble)"}
        </p>
        <p className="text-center mb-6">
          <span className="text-royal-gold font-bold text-xl">
            +{matchEnd.points_awarded[matchEnd.winner_player_id]} pts
          </span>
        </p>

        <table className="w-full text-sm mb-6">
          <thead>
            <tr className="border-b border-royal-gold/30">
              <th className="text-left py-2">Player</th>
              <th className="text-right py-2">Match</th>
              <th className="text-right py-2">Total</th>
            </tr>
          </thead>
          <tbody>
            {matchEnd.placements
              .slice()
              .sort((a, b) => (b.points_earned as number) - (a.points_earned as number))
              .map((p, i) => (
                <tr key={i} className="border-b border-royal-gold/10">
                  <td className="py-2">{p.player_name as string}</td>
                  <td className="text-right py-2 text-royal-gold font-semibold">
                    +{p.points_earned as number}
                  </td>
                  <td className="text-right py-2 font-bold">
                    {meta?.total_points[p.player_id as string] ?? 0}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>

        {!gameOver && !allMatchesDone && (
          <div className="text-center">
            <button className="btn-royal" onClick={() => nextMatch()}>
              Next Match ({upcoming} of 4)
            </button>
            <p className="text-xs text-royal-dark/50 mt-2">
              Any player can continue — everyone advances together. The next starting King rotates.
            </p>
            <div className="mt-3">
              <RulesButton />
            </div>
          </div>
        )}

        {(gameOver || allMatchesDone) && (
          <p className="text-center text-royal-dark/70 italic">
            {gameOver ? "A player reached 10 points!" : "All 4 matches complete."}
            {" "}Final results incoming...
          </p>
        )}
      </motion.div>
    </div>
  );
}
