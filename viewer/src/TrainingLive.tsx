import { useEffect, useState } from "react";

type HistoryRow = {
  episode: number;
  won: boolean;
  opponent?: string;
  loss?: number;
};

type BenchmarkPoint = {
  episode: number;
  skill_gap?: number;
  league_wr?: number;
  exploitability_gap?: number;
  skill_gap_vs_random?: number;
};

type LivePayload = {
  status: string;
  episode: number;
  total_episodes: number;
  progress_pct: number;
  message: string;
  metrics: Record<string, number | string>;
  history: HistoryRow[];
  benchmark_history?: BenchmarkPoint[];
  series?: {
    loss_ma20?: [number, number][];
    win_rate_ma20?: [number, number][];
  };
};

function pct(v: number | undefined | null) {
  if (v == null || Number.isNaN(v)) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function num(v: number | undefined | null, digits = 4) {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toFixed(digits);
}

function LineChart({
  series,
  lines,
  height = 120,
}: {
  series: { key: string; data: [number, number][]; color: string; label: string }[];
  lines?: { y: number; label: string; dash?: boolean }[];
  height?: number;
}) {
  const allX = series.flatMap((s) => s.data.map((d) => d[0]));
  const allY = series.flatMap((s) => s.data.map((d) => d[1]));
  if (!allX.length) {
    return <p className="metric-help">Waiting for data…</p>;
  }
  const minX = Math.min(...allX);
  const maxX = Math.max(...allX, 1);
  const minY = Math.min(...allY, ...(lines?.map((l) => l.y) ?? []));
  const maxY = Math.max(...allY, ...(lines?.map((l) => l.y) ?? []), 0.01);
  const pad = 4;
  const w = 600;
  const h = height;
  const sx = (x: number) => pad + ((x - minX) / (maxX - minX || 1)) * (w - 2 * pad);
  const sy = (y: number) => h - pad - ((y - minY) / (maxY - minY || 1)) * (h - 2 * pad);

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="line-chart" role="img">
      {lines?.map((l) => (
        <line
          key={l.label}
          x1={pad}
          y1={sy(l.y)}
          x2={w - pad}
          y2={sy(l.y)}
          stroke="var(--gold-dim)"
          strokeDasharray={l.dash ? "4 4" : undefined}
          strokeWidth={1}
        />
      ))}
      {series.map((s) => {
        if (s.data.length < 2) return null;
        const pts = s.data.map(([x, y]) => `${sx(x)},${sy(y)}`).join(" ");
        return (
          <polyline
            key={s.key}
            fill="none"
            stroke={s.color}
            strokeWidth={2}
            points={pts}
          />
        );
      })}
      <text x={pad} y={12} fill="var(--parchment-dark)" fontSize="10">
        {series.map((s) => s.label).join(" · ")}
      </text>
    </svg>
  );
}

export default function TrainingLive() {
  const [data, setData] = useState<LivePayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = () => {
      fetch(`/training/live.json?t=${Date.now()}`)
        .then((r) => (r.ok ? r.json() : Promise.reject("No training run active")))
        .then((d) => { setData(d); setError(null); })
        .catch(() => {
          setData(null);
          setError("No active training run — start trainer (see below).");
        });
    };
    load();
    const id = setInterval(load, 2000);
    return () => clearInterval(id);
  }, []);

  if (!data || data.status === "idle") {
    return (
      <div className="detail-panel" style={{ marginTop: 0 }}>
        <h2>Live Training Dashboard</h2>
        <p>{error}</p>
        <div className="prose-block">
          <h4>How to watch live results</h4>
          <ol>
            <li>Open this gallery: <code>cd viewer && npm run dev</code></li>
            <li>In another terminal, start training:</li>
          </ol>
          <pre className="effect-tree">{`cd crown-and-court
.venv\\Scripts\\activate
python -m training.trainer --episodes 200`}</pre>
          <p>This tab refreshes every 2 seconds automatically.</p>
        </div>
      </div>
    );
  }

  const m = data.metrics;
  const resumedFrom = m.resumed_from_episode as number | undefined;
  const bench = data.benchmark_history ?? [];
  const skillSeries: [number, number][] = bench
    .filter((b) => b.skill_gap != null)
    .map((b) => [b.episode, b.skill_gap as number]);
  const exploitSeries: [number, number][] = bench
    .filter((b) => b.exploitability_gap != null)
    .map((b) => [b.episode, b.exploitability_gap as number]);
  const lossSeries = data.series?.loss_ma20 ?? [];
  const seatRows = [0, 1, 2, 3, 4, 5].map((seat) => ({
    seat,
    rate: m[`seat_${seat}_win_rate_ma20`] as number | undefined,
  }));
  const seatRates = seatRows.map((r) => r.rate ?? 0);
  const maxSeat = Math.max(...seatRates, 0.01);

  return (
    <div className="detail-panel" style={{ marginTop: 0 }}>
      <h2>Live Training</h2>
      {resumedFrom != null && resumedFrom > 0 && (
        <p className="section-intro">
          Resumed from episode {resumedFrom}. Rolling metrics use the last 200 episodes from disk;
          benchmark charts fill in at the next checkpoint.
        </p>
      )}
      <p>
        <span className={`badge ${data.status === "running" ? "badge-valid" : "badge-rarity-rare"}`}>
          {data.status}
        </span>
        {" "}{data.message}
      </p>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${data.progress_pct}%` }} />
      </div>
      <p>{data.episode} / {data.total_episodes} episodes ({data.progress_pct}%)</p>

      <div className="metrics-grid">
        <div className="metric-block">
          <h4>Win rate (last 20)</h4>
          <p className="metric-value">{pct(m.train_win_rate_ma20 as number)}</p>
          <p className="metric-help">How often the training seat ends the game as King.</p>
        </div>
        <div className="metric-block">
          <h4>Win rate (last 50)</h4>
          <p className="metric-value">{pct(m.train_win_rate_ma50 as number)}</p>
          <p className="metric-help">Smoother trend vs mixed opponents.</p>
        </div>
        <div className="metric-block">
          <h4>Skill gap</h4>
          <p className="metric-value">{pct(m.skill_gap as number)}</p>
          <p className="metric-help">League WR minus fair 1/n share — higher is better.</p>
        </div>
        <div className="metric-block">
          <h4>Assisted wins (MA20)</h4>
          <p className="metric-value">{pct(m.assisted_win_rate_ma20 as number)}</p>
          <p className="metric-help">Kingmaker gifting rate — lower is better.</p>
        </div>
        <div className="metric-block">
          <h4>Device</h4>
          <p className="metric-value">{String(m.device || "cpu")}</p>
          <p className="metric-help">PPO updates run here; rollouts use CPU workers.</p>
        </div>
        <div className="metric-block">
          <h4>Exploitability gap</h4>
          <p className="metric-value">{pct(m.exploitability_gap as number)}</p>
          <p className="metric-help">League WR minus all-exploit WR.</p>
        </div>
      </div>

      <h3>Skill gap over time</h3>
      <p className="section-intro">
        Measured at benchmark checkpoints. Dashed line is fair share (0% above par).
      </p>
      <LineChart
        series={[
          { key: "skill", data: skillSeries, color: "var(--gold)", label: "Skill gap" },
          { key: "exploit", data: exploitSeries, color: "#7eb8da", label: "Exploit gap" },
        ]}
        lines={[{ y: 0, label: "fair", dash: true }]}
      />

      <h3>Loss curve (MA20)</h3>
      <p className="section-intro">Combined policy + value loss, smoothed over 20 episodes.</p>
      <LineChart
        series={[{ key: "loss", data: lossSeries, color: "#c97b84", label: "Loss MA20" }]}
        height={100}
      />

      <h3>Win rate by training seat</h3>
      <p className="section-intro">
        When training rotates seats, how often each seat wins (MA20). Uneven bars may mean seat difficulty, not a bug.
      </p>
      <div className="bar-chart">
        {seatRows.map((row) => (
          <div key={row.seat} className="bar-row">
            <span className="bar-label">Seat {row.seat}</span>
            <div className="bar-track">
              <div
                className="bar-fill seat-bar"
                style={{ width: `${((row.rate ?? 0) / maxSeat) * 100}%` }}
              />
            </div>
            <span className="bar-value">{pct(row.rate)}</span>
          </div>
        ))}
      </div>

      <h3>Recent episodes</h3>
      <table className="history-table">
        <thead>
          <tr><th>#</th><th>Seat</th><th>Result</th><th>Loss</th></tr>
        </thead>
        <tbody>
          {[...(data.history || [])].reverse().slice(0, 15).map((h) => (
            <tr key={h.episode}>
              <td>{h.episode}</td>
              <td>{(h as HistoryRow & { train_seat?: number }).train_seat ?? "—"}</td>
              <td>{h.won ? "Win" : "Loss"}</td>
              <td>{h.loss != null ? h.loss.toFixed(4) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
