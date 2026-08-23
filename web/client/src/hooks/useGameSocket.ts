import { useCallback, useEffect, useRef, useState } from "react";
import { useGameStore } from "../store";

function resolveWebSocketUrl(): string {
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL;
  }

  const { protocol, hostname, port, host } = window.location;
  const wsProtocol = protocol === "https:" ? "wss:" : "ws:";

  // Vite dev server proxies API separately; connect directly to backend.
  if (import.meta.env.DEV && (port === "5173" || port === "4173")) {
    return `${wsProtocol}//${hostname}:8000/ws`;
  }

  // Production: same origin (FastAPI serves UI + /ws).
  return `${wsProtocol}//${host}/ws`;
}

type OutgoingMessage = {
  type: string;
  payload?: Record<string, unknown>;
};

/** Module singleton so StrictMode remounts / multiple hook calls share one socket. */
let sharedWs: WebSocket | null = null;
let sharedListeners = 0;
const pendingOutbox: OutgoingMessage[] = [];

function flushOutbox(ws: WebSocket) {
  while (pendingOutbox.length > 0 && ws.readyState === WebSocket.OPEN) {
    const msg = pendingOutbox.shift()!;
    ws.send(JSON.stringify(msg));
  }
}

function ensureSharedSocket() {
  if (sharedWs && (sharedWs.readyState === WebSocket.OPEN || sharedWs.readyState === WebSocket.CONNECTING)) {
    return sharedWs;
  }

  const ws = new WebSocket(resolveWebSocketUrl());
  sharedWs = ws;

  ws.onopen = () => {
    useGameStore.setState({ connected: true, error: null });
    flushOutbox(ws);

    const token = localStorage.getItem("cc_reconnect_token");
    if (token) {
      ws.send(JSON.stringify({ type: "reconnect", payload: { token } }));
    }
  };

  ws.onclose = () => {
    useGameStore.setState({ connected: false });
    if (sharedWs === ws) sharedWs = null;
  };

  ws.onerror = () => {
    useGameStore.setState({ error: "Connection failed — is the server running?" });
  };

  ws.onmessage = (ev) => {
    let msg: { type: string; payload?: Record<string, unknown> };
    try {
      msg = JSON.parse(ev.data);
    } catch {
      return;
    }
    const s = useGameStore.getState();
    switch (msg.type) {
      case "error": {
        const message = (msg.payload?.message as string) ?? "Unknown error";
        // Stale reconnect after server restart — clear and stay on home.
        if (
          message.includes("Invalid reconnect") ||
          message.includes("Room no longer") ||
          message.includes("Player not found")
        ) {
          localStorage.removeItem("cc_reconnect_token");
          localStorage.removeItem("cc_room_code");
          localStorage.removeItem("cc_player_id");
          useGameStore.setState({
            reconnectToken: null,
            roomCode: null,
            error: null,
            screen: "home",
          });
          break;
        }
        s.setError(message);
        break;
      }
      case "lobby_state":
        s.handleLobbyState(msg.payload ?? {});
        if (msg.payload?.reconnect_token) {
          localStorage.setItem("cc_reconnect_token", String(msg.payload.reconnect_token));
        }
        if (msg.payload?.code) {
          localStorage.setItem("cc_room_code", String(msg.payload.code));
        }
        if (msg.payload?.your_id) {
          localStorage.setItem("cc_player_id", String(msg.payload.your_id));
        }
        break;
      case "match_intro":
        s.handleMatchIntro(msg.payload ?? {});
        break;
      case "game_state":
        s.handleGameState(msg.payload ?? {});
        break;
      case "decision_required":
        s.handleDecisionRequired(msg.payload ?? {});
        break;
      case "event":
        s.handleEvent(msg.payload ?? {});
        break;
      case "match_end":
        s.handleMatchEnd(msg.payload ?? {});
        break;
      case "game_end":
        s.handleGameEnd(msg.payload ?? {});
        break;
    }
  };

  return ws;
}

function sendShared(msg: OutgoingMessage) {
  const ws = ensureSharedSocket();
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(msg));
  } else {
    pendingOutbox.push(msg);
  }
}

export function useGameSocket() {
  const [connected, setConnected] = useState(useGameStore.getState().connected);
  const subscribed = useRef(false);

  useEffect(() => {
    if (subscribed.current) return;
    subscribed.current = true;
    sharedListeners += 1;
    ensureSharedSocket();

    const unsub = useGameStore.subscribe((state) => setConnected(state.connected));

    return () => {
      unsub();
      subscribed.current = false;
      sharedListeners = Math.max(0, sharedListeners - 1);
      // Keep socket alive across StrictMode remount; only close when no listeners left.
      if (sharedListeners === 0 && sharedWs) {
        // Delay so StrictMode remount can reclaim the same socket.
        const toClose = sharedWs;
        setTimeout(() => {
          if (sharedListeners === 0 && sharedWs === toClose) {
            toClose.close();
            sharedWs = null;
          }
        }, 250);
      }
    };
  }, []);

  const createLobby = useCallback((name: string) => {
    localStorage.removeItem("cc_reconnect_token");
    sendShared({ type: "join", payload: { action: "create", name } });
  }, []);

  const joinLobby = useCallback((code: string, name: string) => {
    localStorage.removeItem("cc_reconnect_token");
    sendShared({ type: "join", payload: { action: "join", code, name } });
  }, []);

  const toggleReady = useCallback(() => {
    const me = useGameStore.getState().players.find(
      (p) => p.id === useGameStore.getState().playerId
    );
    const next = !(me?.ready ?? false);
    sendShared({ type: "ready", payload: { ready: next } });
  }, []);

  const startGame = useCallback(() => {
    sendShared({ type: "start" });
  }, []);

  const beginMatch = useCallback((matchNumber: number) => {
    sendShared({ type: "begin_match", payload: { match_number: matchNumber } });
  }, []);

  const sendAction = useCallback((actionType: string, data: Record<string, unknown> = {}) => {
    sendShared({ type: "action", payload: { action_type: actionType, data } });
  }, []);

  const acceptProposal = useCallback((proposalId: string) => {
    sendShared({ type: "accept_proposal", payload: { proposal_id: proposalId } });
  }, []);

  const rejectProposal = useCallback((proposalId: string) => {
    sendShared({ type: "reject_proposal", payload: { proposal_id: proposalId } });
  }, []);

  return {
    send: sendShared,
    createLobby,
    joinLobby,
    toggleReady,
    startGame,
    beginMatch,
    sendAction,
    acceptProposal,
    rejectProposal,
    connected,
  };
}
