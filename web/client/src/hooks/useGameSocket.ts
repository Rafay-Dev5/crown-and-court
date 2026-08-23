import { useCallback, useEffect, useRef } from "react";
import { useGameStore } from "../store";

function resolveWebSocketUrl(): string {
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL;
  }

  const { protocol, hostname, port, host } = window.location;
  const wsProtocol = protocol === "https:" ? "wss:" : "ws:";

  // Vite dev server (5173) — proxy WebSocket to the Python backend on 8000.
  if (import.meta.env.DEV && port === "5173") {
    return `${wsProtocol}//${hostname}:8000/ws`;
  }

  // Production: same origin (client + server share one URL).
  return `${wsProtocol}//${host}/ws`;
}

type OutgoingMessage = {
  type: string;
  payload?: Record<string, unknown>;
};

export function useGameSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const store = useGameStore();

  const send = useCallback((msg: OutgoingMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(resolveWebSocketUrl());
    wsRef.current = ws;

    ws.onopen = () => {
      useGameStore.setState({ connected: true, error: null });
      const token = localStorage.getItem("cc_reconnect_token");
      const roomCode = localStorage.getItem("cc_room_code");
      const playerId = localStorage.getItem("cc_player_id");
      if (token && roomCode && playerId) {
        send({ type: "reconnect", payload: { token } });
      }
    };

    ws.onclose = () => {
      useGameStore.setState({ connected: false });
    };

    ws.onerror = () => {
      useGameStore.setState({ error: "Connection failed — is the server running?" });
    };

    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      const s = useGameStore.getState();
      switch (msg.type) {
        case "error":
          s.setError(msg.payload?.message ?? "Unknown error");
          break;
        case "lobby_state":
          s.handleLobbyState(msg.payload);
          if (msg.payload.reconnect_token) {
            localStorage.setItem("cc_reconnect_token", msg.payload.reconnect_token);
          }
          if (msg.payload.code) {
            localStorage.setItem("cc_room_code", msg.payload.code);
          }
          if (msg.payload.your_id) {
            localStorage.setItem("cc_player_id", msg.payload.your_id);
          }
          break;
        case "match_intro":
          s.handleMatchIntro(msg.payload);
          break;
        case "game_state":
          s.handleGameState(msg.payload);
          break;
        case "decision_required":
          s.handleDecisionRequired(msg.payload);
          break;
        case "event":
          s.handleEvent(msg.payload);
          break;
        case "match_end":
          s.handleMatchEnd(msg.payload);
          break;
        case "game_end":
          s.handleGameEnd(msg.payload);
          break;
      }
    };
  }, [send]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [connect]);

  const createLobby = useCallback(
    (name: string) => {
      send({ type: "join", payload: { action: "create", name } });
    },
    [send]
  );

  const joinLobby = useCallback(
    (code: string, name: string) => {
      send({ type: "join", payload: { action: "join", code, name } });
    },
    [send]
  );

  const toggleReady = useCallback(() => {
    send({ type: "ready" });
  }, [send]);

  const startGame = useCallback(() => {
    send({ type: "start" });
  }, [send]);

  const beginMatch = useCallback(
    (matchNumber: number) => {
      send({ type: "begin_match", payload: { match_number: matchNumber } });
    },
    [send]
  );

  const sendAction = useCallback(
    (actionType: string, data: Record<string, unknown> = {}) => {
      send({ type: "action", payload: { action_type: actionType, data } });
    },
    [send]
  );

  const acceptProposal = useCallback(
    (proposalId: string) => {
      send({ type: "accept_proposal", payload: { proposal_id: proposalId } });
    },
    [send]
  );

  const rejectProposal = useCallback(
    (proposalId: string) => {
      send({ type: "reject_proposal", payload: { proposal_id: proposalId } });
    },
    [send]
  );

  return {
    send,
    createLobby,
    joinLobby,
    toggleReady,
    startGame,
    beginMatch,
    sendAction,
    acceptProposal,
    rejectProposal,
    connected: store.connected,
  };
}
