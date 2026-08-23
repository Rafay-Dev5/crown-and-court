import { create } from "zustand";
import { createGameStore, type GameStore } from "./gameStore";

export const useGameStore = create<GameStore>((set, get) => createGameStore(set, get));
