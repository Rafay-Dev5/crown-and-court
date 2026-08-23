import { useMemo, useState } from "react";
import {
  describeCardFull,
  describeCardSummary,
} from "./cardText";
import BalanceResults from "./BalanceResults";
import ReplayViewer from "./ReplayViewer";
import TrainingLive from "./TrainingLive";

type Card = {
  id: string;
  name: string;
  owner_type: string;
  category: string;
  rarity: string;
  timing: string;
  copies_in_deck: number;
  effect: Record<string, unknown>;
  on_whiff_penalty?: Record<string, unknown>;
  requires_state?: Record<string, unknown>;
  tags?: string[];
  synergy_tags?: string[];
  flavor_text?: string;
  designer_notes?: string;
};

const VALID_PRIMITIVES = new Set([
  "gold_gain", "gold_loss", "gold_transfer", "steal_card", "force_discard",
  "draw_extra", "peek_card", "reveal_hand", "negate_effect", "redirect_effect",
  "copy_last_effect", "swap_hands", "block_succession", "protect_gold",
  "mark_status", "alliance_bonus", "skip_next_play", "gain_legitimacy",
  "extra_play", "conditional_swing", "prompt_choice", "roll_die", "dice_swing",
  "conditional_on_choice", "conditional_on_status", "on_whiff_penalty",
]);

const cardModules = import.meta.glob("../../cards/{king_deck,noble_deck}/*.json", {
  eager: true,
  import: "default",
}) as Record<string, Card>;

const ALL_CARDS: Card[] = Object.values(cardModules);

const CATEGORIES = [
  "economy", "alliance", "betrayal", "disruption", "protection",
  "tempo", "information", "supercard",
];

const METRIC_HELP: Record<string, string> = {
  assisted_win_rate: "How often the winner got gold gifted from a player who was out of contention. Lower is better — high values mean kingmaking is still a problem.",
  shield_hit_rate: "Protection cards that actually blocked an attack vs guessed wrong. Too high = attacks are predictable; too low = shields feel like traps.",
  whiff_penalty_rate: "How often protection cards missed and triggered their penalty. Part of the risk/reward calibration.",
  protection_net_ev: "Average gold swing per protection card (hits minus whiffs). A good protection card should be bimodal: big win or real loss.",
  skill_gap: "How much trained bots beat random bots. Target ~65–85%: lower means luck dominates, higher means no room for variance.",
  exploitability: "How much a best-response strategy beats your current policy. Lower means the policy is harder to exploit at the table.",
};

function collectPrimitives(obj: unknown, found: Set<string> = new Set()): Set<string> {
  if (!obj || typeof obj !== "object") return found;
  const rec = obj as Record<string, unknown>;
  if (typeof rec.primitive === "string") found.add(rec.primitive);
  for (const v of Object.values(rec)) {
    if (typeof v === "object") collectPrimitives(v, found);
  }
  return found;
}

function validateCard(card: Card): string[] {
  const errors: string[] = [];
  if (!card.id) errors.push("missing id");
  if (!card.name) errors.push("missing name");
  for (const prim of collectPrimitives(card.effect)) {
    if (!VALID_PRIMITIVES.has(prim)) errors.push(`unknown primitive: ${prim}`);
  }
  if (card.on_whiff_penalty) {
    for (const prim of collectPrimitives(card.on_whiff_penalty)) {
      if (!VALID_PRIMITIVES.has(prim)) errors.push(`unknown whiff primitive: ${prim}`);
    }
  }
  if (card.category === "protection" && !card.on_whiff_penalty) {
    errors.push("protection card missing on_whiff_penalty");
  }
  return errors;
}

function CardProse({ card }: { card: Card }) {
  const { sections } = describeCardFull(card);
  return (
    <div>
      {sections.map((sec) => (
        <div key={sec.title} className="prose-block">
          <h4>{sec.title}</h4>
          <ul>
            {sec.lines.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function EffectJson({ data, label }: { data: unknown; label: string }) {
  if (!data) return null;
  return (
    <div style={{ marginTop: "0.75rem" }}>
      <strong>{label}</strong>
      <pre className="effect-tree">{JSON.stringify(data, null, 2)}</pre>
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState<"cards" | "balance" | "replay" | "gaps" | "metrics" | "help" | "training">("cards");
  const [search, setSearch] = useState("");
  const [ownerFilter, setOwnerFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [selected, setSelected] = useState<Card | null>(null);
  const [showJson, setShowJson] = useState(false);

  const cardsWithValidation = useMemo(
    () =>
      ALL_CARDS.map((c) => ({ card: c, errors: validateCard(c) })).sort((a, b) =>
        a.card.name.localeCompare(b.card.name)
      ),
    []
  );

  const filtered = cardsWithValidation.filter(({ card }) => {
    if (ownerFilter !== "all" && card.owner_type !== ownerFilter) return false;
    if (categoryFilter !== "all" && card.category !== categoryFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      const summary = describeCardSummary(card);
      const hay = [
        card.name, card.id, card.category, summary,
        ...(card.tags || []), ...(card.synergy_tags || []),
      ].join(" ").toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const cat of CATEGORIES) counts[cat] = 0;
    for (const { card } of cardsWithValidation) {
      counts[card.category] = (counts[card.category] || 0) + 1;
    }
    return counts;
  }, [cardsWithValidation]);

  return (
    <div className="app">
      <header className="header">
        <h1>Crown & Court</h1>
        <p>Card gallery & balance lab — {ALL_CARDS.length} cards loaded</p>
      </header>

      <div className="tabs">
        {([
          ["cards", "Card Gallery"],
          ["balance", "Balance Results"],
          ["replay", "Game Replay"],
          ["training", "Live Training"],
          ["gaps", "Category Gaps"],
          ["metrics", "Analytics Guide"],
          ["help", "Adding Cards"],
        ] as const).map(([t, label]) => (
          <button key={t} className={`tab ${tab === t ? "active" : ""}`} onClick={() => setTab(t)}>
            {label}
          </button>
        ))}
      </div>

      {tab === "cards" && (
        <>
          <div className="filters">
            <input placeholder="Search name, tags, effects…" value={search} onChange={(e) => setSearch(e.target.value)} />
            <select value={ownerFilter} onChange={(e) => setOwnerFilter(e.target.value)}>
              <option value="all">All owners</option>
              <option value="king">King</option>
              <option value="noble">Noble</option>
            </select>
            <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}>
              <option value="all">All categories</option>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          <div className="grid">
            {filtered.map(({ card, errors }) => (
              <div
                key={card.id}
                className={`card-tile ${card.owner_type}`}
                onClick={() => { setSelected(card); setShowJson(false); }}
              >
                <span className={`badge ${errors.length ? "badge-invalid" : "badge-valid"}`}>
                  {errors.length ? "invalid" : "valid"}
                </span>
                <span className={`badge badge-rarity-${card.rarity}`}>{card.rarity}</span>
                <h3>{card.name}</h3>
                <p className="card-tile-summary">{describeCardSummary(card)}</p>
                {card.flavor_text && <p><em>{card.flavor_text}</em></p>}
                <small>{card.category} · {card.timing} · ×{card.copies_in_deck}</small>
              </div>
            ))}
          </div>

          {selected && (
            <div className="detail-panel">
              <h2>{selected.name}</h2>
              <div className="meta-row">
                <span className={`badge badge-rarity-${selected.rarity}`}>{selected.rarity}</span>
                <span>{selected.owner_type === "king" ? "King deck" : "Noble deck"}</span>
                <span>{selected.copies_in_deck} copies in deck</span>
              </div>
              {selected.flavor_text && <p><em>"{selected.flavor_text}"</em></p>}

              <CardProse card={selected} />

              {selected.designer_notes && (
                <div className="prose-block">
                  <h4>Designer notes</h4>
                  <p style={{ margin: 0 }}>{selected.designer_notes}</p>
                </div>
              )}

              {(selected.synergy_tags || []).length > 0 && (
                <p><strong>Combo tags:</strong> {selected.synergy_tags!.join(", ")}</p>
              )}

              <button type="button" className="tech-toggle" onClick={() => setShowJson(!showJson)}>
                {showJson ? "Hide" : "Show"} technical JSON (for designers)
              </button>

              {showJson && (
                <>
                  <EffectJson data={selected.effect} label="Effect (JSON)" />
                  <EffectJson data={selected.requires_state} label="Requires State (JSON)" />
                  <EffectJson data={selected.on_whiff_penalty} label="On Whiff Penalty (JSON)" />
                </>
              )}

              <button className="tab" style={{ marginTop: "1rem" }} onClick={() => setSelected(null)}>Close</button>
            </div>
          )}
        </>
      )}

      {tab === "balance" && <BalanceResults />}

      {tab === "replay" && <ReplayViewer />}

      {tab === "training" && <TrainingLive />}

      {tab === "gaps" && (
        <div className="category-gap">
          {CATEGORIES.map((cat) => (
            <span key={cat} className={`gap-chip ${categoryCounts[cat] >= 2 ? "filled" : "empty"}`}>
              {cat}: {categoryCounts[cat]}/2
            </span>
          ))}
        </div>
      )}

      {tab === "metrics" && (
        <div>
          {Object.entries(METRIC_HELP).map(([key, desc]) => (
            <div key={key} className="metric-block">
              <h4>{key.replace(/_/g, " ")}</h4>
              <p>{desc}</p>
            </div>
          ))}
        </div>
      )}

      {tab === "help" && (
        <div className="detail-panel" style={{ marginTop: 0 }}>
          <h2>How to add cards manually</h2>
          <div className="prose-block">
            <h4>Step 1 — Create a JSON file</h4>
            <ul>
              <li>King cards → <code>cards/king_deck/your_card.json</code></li>
              <li>Noble cards → <code>cards/noble_deck/your_card.json</code></li>
              <li>Copy an existing card and edit it, or use the template below.</li>
            </ul>
          </div>
          <pre className="effect-tree">{`{
  "id": "noble_my_card_001",
  "name": "My Card Name",
  "owner_type": "noble",
  "category": "economy",
  "rarity": "common",
  "copies_in_deck": 3,
  "timing": "on_reveal",
  "effect": {
    "primitive": "gold_gain",
    "params": { "target": "self", "amount": 75 }
  },
  "flavor_text": "Your quote here."
}`}</pre>
          <div className="prose-block">
            <h4>Step 2 — Validate</h4>
            <ul>
              <li><code>python -m engine.validate</code></li>
              <li>Protection cards must include <code>on_whiff_penalty</code>.</li>
            </ul>
          </div>
          <div className="prose-block">
            <h4>Step 3 — View</h4>
            <ul>
              <li>Refresh the gallery (dev server auto-reloads).</li>
              <li>Full guide: <code>docs/ADDING_CARDS.md</code></li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
