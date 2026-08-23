import { useState } from "react";
import { motion } from "framer-motion";
import { useGameSocket } from "../hooks/useGameSocket";
import { useGameStore } from "../store";

export default function LobbyPage() {
  const { toggleReady, startGame } = useGameSocket();
  const { roomCode, players, playerId, hostId, canStart } = useGameStore();
  const [copied, setCopied] = useState(false);

  const me = players.find((p) => p.id === playerId);
  const inviteLink = `${window.location.origin}?code=${roomCode}`;

  // Seats are assigned only when the match starts; until then show join order.
  const slots: Array<(typeof players)[number] | null> = Array.from({ length: 4 }, (_, i) => {
    const bySeat = players.find((p) => p.seat === i);
    if (bySeat) return bySeat;
    // Fallback: fill empty seats with players who don't have seats yet
    const unseated = players.filter((p) => p.seat === null || p.seat === undefined);
    return unseated[i] ?? null;
  });

  // Deduplicate if some have seats and some don't
  const shownIds = new Set<string>();
  const displaySlots = slots.map((p) => {
    if (!p) return null;
    if (shownIds.has(p.id)) return null;
    shownIds.add(p.id);
    return p;
  });
  // Put any remaining unseated players into empty slots
  for (const p of players) {
    if (shownIds.has(p.id)) continue;
    const emptyIdx = displaySlots.findIndex((s) => s === null);
    if (emptyIdx >= 0) {
      displaySlots[emptyIdx] = p;
      shownIds.add(p.id);
    }
  }

  const copyInvite = async () => {
    await navigator.clipboard.writeText(inviteLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="w-full max-w-2xl"
      >
        <div className="text-center mb-6">
          <h1 className="text-3xl font-display text-royal-gold">Lobby</h1>
          <p className="text-2xl tracking-[0.3em] font-display text-parchment mt-2">{roomCode}</p>
          <p className="text-parchment/60 text-sm mt-1">
            {players.length}/4 players · Waiting to start
          </p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {displaySlots.map((player, i) => {
            const isYou = player?.id === playerId;
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.1 }}
                className={`panel-parchment p-4 text-center ${isYou ? "ring-2 ring-royal-gold" : ""}`}
              >
                {player ? (
                  <>
                    <div className="w-12 h-12 mx-auto mb-2 rounded-full bg-royal-dark/10 flex items-center justify-center">
                      <img src={`/assets/avatar-${(i % 4) + 1}.svg`} alt="" className="w-8 h-8" />
                    </div>
                    <p className="font-semibold truncate">
                      {player.name}
                      {isYou ? " (You)" : ""}
                      {player.id === hostId ? " ★" : ""}
                    </p>
                    <p className={`text-xs mt-1 ${player.ready ? "text-green-700" : "text-amber-700"}`}>
                      {player.ready ? "READY" : "Not ready"}
                    </p>
                    {!player.connected && (
                      <p className="text-xs text-red-600">Disconnected</p>
                    )}
                  </>
                ) : (
                  <>
                    <div className="w-12 h-12 mx-auto mb-2 rounded-full border-2 border-dashed border-royal-gold/40 flex items-center justify-center text-royal-gold/40">
                      ?
                    </div>
                    <p className="text-royal-dark/50 italic">Waiting...</p>
                  </>
                )}
              </motion.div>
            );
          })}
        </div>

        <div className="flex flex-col sm:flex-row gap-3 justify-center mb-4 items-center">
          <button className="btn-outline" onClick={copyInvite}>
            {copied ? "Link Copied!" : "Copy Invite Link"}
          </button>
          <button className="btn-royal" onClick={toggleReady}>
            {me?.ready ? "Unready" : "Ready Up"}
          </button>
        </div>
        <p className="text-center text-xs text-parchment/50 mb-4 break-all px-4">
          Share this link with friends: {inviteLink}
        </p>

        {playerId === hostId && (
          <div className="text-center">
            <button
              className="btn-royal px-12"
              onClick={startGame}
              disabled={!canStart}
            >
              Start Game
            </button>
            {!canStart && (
              <p className="text-sm text-parchment/60 mt-2">
                Need 4 players, all ready ({players.filter((p) => p.ready).length}/4 ready)
              </p>
            )}
          </div>
        )}
      </motion.div>
    </div>
  );
}
