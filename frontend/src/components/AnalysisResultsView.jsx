import { useEffect, useState } from "react";
import { regenerateReport } from "../api";

const TABS = [
  { id: "report", label: "Report & Answer" },
  { id: "data", label: "Data & EDA" },
  { id: "models", label: "Models & SHAP" },
  { id: "quality", label: "Critic & Security" },
  { id: "research", label: "Research" },
  { id: "audit", label: "Raw Audit" },
];

function safeExternalUrl(rawUrl) {
  if (typeof rawUrl !== "string" || !rawUrl.trim()) return null;
  try {
    const parsed = new URL(rawUrl.trim(), window.location.origin);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.href : null;
  } catch {
    return null;
  }
}

function fmtNum(value, decimals = 4) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  const num = Number(value);
  return Number.isInteger(num) ? num.toLocaleString() : num.toFixed(decimals);
}

function ReportChart({ chart }) {
  const rows = chart?.data || [];
  if (!rows.length) return null;
  const max = Math.max(1, ...rows.map((row) => Number(row.value) || 0));
  const palette = ["#3f7d58", "#9a6c56", "#c6a34f", "#486b7a", "#7f8f63", "#8b7265"];

  if (chart.type === "pie" || chart.type === "donut") {
    let cursor = 0;
    const total = rows.reduce((sum, row) => sum + (Number(row.value) || 0), 0) || 1;
    const segments = rows.map((row, index) => {
      const start = cursor;
      cursor += ((Number(row.value) || 0) / total) * 100;
      return `${palette[index % palette.length]} ${start}% ${cursor}%`;
    });
    return (
      <section className="panel">
        <div className="panel-head"><h3>{chart.title}</h3></div>
        <div style={{ display: "grid", gridTemplateColumns: "minmax(150px, 210px) 1fr", gap: 24, alignItems: "center" }}>
          <div
            style={{
              width: "min(100%, 185px)",
              aspectRatio: "1",
              borderRadius: "50%",
              margin: "auto",
              background: `conic-gradient(${segments.join(", ")})`,
              position: "relative",
            }}
          >
            {chart.type === "donut" && (
              <div
                style={{
                  position: "absolute",
                  inset: "28%",
                  borderRadius: "50%",
                  background: "var(--dp-surface)",
                  display: "grid",
                  placeItems: "center",
                  fontSize: 13,
                  fontWeight: 600,
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {total.toLocaleString()}
              </div>
            )}
          </div>
          <div style={{ display: "grid", gap: 10 }}>
            {rows.map((row, index) => (
              <div
                key={row.label}
                style={{ display: "grid", gridTemplateColumns: "12px 1fr auto", gap: 10, alignItems: "center", fontSize: 13 }}
              >
                <span style={{ width: 10, height: 10, borderRadius: 3, background: palette[index % palette.length] }} />
                <span>{row.label}</span>
                <strong style={{ fontVariantNumeric: "tabular-nums" }}>
                  {(Number(row.value) || 0).toLocaleString()}
                  {row.percentage != null ? ` · ${Number(row.percentage).toFixed(2)}%` : ""}
                </strong>
              </div>
            ))}
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="panel-head"><h3>{chart.title}</h3></div>
      <div style={{ display: "grid", gap: 10 }}>
        {rows.map((row, index) => (
          <div
            key={row.label}
            style={{ display: "grid", gridTemplateColumns: "minmax(100px, 190px) 1fr auto", gap: 12, alignItems: "center" }}
          >
            <span title={row.label} style={{ fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {row.label}
            </span>
            <div style={{ height: 12, background: "var(--dp-subtle)", borderRadius: 999, overflow: "hidden" }}>
              <div
                style={{
                  width: `${Math.max(2, ((Number(row.value) || 0) / max) * 100)}%`,
                  height: "100%",
                  background: palette[index % palette.length],
                  borderRadius: 999,
                }}
              />
            </div>
            <span style={{ minWidth: 96, textAlign: "right", fontSize: 13, color: "var(--dp-text-secondary)", fontVariantNumeric: "tabular-nums" }}>
              {(Number(row.value) || 0).toLocaleString()}
              {row.percentage != null ? ` · ${Number(row.percentage).toFixed(1)}%` : ""}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

function MarkdownReport({ markdown }) {
  if (!markdown) return null;
  const inline = (value) =>
    value.split(/(\*\*.*?\*\*|`[^`]+`)/g).map((part, index) => {
      if (part.startsWith("**") && part.endsWith("**")) return <strong key={index}>{part.slice(2, -2)}</strong>;
      if (part.startsWith("`") && part.endsWith("`")) {
        return (
          <code key={index} style={{ background: "var(--dp-subtle)", padding: "1px 5px", borderRadius: 4, fontSize: 12 }}>
            {part.slice(1, -1)}
          </code>
        );
      }
      return part;
    });

  return (
    <div className="panel" style={{ lineHeight: 1.65, fontSize: 14 }}>
      {markdown.split("\n").map((line, index) => {
        if (line.startsWith("# ")) {
          return (
            <h2 key={index} style={{ fontSize: 20, margin: "2px 0 12px" }}>
              {inline(line.slice(2))}
            </h2>
          );
        }
        if (line.startsWith("## ")) {
          return (
            <h3 key={index} style={{ fontSize: 16, margin: "18px 0 8px", paddingTop: 10, borderTop: "1px solid var(--dp-subtle)" }}>
              {inline(line.slice(3))}
            </h3>
          );
        }
        if (line.startsWith("### ")) {
          return (
            <h4 key={index} style={{ fontSize: 14, fontWeight: 600, margin: "12px 0 6px" }}>
              {inline(line.slice(4))}
            </h4>
          );
        }
        if (line.startsWith("- ")) {
          return (
            <div key={index} style={{ paddingLeft: 16, position: "relative", margin: "4px 0", color: "var(--dp-text-secondary)" }}>
              <span style={{ position: "absolute", left: 0, color: "#3f7d58" }}>•</span>
              {inline(line.slice(2))}
            </div>
          );
        }
        if (!line.trim()) return <div key={index} style={{ height: 6 }} />;
        return (
          <p key={index} style={{ margin: "4px 0", color: "var(--dp-text-secondary)" }}>
            {inline(line)}
          </p>
        );
      })}
    </div>
  );
}

function DescriptiveStatsTable({ descriptive }) {
  const entries = Object.entries(descriptive || {});
  if (!entries.length) return null;
  const cols = [
    ["count", "Count"],
    ["mean", "Mean"],
    ["std", "Std"],
    ["min", "Min"],
    ["25%", "25%"],
    ["50%", "Median"],
    ["75%", "75%"],
    ["max", "Max"],
    ["skewness", "Skew"],
  ];

  return (
    <section className="panel">
      <div className="panel-head"><h3>Descriptive statistics</h3></div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Feature</th>
              {cols.map(([key, label]) => (
                <th key={key} className="num">{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {entries.map(([feature, stats]) => (
              <tr key={feature}>
                <td><b>{feature}</b></td>
                {cols.map(([key]) => (
                  <td key={key} className="num">
                    {key === "count" ? fmtNum(stats?.[key], 0) : fmtNum(stats?.[key], 3)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function CorrelationMatrix({ correlation }) {
  const features = Object.keys(correlation || {});
  if (!features.length) return null;
  const shown = features.slice(0, 12);

  function cellBg(val) {
    if (val === null || val === undefined || Number.isNaN(Number(val))) return "transparent";
    const num = Number(val);
    const alpha = Math.min(0.32, Math.abs(num) * 0.32).toFixed(3);
    return num >= 0 ? `rgba(45, 106, 79, ${alpha})` : `rgba(176, 67, 52, ${alpha})`;
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h3>Pearson correlation matrix</h3>
        {features.length > shown.length && <span className="muted">Showing top {shown.length} of {features.length} numeric features</span>}
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Feature</th>
              {shown.map((col) => (
                <th key={col} className="num" title={col}>{col.length > 14 ? `${col.slice(0, 13)}…` : col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((rowKey) => (
              <tr key={rowKey}>
                <td><b>{rowKey}</b></td>
                {shown.map((colKey) => {
                  const val = correlation?.[rowKey]?.[colKey];
                  return (
                    <td key={colKey} className="num" style={{ background: cellBg(val) }}>
                      {val == null ? "—" : Number(val).toFixed(2)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function InferentialTestsSection({ tests = [], notes = [] }) {
  if (!tests.length && !notes.length) return null;
  return (
    <section className="panel">
      <div className="panel-head">
        <h3>Inferential statistical tests</h3>
        <span className="muted">Associational evidence only — does not establish causality</span>
      </div>
      {tests.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Test</th>
                <th>Feature</th>
                <th className="num">Statistic</th>
                <th className="num">p-value</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {tests.map((item, idx) => {
                const pVal = Number(item.p_value);
                const sig = Number.isFinite(pVal) && pVal < 0.05;
                return (
                  <tr key={`${item.test}-${item.feature}-${idx}`}>
                    <td><b style={{ textTransform: "capitalize" }}>{String(item.test || "").replace(/_/g, " ")}</b></td>
                    <td>{item.feature || "—"}</td>
                    <td className="num">{fmtNum(item.statistic, 3)}</td>
                    <td className="num">
                      <span className={`status-pill ${sig ? "success" : ""}`}>
                        {Number.isFinite(pVal) ? (pVal < 0.0001 ? "< 0.0001" : pVal.toFixed(4)) : "—"}
                      </span>
                    </td>
                    <td>
                      <div>{item.interpretation || "—"}</div>
                      {(item.assumption_note || item.caution) && (
                        <small className="muted">{item.assumption_note || item.caution}</small>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {notes.length > 0 && (
        <ul className="studio-list" style={{ marginTop: 14 }}>
          {notes.map((n, i) => <li key={i}>{n}</li>)}
        </ul>
      )}
    </section>
  );
}

function HistogramCard({ title, histogram }) {
  if (!histogram?.counts?.length) return null;
  const max = Math.max(1, ...histogram.counts);
  return (
    <div style={{ padding: 14, border: "1px solid var(--dp-border)", borderRadius: 8, background: "var(--dp-canvas)" }}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>{title}</div>
      <div style={{ display: "flex", alignItems: "end", gap: 4, height: 90 }}>
        {histogram.counts.map((count, i) => (
          <div
            key={i}
            title={`${fmtNum(histogram.bin_edges[i], 2)} – ${fmtNum(histogram.bin_edges[i + 1], 2)}: ${count}`}
            style={{
              flex: 1,
              minWidth: 4,
              height: `${Math.max(3, (count / max) * 82)}px`,
              background: "#3f7d58",
              borderRadius: "3px 3px 0 0",
            }}
          />
        ))}
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--dp-text-muted)", marginTop: 6, fontVariantNumeric: "tabular-nums" }}>
        <span>{fmtNum(histogram.bin_edges[0], 2)}</span>
        <span>{fmtNum(histogram.bin_edges[histogram.bin_edges.length - 1], 2)}</span>
      </div>
    </div>
  );
}

function ContributionBars({ values }) {
  const entries = Object.entries(values || {})
    .filter(([, value]) => typeof value === "number")
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .slice(0, 15);
  if (!entries.length) return null;
  const max = Math.max(0.000001, ...entries.map(([, value]) => Math.abs(value)));
  return (
    <div style={{ display: "grid", gap: 10, marginTop: 10 }}>
      {entries.map(([feature, value]) => (
        <div key={feature} style={{ display: "grid", gridTemplateColumns: "minmax(120px, 220px) 1fr 88px", gap: 12, alignItems: "center" }}>
          <span title={feature} style={{ fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {feature}
          </span>
          <div style={{ height: 11, background: "var(--dp-subtle)", borderRadius: 999, overflow: "hidden" }}>
            <div style={{ width: `${Math.max(2, (Math.abs(value) / max) * 100)}%`, height: "100%", background: "#3f7d58", borderRadius: 999 }} />
          </div>
          <strong style={{ fontSize: 13, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{value.toFixed(5)}</strong>
        </div>
      ))}
    </div>
  );
}

export default function AnalysisResultsView({ data, onBack, backLabel = "← Back to Workspace" }) {
  const [activeTab, setActiveTab] = useState("report");
  const [reportOverride, setReportOverride] = useState(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [reportError, setReportError] = useState("");

  useEffect(() => {
    setReportOverride(null);
    setReportError("");
    setActiveTab("report");
  }, [data?.experiment_id, data?.plan?.goal]);

  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === "Escape" && onBack) {
        const tag = document.activeElement?.tagName;
        if (tag !== "INPUT" && tag !== "TEXTAREA" && tag !== "SELECT") {
          onBack();
        }
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onBack]);

  if (!data) return null;

  const {
    dataset_summary,
    plan,
    models = [],
    critic,
    security,
    eda,
    statistics,
    preprocessing,
    explainability,
    execution_errors = [],
    status,
    blocked_at,
    replanning,
    report,
    research,
    experiment_id,
    agent_trace = [],
  } = data;

  const securityResult = security || critic?.security;
  const visibleReport = reportOverride || report;
  const scorePct = critic ? Math.round((critic.score || 0) * 100) : 0;

  async function handleRegenerateReport() {
    if (!experiment_id || reportBusy) return;
    setReportBusy(true);
    setReportError("");
    try {
      const response = await regenerateReport(experiment_id);
      setReportOverride(response.report);
    } catch (error) {
      setReportError(error.message || "Could not regenerate report.");
    } finally {
      setReportBusy(false);
    }
  }

  function exportJSON() {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `datapilot_audit_${experiment_id ? experiment_id.slice(0, 8) : Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function exportMarkdown() {
    if (!visibleReport?.markdown) return;
    const blob = new Blob([visibleReport.markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `datapilot-report-${experiment_id ? experiment_id.slice(0, 8) : "analysis"}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="results-shell">
      <div className="panel">
        <div className="results-header">
          <div>
            {onBack && (
              <button type="button" className="text-btn" onClick={onBack} style={{ paddingLeft: 0, marginBottom: 6 }}>
                {backLabel}
              </button>
            )}
            <span className="eyebrow">
              {data.dataset_name || "Dataset"} · {plan?.problem_type && plan.problem_type !== "unknown" ? plan.problem_type : "Exploratory analysis"}
            </span>
            <h2 style={{ fontSize: 20, marginTop: 4 }}>{plan?.goal || "Analysis Results"}</h2>
            <div className="muted" style={{ marginTop: 4 }}>
              Status: <strong style={{ textTransform: "capitalize" }}>{status || "unknown"}</strong>
              {experiment_id ? ` · ID ${experiment_id.slice(0, 8)}` : ""}
              {visibleReport?.llm?.model ? ` · Narrative: ${visibleReport.llm.model}` : ""}
            </div>
          </div>

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            {visibleReport?.markdown && (
              <button type="button" className="secondary-btn" onClick={exportMarkdown}>
                Export Markdown
              </button>
            )}
            {experiment_id && visibleReport?.markdown && (
              <a
                className="primary-btn"
                href={`/api/history/${encodeURIComponent(experiment_id)}/report.pdf`}
                target="_blank"
                rel="noopener noreferrer"
              >
                Export PDF
              </a>
            )}
            <button type="button" className="ghost-btn" onClick={exportJSON}>
              Export JSON
            </button>
          </div>
        </div>

        <div className="results-tabs" role="tablist" aria-label="Analysis result sections" style={{ marginTop: 14 }}>
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={activeTab === tab.id}
              className={`results-tab ${activeTab === tab.id ? "active" : ""}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* TAB 1: REPORT & ANSWER */}
      {activeTab === "report" && (
        <>
          <div className="kpi-grid">
            <div className="kpi-box">
              <small>Dataset shape</small>
              <strong>
                {fmtNum(dataset_summary?.rows, 0)} × {fmtNum(dataset_summary?.columns_count, 0)}
              </strong>
            </div>
            <div className="kpi-box">
              <small>Target column</small>
              <strong>{plan?.target_column || "Exploratory"}</strong>
            </div>
            <div className="kpi-box">
              <small>Models evaluated</small>
              <strong>{models.length}</strong>
            </div>
            <div className="kpi-box">
              <small>Critic readiness</small>
              <strong>{scorePct}%</strong>
            </div>
          </div>

          {visibleReport?.question_answer && (
            <div className="answer-banner" style={{ flexDirection: "column", alignItems: "stretch", gap: 12 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 18, flexWrap: "wrap" }}>
                <div>
                  <span className="eyebrow" style={{ color: "var(--dp-lime)" }}>
                    Direct answer · {visibleReport.question_answer.planner_provider === "deterministic_fallback" ? "deterministic query" : `routed via ${visibleReport.question_answer.planner_provider || "computed data"}`}
                  </span>
                  <div style={{ fontSize: 18, fontWeight: 600, marginTop: 4 }}>
                    {visibleReport.question_answer.answer_type === "scalar_metric"
                      ? `${visibleReport.question_answer.operation?.toUpperCase()} ${visibleReport.question_answer.target_column}: ${fmtNum(visibleReport.question_answer.answer_value, 2)}`
                      : `${visibleReport.question_answer.category} · ${fmtNum(visibleReport.question_answer.count, 0)} of ${fmtNum(visibleReport.question_answer.total, 0)}`}
                  </div>
                  {visibleReport.question_answer.summary && (
                    <div style={{ fontSize: 13, opacity: 0.9, marginTop: 4 }}>
                      {visibleReport.question_answer.summary}
                    </div>
                  )}
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 6, fontSize: 12, opacity: 0.88 }}>
                    {visibleReport.question_answer.target_column && (
                      <span>Column: <code>{visibleReport.question_answer.target_column}</code></span>
                    )}
                    {(visibleReport.question_answer.filters_applied || []).map((f, idx) => (
                      <span key={idx} style={{ background: "rgba(255,255,255,0.12)", padding: "1px 8px", borderRadius: 999 }}>
                        {f.column} {f.op} {String(f.value)}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="pct">
                  {visibleReport.question_answer.answer_type === "scalar_metric"
                    ? fmtNum(visibleReport.question_answer.answer_value, 2)
                    : `${Number(visibleReport.question_answer.percentage || 0).toFixed(2)}%`}
                </div>
              </div>
              {visibleReport.question_answer.rows?.length > 0 && (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 8 }}>
                  {visibleReport.question_answer.rows.slice(0, 6).map((row) => (
                    <div key={row.label} style={{ background: "rgba(255,255,255,0.09)", padding: "8px 10px", borderRadius: 6, fontSize: 13 }}>
                      <div style={{ fontWeight: 600 }}>{row.label}</div>
                      <div style={{ fontVariantNumeric: "tabular-nums", opacity: 0.9 }}>
                        {fmtNum(row.value, 2)}{row.percentage != null ? ` · ${Number(row.percentage).toFixed(1)}%` : ""}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {experiment_id && visibleReport?.markdown && (
            <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <button type="button" className="secondary-btn" disabled={reportBusy} onClick={handleRegenerateReport}>
                {reportBusy ? "Regenerating narrative…" : "Regenerate narrative with LLM"}
              </button>
              <span className="muted">
                Narrative status: <b>{visibleReport?.llm?.status || "deterministic"}</b>
              </span>
              {reportError && <span style={{ color: "var(--dp-danger-fg)", fontSize: 13 }}>{reportError}</span>}
            </div>
          )}

          {(visibleReport?.charts || []).map((chart) => (
            <ReportChart key={chart.id || chart.title} chart={chart} />
          ))}

          {visibleReport?.markdown ? (
            <MarkdownReport markdown={visibleReport.markdown} />
          ) : (
            <div className="panel empty-state">No Markdown report was generated for this run.</div>
          )}
        </>
      )}

      {/* TAB 2: DATA & EDA */}
      {activeTab === "data" && (
        <>
          <div className="kpi-grid">
            <div className="kpi-box"><small>Rows</small><strong>{fmtNum(eda?.shape?.rows ?? dataset_summary?.rows, 0)}</strong></div>
            <div className="kpi-box"><small>Columns</small><strong>{fmtNum(eda?.shape?.columns ?? dataset_summary?.columns_count, 0)}</strong></div>
            <div className="kpi-box"><small>Duplicate rows</small><strong>{fmtNum(dataset_summary?.duplicate_rows, 0)}</strong></div>
            <div className="kpi-box"><small>Numeric / Categorical</small><strong>{eda?.numeric_columns?.length ?? 0} / {eda?.categorical_columns?.length ?? 0}</strong></div>
          </div>

          {dataset_summary?.warnings?.length > 0 && (
            <div className="status-banner warn">
              <strong>Profiler warnings</strong>
              <ul className="studio-list" style={{ marginTop: 8 }}>
                {dataset_summary.warnings.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
            </div>
          )}

          <section className="panel">
            <div className="panel-head"><h3>Column profiles</h3></div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Column</th>
                    <th>Kind</th>
                    <th className="num">Unique values</th>
                    <th className="num">Missing count</th>
                  </tr>
                </thead>
                <tbody>
                  {(dataset_summary?.columns || []).map((c) => (
                    <tr key={c.name}>
                      <td><b>{c.name}</b></td>
                      <td style={{ textTransform: "capitalize" }}>{c.kind}</td>
                      <td className="num">{fmtNum(c.unique_count, 0)}</td>
                      <td className="num" style={{ color: c.missing_count > 0 ? "var(--dp-danger-fg)" : "inherit" }}>
                        {fmtNum(c.missing_count, 0)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {dataset_summary?.preview?.length > 0 && (
            <section className="panel">
              <div className="panel-head"><h3>Sample rows (first {dataset_summary.preview.length})</h3></div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      {Object.keys(dataset_summary.preview[0]).map((k) => (
                        <th key={k}>{k}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {dataset_summary.preview.map((row, i) => (
                      <tr key={i}>
                        {Object.values(row).map((v, j) => (
                          <td key={j}>{String(v)}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          <DescriptiveStatsTable descriptive={statistics?.descriptive} />
          <CorrelationMatrix correlation={statistics?.correlation} />
          <InferentialTestsSection tests={statistics?.tests} notes={statistics?.notes} />

          {eda?.histograms && Object.keys(eda.histograms).length > 0 && (
            <section className="panel">
              <div className="panel-head"><h3>Numeric distributions</h3></div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
                {Object.entries(eda.histograms).slice(0, 8).map(([name, histogram]) => (
                  <HistogramCard key={name} title={name} histogram={histogram} />
                ))}
              </div>
            </section>
          )}

          {eda?.outliers && Object.keys(eda.outliers).length > 0 && (
            <section className="panel">
              <div className="panel-head"><h3>IQR outlier summary</h3></div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Column</th>
                      <th className="num">Outlier count</th>
                      <th className="num">Share</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(eda.outliers).map(([col, info]) => (
                      <tr key={col}>
                        <td><b>{col}</b></td>
                        <td className="num">{fmtNum(info?.count, 0)}</td>
                        <td className="num">{fmtNum(info?.percentage, 2)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )}

      {/* TAB 3: MODELS & SHAP */}
      {activeTab === "models" && (
        <>
          <section className="panel">
            <div className="panel-head"><h3>Leakage-safe preprocessing</h3></div>
            <div className="kpi-grid">
              <div className="kpi-box"><small>Transformer</small><strong>{preprocessing?.execution?.transformer || "—"}</strong></div>
              <div className="kpi-box"><small>Fit scope</small><strong>{preprocessing?.execution?.fit_scope || "—"}</strong></div>
              <div className="kpi-box"><small>Train / Val rows</small><strong>{fmtNum(preprocessing?.execution?.fit_rows, 0)} / {fmtNum(preprocessing?.execution?.validation_rows, 0)}</strong></div>
              <div className="kpi-box"><small>Features after transform</small><strong>{fmtNum(preprocessing?.execution?.transformed_feature_count, 0)}</strong></div>
            </div>
            {preprocessing?.excluded_identifier_columns?.length > 0 && (
              <p className="muted" style={{ marginTop: 12, marginBottom: 0 }}>
                Excluded identifier columns: <code>{preprocessing.excluded_identifier_columns.join(", ")}</code>
              </p>
            )}
            {data.cross_validation?.summary && (
              <p className="muted" style={{ marginTop: 8, marginBottom: 0 }}>
                Cross-validation: <b>{data.cross_validation.summary}</b>
              </p>
            )}
          </section>

          <section className="panel">
            <div className="panel-head"><h3>Model comparison</h3></div>
            {models.length === 0 ? (
              <div className="empty-state">No predictive models were trained (exploratory / question-answering plan).</div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Model</th>
                      <th className="num">Train score</th>
                      <th className="num">Val score</th>
                      <th>Key metrics</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {models.map((m, i) => {
                      const overfit = m.train_score != null && m.validation_score != null && m.train_score - m.validation_score >= 0.15;
                      const metricText = Object.entries(m.metrics || {})
                        .filter(([k, v]) => k !== "confusion_matrix" && typeof v === "number")
                        .map(([k, v]) => `${k}: ${Number(v).toFixed(4)}`)
                        .join(" · ");
                      return (
                        <tr key={`${m.model_name}-${i}`}>
                          <td><b style={{ textTransform: "capitalize" }}>{String(m.model_name).replace(/_/g, " ")}</b></td>
                          <td className="num">{fmtNum(m.train_score, 4)}</td>
                          <td className="num"><b>{fmtNum(m.validation_score, 4)}</b></td>
                          <td className="mono" style={{ fontSize: 12 }}>{metricText || "—"}</td>
                          <td>
                            <span className={`status-pill ${overfit ? "warn" : "success"}`}>
                              {overfit ? "Overfit risk" : "Evaluated"}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="panel">
            <div className="panel-head">
              <h3>Explainability ({explainability?.method || "not available"})</h3>
              {explainability?.best_model && (
                <span className="muted" style={{ textTransform: "capitalize" }}>
                  Best model: <b>{explainability.best_model.replace(/_/g, " ")}</b>
                </span>
              )}
            </div>
            {Object.keys(explainability?.feature_importance || {}).length > 0 ? (
              <ContributionBars values={explainability.feature_importance} />
            ) : (
              <div className="empty-state">No feature importance available for this run.</div>
            )}
          </section>
        </>
      )}

      {/* TAB 4: CRITIC & SECURITY */}
      {activeTab === "quality" && (
        <>
          <div className={`status-banner ${securityResult?.allowed ? "safe" : "danger"}`}>
            <strong>Pre-execution Security Guardian: {securityResult?.allowed ? "Execution Allowed" : "Execution Blocked"}</strong>
            <div style={{ fontSize: 13, marginTop: 4 }}>
              Risk level: <b>{(securityResult?.risk_level || "unknown").toUpperCase()}</b> · {securityResult?.rationale || ""}
            </div>
            {blocked_at && <div style={{ fontSize: 13, marginTop: 4 }}>Pipeline stopped at: <code>{blocked_at}</code></div>}
          </div>

          {securityResult?.violations?.length > 0 && (
            <section className="panel">
              <div className="panel-head"><h3>Security violations</h3></div>
              <ul className="studio-list danger">
                {securityResult.violations.map((v, i) => <li key={i}>{v}</li>)}
              </ul>
            </section>
          )}

          <section className="panel">
            <div className="panel-head">
              <h3>Critic quality gate</h3>
              <span className={`status-pill ${critic?.satisfactory ? "success" : "warn"}`}>
                Readiness {scorePct}% · {critic?.satisfactory ? "Passed" : "Needs review"}
              </span>
            </div>
            {critic?.issues?.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <strong style={{ fontSize: 13 }}>Identified issues</strong>
                <ul className="studio-list" style={{ marginTop: 8 }}>
                  {critic.issues.map((iss, i) => <li key={i}>{iss}</li>)}
                </ul>
              </div>
            )}
            {critic?.recommendations?.length > 0 && (
              <div>
                <strong style={{ fontSize: 13 }}>Recommendations</strong>
                <ul className="studio-list" style={{ marginTop: 8 }}>
                  {critic.recommendations.map((rec, i) => <li key={i}>{rec}</li>)}
                </ul>
              </div>
            )}
            {execution_errors.length > 0 && (
              <div className="status-banner danger" style={{ marginTop: 12, marginBottom: 0 }}>
                <strong>Execution errors</strong>
                <ul className="studio-list danger" style={{ marginTop: 8 }}>
                  {execution_errors.map((e, i) => <li key={i}>{typeof e === "string" ? e : JSON.stringify(e)}</li>)}
                </ul>
              </div>
            )}
          </section>

          <section className="panel">
            <div className="panel-head">
              <h3>Bounded replanning & execution trace</h3>
              <span className="muted">
                Retries used: {replanning?.history?.filter((x) => x.attempted).length || 0} / {replanning?.max_retries || 1}
              </span>
            </div>
            {agent_trace.length > 0 ? (
              <div className="trace-list">
                {agent_trace.map((step, i) => (
                  <div className="trace-row" key={`${step.agent}-${i}`}>
                    <b>{step.agent}</b>
                    <span>{step.detail}</span>
                    <span className={`status-pill ${step.status}`}>{step.status}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="chip-row">
                {(plan?.steps || []).map((step, i) => (
                  <span className="selected-badge" key={`${step}-${i}`}>
                    {i + 1}. {step.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
            )}
          </section>
        </>
      )}

      {/* TAB 5: RESEARCH */}
      {activeTab === "research" && (
        <>
          <section className="panel">
            <div className="panel-head"><h3>Retrieved research papers & records</h3></div>
            {research?.research_query && (
              <p className="muted" style={{ marginTop: 0 }}>Query: <code>{research.research_query}</code></p>
            )}
            {!research?.sources?.length ? (
              <div className="empty-state">No external papers were retrieved for this run.</div>
            ) : (
              <div style={{ display: "grid", gap: 12 }}>
                {research.sources.map((source, index) => {
                  const doiUrl = source.doi
                    ? safeExternalUrl(`https://doi.org/${String(source.doi).replace(/^https?:\/\/doi\.org\//, "")}`)
                    : null;
                  const sourceUrl = safeExternalUrl(source.url);
                  return (
                    <article key={source.doi || source.url || index} style={{ padding: 14, border: "1px solid var(--dp-border)", borderRadius: 8, background: "var(--dp-canvas)" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
                        <strong style={{ fontSize: 15 }}>{source.title || "Untitled research record"}</strong>
                        <span className="status-pill">{source.provider || "Index"} · {source.evidence_level || "metadata_only"}</span>
                      </div>
                      <div className="muted" style={{ marginTop: 4 }}>
                        {(source.authors || []).join(", ") || "Authors not listed"} · {source.year || "n.d."} · {source.source || "Unknown source"}
                      </div>
                      {source.abstract && (
                        <p style={{ fontSize: 13, color: "var(--dp-text-secondary)", margin: "8px 0" }}>
                          {source.abstract.slice(0, 800)}{source.abstract.length > 800 ? "…" : ""}
                        </p>
                      )}
                      <div style={{ display: "flex", gap: 14, fontSize: 13, marginTop: 6 }}>
                        {doiUrl && <a href={doiUrl} target="_blank" rel="noopener noreferrer" style={{ color: "var(--dp-forest)" }}>Open DOI ↗</a>}
                        {sourceUrl && <a href={sourceUrl} target="_blank" rel="noopener noreferrer" style={{ color: "var(--dp-forest)" }}>Source record ↗</a>}
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </section>

          {research?.findings?.length > 0 && (
            <section className="panel">
              <div className="panel-head"><h3>Methodology guidance (offline)</h3></div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 12 }}>
                {research.findings.map((finding, idx) => (
                  <article key={`${finding.topic}-${idx}`} style={{ padding: 14, border: "1px solid var(--dp-border)", borderRadius: 8, background: "var(--dp-canvas)" }}>
                    <strong style={{ fontSize: 14 }}>{finding.topic}</strong>
                    <p style={{ fontSize: 13, color: "var(--dp-text-secondary)", margin: "6px 0" }}>{finding.finding}</p>
                    <div className="muted"><b>Recommendation:</b> {finding.recommendation}</div>
                  </article>
                ))}
              </div>
            </section>
          )}
        </>
      )}

      {/* TAB 6: RAW AUDIT */}
      {activeTab === "audit" && (
        <section className="panel">
          <div className="panel-head">
            <h3>Raw analysis JSON</h3>
            <button type="button" className="secondary-btn" onClick={exportJSON}>Download JSON</button>
          </div>
          <pre style={{ maxHeight: 560 }}>{JSON.stringify(data, null, 2)}</pre>
        </section>
      )}
    </div>
  );
}
