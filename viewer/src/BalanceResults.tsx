import { useEffect, useMemo, useState } from "react";

type SeatRow = {
  seat: number;
  label: string;
  win_rate: number;
  wins: number;
  games: number;
  delta_vs_fair: number;
  layman: string;
};

type CardRow = {
  id: string;
  name: string;
  times_played: number;
  games_with_card: number;
  wins_when_played: number;
  win_rate_when_played: number;
  delta_vs_fair: number;
  verdict: string;
  layman: string;
};

type BalancePayload = {
  status: string;
  message?: string;
  card_set_version?: string;
  games_run?: number;
  min_recommended_games?: number;
  methodology?: { bots: string; purpose: string; developer_note: string };
  training_choices_note?: { layman: string; trained_seat: string; opponent_bots: string };
  headlines?: {
    assisted_win_rate: number;
    assisted_status: string;
    assisted_layman: string;
    shield_hit_rate: number;
    shield_layman: string;
    started_as_king_win_rate: number;
    started_as_noble_win_rate: number;
    role_layman: string;
  };
  seat_chart?: SeatRow[];
  card_contributions?: CardRow[];
  kingmaker?: { fix_works: boolean; gold_only_ascension: number; earned_gold_ascension: number; layman: string };
  tune?: { passes: number; changes_count: number; recommendations: string[] };
  signoff_comparison?: {
    recommendation: string;
    reason: string;
    standard_tuned_run: { metrics: { assisted_win_rate: number }; score: { gates_passed: number } };
    prd_sample_run: { metrics: { assisted_win_rate: number }; score: { gates_passed: number } };
  };
};

function pct(n: number) {
  return `${(n * 100).toFixed(1)}%`;
}

function verdictClass(v: string) {
  if (v === "overperformer") return "verdict-over";
  if (v === "underperformer") return "verdict-under";
  if (v === "too_few_games") return "verdict-low-n";
  return "verdict-ok";
}

function statusClass(s: string) {
  if (s === "good") return "badge-valid";
  if (s === "watch") return "badge-rarity-rare";
  return "badge-invalid";
}

export default function BalanceResults() {
  const [data, setData] = useState<BalancePayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showDev, setShowDev] = useState(false);
  const [cardFilter, setCardFilter] = useState("");
  const [sortBy, setSortBy] = useState<"delta" | "plays" | "name">("delta");

  useEffect(() => {
    fetch(`/balance/summary.json?t=${Date.now()}`)
      .then((r) => (r.ok ? r.json() : Promise.reject("missing")))
      .then((d: BalancePayload) => {
        setData(d);
        setError(null);
      })
      .catch(() => {
        setData(null);
        setError("No balance data exported yet.");
      });
  }, []);

  const cards = useMemo(() => {
    const list = data?.card_contributions ?? [];
    const q = cardFilter.toLowerCase();
    const filtered = q
      ? list.filter((c) => c.name.toLowerCase().includes(q) || c.id.toLowerCase().includes(q))
      : list;
    return [...filtered].sort((a, b) => {
      if (sortBy === "plays") return b.times_played - a.times_played;
      if (sortBy === "name") return a.name.localeCompare(b.name);
      return b.delta_vs_fair - a.delta_vs_fair;
    });
  }, [data, cardFilter, sortBy]);

  if (!data || data.status === "idle") {
    return (
      <div className="detail-panel" style={{ marginTop: 0 }}>
        <h2>Balance Results</h2>
        <p>{error || data?.message}</p>
        <div className="prose-block">
          <h4>How to generate results</h4>
          <pre className="effect-tree">{`cd crown-and-court
.venv\\Scripts\\activate
python -m analytics.auto_tune --games 80
python -m analytics.export_viewer_balance`}</pre>
          <p>Then refresh this tab. Results are written to <code>viewer/public/balance/summary.json</code>.</p>
        </div>
      </div>
    );
  }

  const h = data.headlines!;
  const maxSeatRate = Math.max(...(data.seat_chart ?? []).map((s) => s.win_rate), 0.01);

  return (
    <div className="detail-panel balance-panel" style={{ marginTop: 0 }}>
      <div className="balance-header">
        <div>
          <h2>Balance Results</h2>
          <p className="balance-meta">
            {data.games_run} simulated games · card set <code>{data.card_set_version}</code>
            {data.min_recommended_games && data.games_run! < data.min_recommended_games && (
              <span className="sample-warn"> · below recommended {data.min_recommended_games} games</span>
            )}
          </p>
        </div>
        <button type="button" className="tech-toggle" onClick={() => setShowDev(!showDev)}>
          {showDev ? "Hide" : "Show"} developer details
        </button>
      </div>

      <div className="metrics-grid">
        <div className="metric-block">
          <h4>Gifted wins (kingmaking signal)</h4>
          <p className="metric-value">{pct(h.assisted_win_rate)}</p>
          <span className={`badge ${statusClass(h.assisted_status)}`}>{h.assisted_status}</span>
          <p className="metric-help">{h.assisted_layman}</p>
        </div>
        <div className="metric-block">
          <h4>Starting King wins</h4>
          <p className="metric-value">{pct(h.started_as_king_win_rate)}</p>
          <p className="metric-help">{h.role_layman}</p>
        </div>
        <div className="metric-block">
          <h4>Protection cards that hit</h4>
          <p className="metric-value">{pct(h.shield_hit_rate)}</p>
          <p className="metric-help">{h.shield_layman}</p>
        </div>
      </div>

      {data.signoff_comparison && (
        <div className="prose-block">
          <h4>Sign-off comparison (100 tuned vs 385 PRD)</h4>
          <p>
            Recommendation: <strong>{data.signoff_comparison.recommendation}</strong> — {data.signoff_comparison.reason}
          </p>
          <ul>
            <li>100-game tuned: assisted {(data.signoff_comparison.standard_tuned_run.metrics.assisted_win_rate * 100).toFixed(1)}%, gates {data.signoff_comparison.standard_tuned_run.score.gates_passed}/4</li>
            <li>385-game PRD: assisted {(data.signoff_comparison.prd_sample_run.metrics.assisted_win_rate * 100).toFixed(1)}%, gates {data.signoff_comparison.prd_sample_run.score.gates_passed}/4</li>
          </ul>
        </div>
      )}

      {data.kingmaker && (
        <div className="prose-block">
          <h4>Kingmaker test</h4>
          <p>{data.kingmaker.layman}</p>
          <p>
            <span className={`badge ${data.kingmaker.fix_works ? "badge-valid" : "badge-invalid"}`}>
              {data.kingmaker.fix_works ? "Earned-gold fix works" : "Fix not verified"}
            </span>
          </p>
        </div>
      )}

      <h3>Win rate by seat</h3>
      <p className="section-intro">
        Each bar shows how often the player in that chair at game start ended as King. Uneven bars may mean seating advantage — not a specific bot winning.
      </p>
      <div className="bar-chart">
        {(data.seat_chart ?? []).map((row) => (
          <div key={row.seat} className="bar-row" title={row.layman}>
            <span className="bar-label">{row.label}</span>
            <div className="bar-track">
              <div
                className="bar-fill seat-bar"
                style={{ width: `${(row.win_rate / maxSeatRate) * 100}%` }}
              />
            </div>
            <span className="bar-value">{pct(row.win_rate)} ({row.wins}/{row.games})</span>
          </div>
        ))}
      </div>

      <h3>Card win contribution</h3>
      <p className="section-intro">
        When a card was played, how often did that player go on to win? Positive delta vs fair share suggests the card may be overtuned.
      </p>
      <div className="filters">
        <input
          placeholder="Filter cards…"
          value={cardFilter}
          onChange={(e) => setCardFilter(e.target.value)}
        />
        <select value={sortBy} onChange={(e) => setSortBy(e.target.value as typeof sortBy)}>
          <option value="delta">Sort by impact (delta)</option>
          <option value="plays">Sort by times played</option>
          <option value="name">Sort by name</option>
        </select>
      </div>
      <div className="card-contrib-list">
        {cards.length === 0 && (
          <p className="section-intro">
            No card win data yet. Run <code>make sweep</code> or <code>make balance</code> after updating metrics, then refresh.
          </p>
        )}
        {cards.map((c) => (
          <details key={c.id} className="contrib-row">
            <summary>
              <span className="contrib-name">{c.name}</span>
              <span className={`badge ${verdictClass(c.verdict)}`}>{c.verdict.replace(/_/g, " ")}</span>
              <span className="contrib-stat">{pct(c.win_rate_when_played)} win when played</span>
              <span className={`contrib-delta ${c.delta_vs_fair >= 0 ? "pos" : "neg"}`}>
                {c.delta_vs_fair >= 0 ? "+" : ""}{pct(c.delta_vs_fair)} vs fair
              </span>
            </summary>
            <p className="contrib-layman">{c.layman}</p>
            {showDev && (
              <pre className="effect-tree">{JSON.stringify(c, null, 2)}</pre>
            )}
          </details>
        ))}
      </div>

      <div className="prose-block">
        <h4>Dice &amp; card choices in sweeps vs training</h4>
        <p>{data.training_choices_note?.layman}</p>
        {showDev && data.training_choices_note && (
          <ul>
            <li><strong>Trained seat:</strong> {data.training_choices_note.trained_seat}</li>
            <li><strong>Opponents:</strong> {data.training_choices_note.opponent_bots}</li>
            <li><strong>Sweep bots:</strong> {data.methodology?.bots}</li>
          </ul>
        )}
      </div>

      {data.tune && data.tune.changes_count > 0 && (
        <div className="prose-block">
          <h4>Auto-tune applied</h4>
          <p>{data.tune.passes} pass(es), {data.tune.changes_count} numeric tweaks to card gold/whiff values.</p>
        </div>
      )}
    </div>
  );
}
