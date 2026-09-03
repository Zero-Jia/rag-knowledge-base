import { useCallback, useEffect, useState } from "react";
import {
  getMetricsSummary,
  getMetricsTimeseries,
  getRecentMetrics,
  getReactComparison,
} from "../api/metrics";

const RANGE_OPTIONS = [
  { label: "1 day", days: 1 },
  { label: "7 days", days: 7 },
  { label: "30 days", days: 30 },
];

function isoDaysAgo(days) {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() - (days - 1));
  return d.toISOString();
}

function nowIso() {
  return new Date().toISOString();
}

function formatPct(rate) {
  if (rate === null || rate === undefined) return "—";
  return `${(rate * 100).toFixed(1)}%`;
}

function formatNum(value, digits = 1) {
  if (value === null || value === undefined) return "—";
  return Number(value).toFixed(digits);
}

function formatTime(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString();
}

export default function Metrics() {
  const [range, setRange] = useState(7);
  const [summary, setSummary] = useState(null);
  const [timeseries, setTimeseries] = useState([]);
  const [recent, setRecent] = useState([]);
  const [reactCmp, setReactCmp] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError("");
    const params = { start: isoDaysAgo(range), end: nowIso() };
    try {
      const [s, t, rc] = await Promise.all([
        getMetricsSummary(params),
        getMetricsTimeseries(params),
        getReactComparison(params),
      ]);
      const r = await getRecentMetrics({ limit: 20 });
      setSummary(s);
      setTimeseries(t);
      setReactCmp(rc);
      setRecent(r);
    } catch (e) {
      setError(e.message || "Failed to load metrics");
    } finally {
      setLoading(false);
    }
  }, [range]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  return (
    <div className="metrics-page">
      <div className="metrics-toolbar">
        <div className="range-group">
          {RANGE_OPTIONS.map((opt) => (
            <button
              key={opt.days}
              type="button"
              className={`range-btn ${range === opt.days ? "active" : ""}`}
              onClick={() => setRange(opt.days)}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <button
          type="button"
          className="refresh-btn"
          onClick={loadAll}
          disabled={loading}
        >
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      {error && <div className="alert error">{error}</div>}

      <SummaryCards summary={summary} />

      <ReactComparisonCard reactCmp={reactCmp} />

      <TimeseriesChart rows={timeseries} />

      <RecentTable rows={recent} />
    </div>
  );
}

function SummaryCards({ summary }) {
  if (!summary) {
    return <div className="metrics-empty">Loading summary…</div>;
  }
  const cards = [
    { label: "Total requests", value: summary.total_requests ?? 0 },
    { label: "Fallback rate", value: formatPct(summary.fallback_rate) },
    { label: "ReAct triggered", value: formatPct(summary.react_triggered_rate) },
    {
      label: "ReAct rescue rate",
      value: formatPct(summary.react_rescue_rate),
      hint: summary.react_triggered_count
        ? `${summary.react_success_count}/${summary.react_triggered_count}`
        : "0 triggers",
    },
    { label: "Avg latency (ms)", value: formatNum(summary.avg_latency_ms, 0) },
    { label: "P95 latency (ms)", value: formatNum(summary.p95_latency_ms, 0) },
    { label: "Avg tokens", value: formatNum(summary.avg_token_total, 0) },
    {
      label: "Total tokens",
      value: summary.total_token_consumed ?? 0,
    },
    {
      label: "Grounding pass rate",
      value: formatPct(summary.grounding_pass_rate),
    },
    { label: "Cache hit rate", value: formatPct(summary.cache_hit_rate) },
    {
      label: "Auto-merge rate",
      value: formatPct(summary.auto_merge_rate),
      hint: `${summary.auto_merge_requests ?? 0} reqs / ${summary.auto_merge_parent_chunks ?? 0} parents`,
    },
  ];
  return (
    <div className="summary-grid">
      {cards.map((c) => (
        <div key={c.label} className="summary-card">
          <span className="summary-label">{c.label}</span>
          <strong className="summary-value">{c.value}</strong>
          {c.hint && <span className="summary-hint">{c.hint}</span>}
        </div>
      ))}
    </div>
  );
}

function ReactComparisonCard({ reactCmp }) {
  if (!reactCmp) {
    return <div className="metrics-empty">Loading ReAct comparison…</div>;
  }
  const { quick_path: quick, react, delta_latency_ms, delta_token_total } =
    reactCmp;
  const metrics = [
    { label: "Count", q: quick?.count ?? 0, r: react?.count ?? 0 },
    {
      label: "Fallback rate",
      q: formatPct(quick?.fallback_rate),
      r: formatPct(react?.fallback_rate),
    },
    {
      label: "Avg latency (ms)",
      q: formatNum(quick?.avg_latency_ms, 0),
      r: formatNum(react?.avg_latency_ms, 0),
    },
    {
      label: "Avg tokens",
      q: formatNum(quick?.avg_token_total, 0),
      r: formatNum(react?.avg_token_total, 0),
    },
    {
      label: "Grounding pass",
      q: formatPct(quick?.grounding_pass_rate),
      r: formatPct(react?.grounding_pass_rate),
    },
    {
      label: "Avg tool rounds",
      q: "—",
      r: formatNum(react?.avg_tool_rounds, 2),
    },
    {
      label: "Avg evidence count",
      q: "—",
      r: formatNum(react?.avg_evidence_count, 1),
    },
    {
      label: "Rescue rate",
      q: "—",
      r: formatPct(react?.rescue_rate),
    },
  ];
  return (
    <div className="react-cmp-card">
      <div className="card-title">
        ReAct vs Quick Path
        <span className="delta-line">
          Δ latency: {formatNum(delta_latency_ms, 0)} ms / Δ tokens:{" "}
          {formatNum(delta_token_total, 0)}
        </span>
      </div>
      <table className="cmp-table">
        <thead>
          <tr>
            <th>Metric</th>
            <th>Quick path</th>
            <th>ReAct</th>
          </tr>
        </thead>
        <tbody>
          {metrics.map((m) => (
            <tr key={m.label}>
              <td>{m.label}</td>
              <td>{m.q}</td>
              <td>{m.r}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TimeseriesChart({ rows }) {
  if (!rows || rows.length === 0) {
    return (
      <div className="metrics-empty">No timeseries data in this range.</div>
    );
  }
  const maxCount = Math.max(
    1,
    ...rows.map((r) => r.request_count || 0)
  );
  return (
    <div className="timeseries-card">
      <div className="card-title">Daily Volume</div>
      <div className="ts-chart">
        {rows.map((r) => {
          const h = ((r.request_count || 0) / maxCount) * 100;
          const fbH =
            r.request_count > 0
              ? ((r.fallback_count || 0) / r.request_count) * 100
              : 0;
          const reactH =
            r.request_count > 0
              ? ((r.react_triggered_count || 0) / r.request_count) * 100
              : 0;
          return (
            <div key={r.date} className="ts-col" title={`${r.date} | req=${r.request_count} fb=${r.fallback_count} react=${r.react_triggered_count}`}>
              <div className="ts-bar-wrap">
                <div className="ts-bar ts-bar-react" style={{ height: `${reactH}%` }} />
                <div className="ts-bar ts-bar-fb" style={{ height: `${fbH}%` }} />
                <div className="ts-bar ts-bar-total" style={{ height: `${h}%` }} />
              </div>
              <span className="ts-label">{r.request_count}</span>
              <span className="ts-date">{r.date.slice(5)}</span>
            </div>
          );
        })}
      </div>
      <div className="ts-legend">
        <span><i className="dot dot-total" /> Requests</span>
        <span><i className="dot dot-fb" /> Fallback</span>
        <span><i className="dot dot-react" /> ReAct triggered</span>
      </div>
    </div>
  );
}

function RecentTable({ rows }) {
  if (!rows || rows.length === 0) {
    return <div className="metrics-empty">No recent rows.</div>;
  }
  return (
    <div className="recent-card">
      <div className="card-title">Recent rows (latest 20)</div>
      <div className="recent-table-wrap">
        <table className="recent-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Route</th>
              <th>Cache</th>
              <th>Grade</th>
              <th>Grounding</th>
              <th>Fallback</th>
              <th>ReAct</th>
              <th>Latency(ms)</th>
              <th>Tokens</th>
              <th>Session</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{formatTime(r.created_at)}</td>
                <td>{r.route || "—"}</td>
                <td>{r.cache_hit ? "hit" : "miss"}</td>
                <td>{r.evidence_grade || "—"}</td>
                <td>{r.grounding_passed === null ? "—" : r.grounding_passed ? "pass" : "fail"}</td>
                <td>
                  {r.need_fallback ? (
                    <span className="tag tag-warn">{r.fallback_reason || "yes"}</span>
                  ) : (
                    "no"
                  )}
                </td>
                <td>
                  {r.react_attempted ? (
                    <span className="tag tag-react">
                      {r.react_status || "on"}
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
                <td>{formatNum(r.total_latency_ms, 0)}</td>
                <td>{r.token_total ?? "—"}</td>
                <td className="session-cell" title={r.session_id || ""}>
                  {r.session_id ? r.session_id.slice(0, 16) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
