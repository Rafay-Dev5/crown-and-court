import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { RulesButton } from "../components/RulesModal";
import { useGameSocket } from "../hooks/useGameSocket";
import { useGameStore } from "../store";

export default function HomePage() {
  const [mode, setMode] = useState<"menu" | "create" | "join">("menu");
  const [joinCode, setJoinCode] = useState("");
  const { createLobby, practiceVsBots, joinLobby, connected } = useGameSocket();
  const { playerName, setPlayerName, error, setError } = useGameStore();

  useEffect(() => {
    const saved = localStorage.getItem("cc_player_name");
    if (saved && !playerName) setPlayerName(saved);
  }, [playerName, setPlayerName]);

  // Prefill join from invite link ?code=ABCD
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    if (code) {
      setJoinCode(code.toUpperCase());
      setMode("join");
    }
  }, []);

  const handleCreate = () => {
    if (!playerName.trim()) return;
    setError(null);
    createLobby(playerName.trim());
  };

  const handlePractice = () => {
    if (!playerName.trim()) return;
    setError(null);
    practiceVsBots(playerName.trim());
  };

  const handleJoin = () => {
    if (!playerName.trim() || !joinCode.trim()) return;
    setError(null);
    joinLobby(joinCode.trim().toUpperCase(), playerName.trim());
  };

  return (
    <div className="min-h-screen min-h-[100dvh] flex flex-col items-center justify-center p-4 sm:p-6">
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center mb-6 sm:mb-8"
      >
        <img src="/assets/crown.svg" alt="" className="w-12 h-12 sm:w-16 sm:h-16 mx-auto mb-3 sm:mb-4" />
        <h1 className="text-3xl sm:text-5xl font-display text-royal-gold tracking-wider mb-2 px-2">
          Crown & Court
        </h1>
        <p className="text-parchment/80 text-base sm:text-lg italic px-4">
          Gold, bluffing, alliances, and succession
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="panel-parchment p-5 sm:p-8 w-full max-w-md shadow-2xl"
      >
        {!connected && (
          <p className="text-center text-sm mb-4 text-amber-800">Connecting to server...</p>
        )}
        {error && (
          <p className="text-center text-sm mb-4 text-red-700 bg-red-100 rounded p-2">{error}</p>
        )}

        <label className="block mb-4">
          <span className="text-sm font-semibold">Your Name</span>
          <input
            type="text"
            value={playerName}
            onChange={(e) => setPlayerName(e.target.value)}
            maxLength={24}
            placeholder="Enter display name"
            className="mt-1 w-full px-4 py-2 rounded-lg border-2 border-royal-gold/50 bg-white/80 text-royal-dark focus:outline-none focus:border-royal-gold"
          />
        </label>

        {mode === "menu" && (
          <div className="flex flex-col gap-3">
            <button className="btn-royal w-full" onClick={() => setMode("create")} disabled={!connected}>
              Create Lobby
            </button>
            <button
              className="btn-royal w-full"
              onClick={handlePractice}
              disabled={!playerName.trim() || !connected}
            >
              Practice vs Bots
            </button>
            <button className="btn-outline w-full" onClick={() => setMode("join")} disabled={!connected}>
              Join with Code
            </button>
            <div className="text-center mt-1">
              <RulesButton />
            </div>
          </div>
        )}

        {mode === "create" && (
          <div className="flex flex-col gap-3">
            <button className="btn-royal w-full" onClick={handleCreate} disabled={!playerName.trim() || !connected}>
              Create & Enter Lobby
            </button>
            <button className="btn-outline w-full" onClick={() => setMode("menu")}>
              Back
            </button>
          </div>
        )}

        {mode === "join" && (
          <div className="flex flex-col gap-3">
            <input
              type="text"
              value={joinCode}
              onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
              placeholder="Room code (e.g. ABCD)"
              className="w-full px-4 py-2 rounded-lg border-2 border-royal-gold/50 bg-white/80 text-royal-dark focus:outline-none focus:border-royal-gold uppercase tracking-widest text-center"
            />
            <button
              className="btn-royal w-full"
              onClick={handleJoin}
              disabled={!playerName.trim() || !joinCode.trim() || !connected}
            >
              Join Lobby
            </button>
            <button className="btn-outline w-full" onClick={() => setMode("menu")}>
              Back
            </button>
          </div>
        )}
      </motion.div>

      <div className="mt-8 text-center text-parchment/60 text-sm max-w-md">
        <p>4 players · 4 matches · 4 rounds each</p>
        <p className="mt-2">First to 10 points wins the game. Everyone gets to be King once.</p>
        <p className="mt-2 text-parchment/45">
          Practice seats you against The Hoarder, The Aggressor, and The Diplomat — a full
          four-match table so you can see negotiation, reveals, and succession.
        </p>
      </div>
    </div>
  );
}
