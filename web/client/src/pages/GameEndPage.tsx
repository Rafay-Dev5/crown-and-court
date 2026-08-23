import { motion } from "framer-motion";
import { useGameStore } from "../store";

export default function GameEndPage() {
  const { gameEnd, reset } = useGameStore();

  if (!gameEnd) return null;

  const standings = Object.entries(gameEnd.meta.total_points)
    .map(([id, pts]) => ({
      id,
      name: gameEnd.meta.player_names[id] ?? id,
      points: pts,
      kingWins: gameEnd.meta.king_finish_wins[id] ?? 0,
      noblePts: gameEnd.meta.noble_points_earned[id] ?? 0,
      isWinner: gameEnd.winners.includes(id),
    }))
    .sort((a, b) => b.points - a.points);

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="text-center max-w-2xl w-full"
      >
        <motion.img
          src="/assets/crown.svg"
          alt=""
          className="w-24 h-24 mx-auto mb-4"
          animate={{ scale: [1, 1.1, 1] }}
          transition={{ repeat: Infinity, duration: 2 }}
        />

        <h1 className="text-4xl font-display text-royal-gold mb-2">
          {gameEnd.co_winners ? "Shared Victory!" : "Grand Victory!"}
        </h1>
        <p className="text-2xl text-parchment mb-8">
          {gameEnd.winner_names.join(" & ")} {gameEnd.co_winners ? "Win" : "Wins"}!
        </p>

        <div className="panel-parchment p-6 text-left">
          <h3 className="font-display text-lg text-royal-dark mb-4 text-center">Final Standings</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-royal-gold/30">
                <th className="py-2 text-left">Player</th>
                <th className="py-2 text-right">Points</th>
                <th className="py-2 text-right">King Wins</th>
                <th className="py-2 text-right">Noble Pts</th>
              </tr>
            </thead>
            <tbody>
              {standings.map((s) => (
                <tr
                  key={s.id}
                  className={`border-b border-royal-gold/10 ${s.isWinner ? "bg-royal-gold/10" : ""}`}
                >
                  <td className="py-2 font-semibold">
                    {s.isWinner && "👑 "}{s.name}
                  </td>
                  <td className="py-2 text-right font-bold">{s.points}</td>
                  <td className="py-2 text-right">{s.kingWins}</td>
                  <td className="py-2 text-right">{s.noblePts}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <button
          className="btn-royal mt-8"
          onClick={() => {
            localStorage.removeItem("cc_reconnect_token");
            localStorage.removeItem("cc_room_code");
            localStorage.removeItem("cc_player_id");
            reset();
            window.location.href = "/";
          }}
        >
          Play Again
        </button>
      </motion.div>
    </div>
  );
}
