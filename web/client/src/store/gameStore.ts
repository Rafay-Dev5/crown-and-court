export type Screen = "home" | "lobby" | "match_intro" | "game" | "match_end" | "game_end";

export type PlayerInfo = {
  id: string;
  name: string;
  seat: number | null;
  ready: boolean;
  connected: boolean;
  is_bot?: boolean;
};

export type StatusInfo = {
  name: string;
  remaining_rounds: number;
};

export type PublicSeat = {
  seat_id: number;
  person_id: number;
  role: string;
  player_id: string;
  player_name: string;
  gold: number;
  earned_gold: number;
  gifted_gold: number;
  gift_sent?: number;
  cards_sent?: number;
  hand_size: number;
  deck_size: number;
  statuses: Array<StatusInfo | string>;
};

export type PublicGameState = {
  current_round: number;
  n_rounds: number;
  phase: string;
  king_seat: number;
  turn_direction: number;
  seats: PublicSeat[];
  alliances: number[][];
  event_log_tail: Record<string, unknown>[];
  pending_proposals: Record<string, unknown>[];
  negotiation_tick: number | null;
  negotiation_ticks: number | null;
  locked_seats?: number[];
  max_negotiation_gift?: number;
  max_negotiation_gift_per_phase?: number;
};

export type PrivateGameState = {
  hand: CardData[];
  seat: number;
  person_id: number;
  peek?: {
    from_seat: number;
    card: CardData;
    card_index?: number;
  } | null;
  discard_choice?: {
    count: number;
    hand: CardData[];
    card?: CardData;
    card_seat?: number;
  } | null;
};

export type CardData = {
  id: string;
  name: string;
  owner_type?: string;
  category?: string;
  rarity?: string;
  timing?: string;
  effect?: Record<string, unknown>;
  on_whiff_penalty?: Record<string, unknown>;
  requires_state?: Record<string, unknown>;
  copies_in_deck?: number;
  flavor_text?: string;
};

export type DecisionInfo = {
  decision_id: string;
  seat: number;
  dtype: string;
  context: Record<string, unknown>;
};

export type MetaState = {
  current_match: number;
  total_matches: number;
  total_points: Record<string, number>;
  king_finish_wins: Record<string, number>;
  noble_points_earned: Record<string, number>;
  player_names: Record<string, string>;
  match_results: Record<string, unknown>[];
};

export type MatchEndPayload = {
  match_number: number;
  winner_player_id: string;
  winner_started_as_king: boolean;
  points_awarded: Record<string, number>;
  placements: Record<string, unknown>[];
  meta: MetaState;
};

export type GameEndPayload = {
  winners: string[];
  winner_names: string[];
  meta: MetaState;
  co_winners: boolean;
};

export type GameStore = {
  screen: Screen;
  playerId: string | null;
  playerName: string;
  reconnectToken: string | null;
  roomCode: string | null;
  hostId: string | null;
  yourSeat: number | null;
  players: PlayerInfo[];
  canStart: boolean;
  connected: boolean;
  error: string | null;
  publicState: PublicGameState | null;
  privateState: PrivateGameState | null;
  decision: DecisionInfo | null;
  decisionPlayerId: string | null;
  decisionPlayerName: string | null;
  events: Record<string, unknown>[];
  meta: MetaState | null;
  matchNumber: number;
  matchIntro: { kingName: string; kingSeat: number } | null;
  matchEnd: MatchEndPayload | null;
  gameEnd: GameEndPayload | null;
  lastSuccession: Record<string, unknown> | null;
  revealAcks: string[];

  setScreen: (s: Screen) => void;
  setPlayerName: (name: string) => void;
  setError: (e: string | null) => void;
  handleLobbyState: (payload: Record<string, unknown>) => void;
  handleMatchIntro: (payload: Record<string, unknown>) => void;
  handleGameState: (payload: Record<string, unknown>) => void;
  handleDecisionRequired: (payload: Record<string, unknown>) => void;
  handleEvent: (payload: Record<string, unknown>) => void;
  handleMatchEnd: (payload: Record<string, unknown>) => void;
  handleGameEnd: (payload: Record<string, unknown>) => void;
  reset: () => void;
};

const initialState = {
  screen: "home" as Screen,
  playerId: null as string | null,
  playerName: "",
  reconnectToken: null as string | null,
  roomCode: null as string | null,
  hostId: null as string | null,
  yourSeat: null as number | null,
  players: [] as PlayerInfo[],
  canStart: false,
  connected: false,
  error: null as string | null,
  publicState: null as PublicGameState | null,
  privateState: null as PrivateGameState | null,
  decision: null as DecisionInfo | null,
  decisionPlayerId: null as string | null,
  decisionPlayerName: null as string | null,
  events: [] as Record<string, unknown>[],
  meta: null as MetaState | null,
  matchNumber: 0,
  matchIntro: null as { kingName: string; kingSeat: number } | null,
  matchEnd: null as MatchEndPayload | null,
  gameEnd: null as GameEndPayload | null,
  lastSuccession: null as Record<string, unknown> | null,
  revealAcks: [] as string[],
};

function eventKey(e: Record<string, unknown>): string {
  return JSON.stringify(e);
}

function mergeEvents(existing: Record<string, unknown>[], incoming: Record<string, unknown>[]): Record<string, unknown>[] {
  const keys = new Set(existing.map(eventKey));
  const next = [...existing];
  for (const ev of incoming) {
    const k = eventKey(ev);
    if (keys.has(k)) continue;
    keys.add(k);
    next.push(ev);
  }
  return next.slice(-50);
}

export function createGameStore(set: (partial: Partial<GameStore> | ((s: GameStore) => Partial<GameStore>)) => void, get: () => GameStore): GameStore {
  return {
    ...initialState,
    setScreen: (screen) => set({ screen }),
    setPlayerName: (playerName) => set({ playerName }),
    setError: (error) => set({ error }),
    reset: () => set({ ...initialState, playerName: get().playerName }),

    handleLobbyState: (payload) => {
      const phase = payload.phase as string;
      let screen: Screen = "lobby";
      if (phase === "match_intro") screen = "match_intro";
      else if (phase === "playing") screen = "game";
      else if (phase === "match_end") screen = "match_end";
      else if (phase === "game_end") screen = "game_end";

      set({
        screen,
        roomCode: payload.code as string,
        hostId: payload.host_id as string,
        playerId: payload.your_id as string,
        yourSeat: (payload.your_seat as number) ?? null,
        players: payload.players as PlayerInfo[],
        canStart: payload.can_start as boolean,
        reconnectToken: (payload.reconnect_token as string) ?? get().reconnectToken,
        meta: (payload.meta as MetaState) ?? get().meta,
        connected: true,
        error: null,
      });
    },

    handleMatchIntro: (payload) => {
      set({
        screen: "match_intro",
        matchNumber: payload.match_number as number,
        matchIntro: {
          kingName: payload.starting_king_name as string,
          kingSeat: payload.starting_king_seat as number,
        },
        meta: payload.meta as MetaState,
      });
    },

    handleGameState: (payload) => {
      const incoming = payload.public as PublicGameState;
      const matchNumber = payload.match_number as number;
      const prev = get();
      let events = prev.matchNumber !== matchNumber ? [] : prev.events;
      if (incoming?.event_log_tail?.length) {
        events = mergeEvents(events, incoming.event_log_tail);
      }
      set({
        screen: "game",
        publicState: incoming,
        privateState: payload.private as PrivateGameState,
        decision: (payload.decision as DecisionInfo) ?? null,
        yourSeat: (payload.your_seat as number) ?? prev.yourSeat,
        matchNumber,
        meta: (payload.meta as MetaState) ?? prev.meta,
        events,
        revealAcks: (payload.reveal_acks as string[]) ?? [],
      });
    },

    handleDecisionRequired: (payload) => {
      set({
        decision: payload.decision as DecisionInfo,
        decisionPlayerId: payload.seat_player_id as string,
        decisionPlayerName: payload.seat_player_name as string,
      });
    },

    handleEvent: (payload) => {
      const event = payload.event as Record<string, unknown>;
      const prev = get().events;
      if (prev.some((e) => eventKey(e) === eventKey(event))) {
        return;
      }
      const events = [...prev, event].slice(-50);
      const updates: Partial<GameStore> = { events };
      if (event.type === "succession" || event.type === "seat_swap") {
        updates.lastSuccession = event;
      }
      set(updates);
    },

    handleMatchEnd: (payload) => {
      set({
        screen: "match_end",
        matchEnd: payload as unknown as MatchEndPayload,
        meta: payload.meta as MetaState,
        decision: null,
      });
    },

    handleGameEnd: (payload) => {
      set({
        screen: "game_end",
        gameEnd: payload as unknown as GameEndPayload,
        meta: payload.meta as MetaState,
      });
    },
  };
}
