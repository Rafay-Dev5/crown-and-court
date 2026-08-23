import { useEffect } from "react";
import { useGameSocket } from "./hooks/useGameSocket";
import { useGameStore } from "./store";
import HomePage from "./pages/HomePage";
import LobbyPage from "./pages/LobbyPage";
import MatchIntroPage from "./pages/MatchIntroPage";
import GamePage from "./pages/GamePage";
import MatchEndPage from "./pages/MatchEndPage";
import GameEndPage from "./pages/GameEndPage";

export default function App() {
  // Single socket subscription for the whole app (do not call useGameSocket twice).
  useGameSocket();
  const screen = useGameStore((s) => s.screen);
  const setPlayerName = useGameStore((s) => s.setPlayerName);
  const playerName = useGameStore((s) => s.playerName);

  useEffect(() => {
    if (playerName) localStorage.setItem("cc_player_name", playerName);
  }, [playerName]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    if (!code) return;
    const savedName = localStorage.getItem("cc_player_name");
    if (savedName && !playerName) {
      setPlayerName(savedName);
    }
  }, [playerName, setPlayerName]);

  switch (screen) {
    case "lobby":
      return <LobbyPage />;
    case "match_intro":
      return <MatchIntroPage />;
    case "game":
      return <GamePage />;
    case "match_end":
      return <MatchEndPage />;
    case "game_end":
      return <GameEndPage />;
    default:
      return <HomePage />;
  }
}
