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
  useGameSocket();
  const { screen, setPlayerName } = useGameStore();
  const { joinLobby: join } = useGameSocket();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    if (code && screen === "home") {
      const savedName = localStorage.getItem("cc_player_name");
      if (savedName) {
        setPlayerName(savedName);
        join(code, savedName);
      }
    }
  }, [screen, setPlayerName, join]);

  useEffect(() => {
    const name = useGameStore.getState().playerName;
    if (name) localStorage.setItem("cc_player_name", name);
  });

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
