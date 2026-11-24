import { useState } from "react";
import { regenerateReport } from "../api";

const T = {
  ink: "#2C221E",
  inkLight: "#4A3830",
  sepia: "#7A5C48",
  clay: "#A77A65",
  cream: "#FDFBF7",
  creamDark: "#F4EFEA",
  creamMid: "#EDE5DC",
  rule: "rgba(44,34,30,0.18)",
  ruleMid: "rgba(44,34,30,0.10)",
  playfair: "'Playfair Display', Georgia, serif",
  garamond: "'EB Garamond', Georgia, serif",
  inter: "'Inter', system-ui, sans-serif",
};

function SectionTitle({ children }) {
  return <div style={{ fontFamily: T.playfair, fontSize: 17, fontWeight: 600, marginBottom: 10 }}>{children}</div>;
}

function Pill({ children }) {
  return <span style={{ padding: "5px 9px", background: T.cream, border: `1px solid ${T.rule}`, fontFamily: T.inter, fontSize: 11, textTransform: "capitalize" }}>{children}</span>;
}

function InfoCard({ title, value }) {
  return <div style={{ padding: 14, background: T.creamDark, border: `1px solid ${T.rule}` }}><div style={{ fontSize: 11, color: T.clay, fontStyle: "italic" }}>{title}</div><div style={{ fontFamily: T.playfair, fontSize: 17, fontWeight: 600, marginTop: 4, textTransform: "capitalize" }}>{String(value)}</div></div>;
}

function MetricCard({ label, value }) {
  return <div style={{ padding: 12, background: T.creamDark, border: `1px solid ${T.ruleMid}` }}><div style={{ fontSize: 10, color: T.clay }}>{label}</div><div style={{ fontFamily: T.playfair, fontSize: 19, fontWeight: 700 }}>{String(value)}</div></div>;
}

function StatusPanel({ title, value, subtitle, tone }) {
  const safe = tone === "safe";
  return <div style={{ padding: 18, marginBottom: 18, border: `1.5px solid ${safe ? "#2D6A4F" : "#A8422B"}`, background: safe ? "rgba(45,106,79,0.06)" : "rgba(168,66,43,0.07)" }}><div style={{ fontFamily: T.playfair, fontSize: 19, fontWeight: 700 }}>{title}</div><div style={{ fontFamily: T.inter, fontSize: 13, fontWeight: 700, marginTop: 5, color: safe ? "#2D6A4F" : "#A8422B" }}>{value}</div><div style={{ fontSize: 13, color: T.sepia, marginTop: 4 }}>{subtitle}</div></div>;
}

function ListBlock({ title, items, danger = false }) {
  if (!items?.length) return null;
  return <div style={{ marginBottom: 18 }}><SectionTitle>{title}</SectionTitle><ul style={{ margin: 0, paddingLeft: 20 }}>{items.map((x, i) => <li key={i} style={{ fontSize: 13, marginBottom: 5, color: danger ? "#A8422B" : T.ink }}>{String(x)}</li>)}</ul></div>;
}

function JsonArrayBlock({ title, items }) {
  if (!items?.length) return null;
  return <ListBlock title={title} items={items.map((x) => typeof x === "string" ? x : JSON.stringify(x))} />;
}

function JsonTable({ title, data }) {
  const entries = Object.entries(data || {});
  if (!entries.length) return null;
  return <div style={{ marginBottom: 18 }}><SectionTitle>{title}</SectionTitle><div style={{ overflowX: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse", fontFamily: T.inter, fontSize: 12 }}><tbody>{entries.map(([k,v]) => <tr key={k} style={{ borderBottom: `1px solid ${T.ruleMid}` }}><td style={{ padding: "7px 8px", fontWeight: 600 }}>{k}</td><td style={{ padding: "7px 8px", color: T.sepia }}>{typeof v === "object" ? JSON.stringify(v) : String(v)}</td></tr>)}</tbody></table></div></div>;
}

function MiniBars({ title, values }) {
  const entries = Object.entries(values || {});
  if (!entries.length) return null;
  const max = Math.max(1, ...entries.map(([, value]) => Number(value) || 0));
  return <div style={{ marginBottom: 20, padding: 14, border: `1px solid ${T.ruleMid}`, background: T.creamDark }}>
    <SectionTitle>{title}</SectionTitle>
    <div style={{ display: "flex", alignItems: "end", gap: 8, minHeight: 132, overflowX: "auto" }}>
      {entries.map(([label, value]) => { const n = Number(value) || 0; return <div key={label} title={`${label}: ${n}`} style={{ minWidth: 38, flex: 1, display: "flex", flexDirection: "column", justifyContent: "end", alignItems: "center", height: 120 }}>
        <span style={{ fontSize: 10, color: T.sepia, marginBottom: 4 }}>{n}</span>
        <div style={{ width: "100%", maxWidth: 54, height: `${Math.max(3, n / max * 88)}px`, background: T.clay, border: `1px solid ${T.sepia}` }} />
        <span style={{ fontSize: 9, color: T.ink, marginTop: 5, maxWidth: 64, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{label}</span>
      </div>; })}
    </div>
  </div>;
}

function HistogramCard({ title, histogram }) {
  if (!histogram?.counts?.length) return null;
  const max = Math.max(1, ...histogram.counts);
  return <div style={{ marginBottom: 16, padding: 14, border: `1px solid ${T.ruleMid}`, background: T.creamDark }}>
    <SectionTitle>{title}</SectionTitle>
    <div style={{ display: "flex", alignItems: "end", gap: 4, height: 110 }}>
      {histogram.counts.map((count, i) => <div key={i} title={`${histogram.bin_edges[i]?.toFixed?.(2) ?? ""}–${histogram.bin_edges[i+1]?.toFixed?.(2) ?? ""}: ${count}`} style={{ flex: 1, minWidth: 4, height: `${Math.max(2, count / max * 90)}px`, background: T.clay }} />)}
    </div>
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: T.sepia, marginTop: 6 }}><span>{histogram.bin_edges[0]}</span><span>{histogram.bin_edges[histogram.bin_edges.length - 1]}</span></div>
  </div>;
}


function ReportChart({ chart }) {
  const rows = chart?.data || [];
  if (!rows.length) return null;
  const max = Math.max(1, ...rows.map((row) => Number(row.value) || 0));
  const palette = ["#78964A", "#A77A65", "#D2B96F", "#567C70", "#B7A08B", "#8C9B6B"];
  if (chart.type === "pie" || chart.type === "donut") {
    let cursor = 0;
    const total = rows.reduce((sum, row) => sum + (Number(row.value) || 0), 0) || 1;
    const segments = rows.map((row, index) => {
      const start = cursor;
      cursor += ((Number(row.value) || 0) / total) * 100;
      return `${palette[index % palette.length]} ${start}% ${cursor}%`;
    });
    return <div style={{ marginBottom: 18, padding: 18, background: T.cream, border: `1px solid ${T.rule}`, borderRadius: 8 }}>
      <SectionTitle>{chart.title}</SectionTitle>
      <div style={{ display: "grid", gridTemplateColumns: "minmax(150px, 220px) 1fr", gap: 24, alignItems: "center" }}>
        <div style={{ width: "min(100%, 190px)", aspectRatio: "1", borderRadius: "50%", margin: "auto", background: `conic-gradient(${segments.join(", ")})`, position: "relative" }}>
          {chart.type === "donut" && <div style={{ position: "absolute", inset: "27%", borderRadius: "50%", background: T.cream, display: "grid", placeItems: "center", fontFamily: T.playfair, fontSize: 13, color: T.ink }}>{total.toLocaleString()}</div>}
        </div>
        <div style={{ display: "grid", gap: 10 }}>
          {rows.map((row, index) => <div key={row.label} style={{ display: "grid", gridTemplateColumns: "12px 1fr auto", gap: 9, alignItems: "center", fontSize: 12 }}>
            <span style={{ width: 10, height: 10, borderRadius: 3, background: palette[index % palette.length] }} />
            <span style={{ color: T.ink }}>{row.label}</span>
            <strong style={{ color: T.ink, fontVariantNumeric: "tabular-nums" }}>{(Number(row.value) || 0).toLocaleString()} {row.percentage != null ? `· ${Number(row.percentage).toFixed(2)}%` : ""}</strong>
          </div>)}
        </div>
      </div>
    </div>;
  }
  return (
    <div style={{ marginBottom: 16, padding: 16, background: T.cream, border: `1px solid ${T.rule}`, borderRadius: 8 }}>
      <SectionTitle>{chart.title}</SectionTitle>
      <div style={{ display: "grid", gap: 10 }}>
        {rows.map((row, index) => (
          <div key={row.label} style={{ display: "grid", gridTemplateColumns: "minmax(90px, 180px) 1fr auto", gap: 10, alignItems: "center" }}>
            <span title={row.label} style={{ fontSize: 12, color: T.ink, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{row.label}</span>
            <div style={{ height: 14, background: T.creamMid, overflow: "hidden", borderRadius: 20 }}>
              <div style={{ width: `${Math.max(1, (Number(row.value) || 0) / max * 100)}%`, height: "100%", background: palette[index % palette.length], borderRadius: 20 }} />
            </div>
            <span style={{ minWidth: 82, textAlign: "right", fontSize: 11, color: T.sepia, fontVariantNumeric: "tabular-nums" }}>
              {(Number(row.value) || 0).toLocaleString()} {row.percentage != null ? `· ${Number(row.percentage).toFixed(2)}%` : ""}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ContributionBars({ values }) {
  const entries = Object.entries(values || {}).filter(([, value]) => typeof value === "number").sort((a, b) => Math.abs(b[1]) - Math.abs(a[1])).slice(0, 15);
  if (!entries.length) return null;
  const max = Math.max(0.000001, ...entries.map(([, value]) => Math.abs(value)));
  return <div style={{ display: "grid", gap: 10, marginTop: 10 }}>
    {entries.map(([feature, value]) => <div key={feature} style={{ display: "grid", gridTemplateColumns: "minmax(120px, 220px) 1fr 82px", gap: 10, alignItems: "center" }}>
      <span title={feature} style={{ color: T.ink, fontSize: 11, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{feature}</span>
      <div style={{ height: 13, background: T.creamMid, borderRadius: 20, overflow: "hidden" }}><div style={{ width: `${Math.max(1, Math.abs(value) / max * 100)}%`, height: "100%", background: "#78964A", borderRadius: 20 }} /></div>
      <strong style={{ color: T.ink, fontSize: 11, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{value.toFixed(6)}</strong>
    </div>)}
  </div>;
}

function ResearchFindingCards({ findings = [] }) {
  if (!findings.length) return null;
  return <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10, marginBottom: 18 }}>
    {findings.map((finding, index) => <article key={`${finding.topic || "finding"}-${index}`} style={{ padding: 14, background: T.cream, border: `1px solid ${T.rule}`, borderRadius: 7 }}>
      <div style={{ fontSize: 10, color: "#66834A", textTransform: "uppercase", letterSpacing: 1, marginBottom: 7 }}>Methodology guidance</div>
      <strong style={{ color: T.ink, fontFamily: T.playfair, fontSize: 14 }}>{finding.topic || "Finding"}</strong>
      <p style={{ color: T.inkLight, fontSize: 12, lineHeight: 1.55, margin: "7px 0" }}>{finding.finding || ""}</p>
      <div style={{ color: T.sepia, fontSize: 11, lineHeight: 1.5 }}><strong>Recommendation:</strong> {finding.recommendation || ""}</div>
    </article>)}
  </div>;
}

function safeExternalUrl(rawUrl) {
  if (typeof rawUrl !== "string" || !rawUrl.trim()) return null;
  try {
    const parsed = new URL(rawUrl.trim(), window.location.origin);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.href : null;
  } catch {
    return null;
  }
}

function ResearchSourceCards({ sources = [] }) {
  if (!sources.length) return <div style={{ padding: 14, background: T.creamDark, color: T.sepia, fontSize: 12 }}>No external papers were retrieved for this run. Offline recommendations are shown separately and are not presented as papers.</div>;
  return <div style={{ display: "grid", gap: 10, marginBottom: 18 }}>
    {sources.map((source, index) => {
      const doiUrl = source.doi ? safeExternalUrl(`https://doi.org/${String(source.doi).replace(/^https?:\/\/doi\.org\//, "")}`) : null;
      const sourceUrl = safeExternalUrl(source.url);
      return <article key={source.doi || source.url || index} style={{ padding: 15, background: T.cream, border: `1px solid ${T.rule}`, borderRadius: 7 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
          <strong style={{ color: T.ink, fontFamily: T.playfair, fontSize: 15 }}>{source.title || "Untitled research record"}</strong>
          <Pill>{source.provider || "Research index"} · {source.evidence_level || "metadata_only"}</Pill>
        </div>
        <div style={{ color: T.sepia, fontSize: 11, marginTop: 6 }}>{(source.authors || []).join(", ") || "Authors not listed"} · {source.year || "Year unavailable"} · {source.source || "Source unavailable"}</div>
        {source.abstract && <p style={{ color: T.inkLight, fontSize: 12, lineHeight: 1.6, margin: "9px 0" }}>{source.abstract.slice(0, 900)}{source.abstract.length > 900 ? "…" : ""}</p>}
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 8, fontSize: 11 }}>
          {doiUrl && <a href={doiUrl} target="_blank" rel="noopener noreferrer" style={{ color: "#55783d" }}>Open DOI ↗</a>}
          {sourceUrl && <a href={sourceUrl} target="_blank" rel="noopener noreferrer" style={{ color: "#55783d" }}>Source record ↗</a>}
        </div>
      </article>;
    })}
  </div>;
}

function MarkdownReport({ markdown }) {
  if (!markdown) return null;
  const inline = (value) => value.split(/(\*\*.*?\*\*|`[^`]+`)/g).map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={index}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`")) return <code key={index} style={{ background: T.creamMid, padding: "1px 4px" }}>{part.slice(1, -1)}</code>;
    return part;
  });
  return <div style={{ padding: 18, background: T.cream, border: `1px solid ${T.rule}`, color: T.ink, fontFamily: T.inter, fontSize: 13, lineHeight: 1.7 }}>
    {markdown.split("\n").map((line, index) => {
      if (line.startsWith("# ")) return <h2 key={index} style={{ fontFamily: T.playfair, fontSize: 23, margin: "4px 0 14px" }}>{inline(line.slice(2))}</h2>;
      if (line.startsWith("## ")) return <h3 key={index} style={{ fontFamily: T.playfair, fontSize: 18, margin: "20px 0 8px", color: T.ink }}>{inline(line.slice(3))}</h3>;
      if (line.startsWith("### ")) return <h4 key={index} style={{ fontSize: 14, margin: "14px 0 6px" }}>{inline(line.slice(4))}</h4>;
      if (line.startsWith("- ")) return <div key={index} style={{ paddingLeft: 15, position: "relative", margin: "3px 0" }}><span style={{ position: "absolute", left: 0, color: "#78964A" }}>•</span>{inline(line.slice(2))}</div>;
      if (!line.trim()) return <div key={index} style={{ height: 5 }} />;
      return <p key={index} style={{ margin: "4px 0" }}>{inline(line)}</p>;
    })}
  </div>;
}

export default function AnalysisResultsModal({ data, onClose }) {
  const [activeTab, setActiveTab] = useState("overview");
  const [reportOverride, setReportOverride] = useState(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [reportError, setReportError] = useState("");

  if (!data) return null;

  const { dataset_summary, plan, models, critic, security, eda, preprocessing, explainability, execution_errors, status, blocked_at, replanning, report, research, experiment_id } = data;
  const securityResult = security || critic?.security;
  const visibleReport = reportOverride || report;

  async function handleRegenerateReport() {
    if (!experiment_id || reportBusy) return;
    setReportBusy(true); setReportError("");
    try { const response = await regenerateReport(experiment_id); setReportOverride(response.report); }
    catch (error) { setReportError(error.message || "Could not regenerate report."); }
    finally { setReportBusy(false); }
  }

  function exportJSON() {
    const jsonString = `data:text/json;charset=utf-8,${encodeURIComponent(
      JSON.stringify(data, null, 2)
    )}`;
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", jsonString);
    downloadAnchor.setAttribute("download", `datapilot_audit_${Date.now()}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  }

  const scorePct = critic ? Math.round(critic.score * 100) : 0;
  const isSatisfactory = critic?.satisfactory;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(19,39,29,0.84)",
        backdropFilter: "blur(6px)",
        padding: 24,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          width: "min(1440px, 96vw)",
          maxWidth: 1440,
          maxHeight: "94vh",
          background: T.cream,
          border: `1.5px solid ${T.ink}`,
          boxShadow: "0 24px 80px rgba(0,0,0,0.38)",
          display: "flex",
          flexDirection: "column",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Header banner */}
        <div
          style={{
            padding: "16px 28px",
            borderBottom: `1px solid ${T.rule}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: T.creamDark,
          }}
        >
          <div>
            <div
              style={{
                fontFamily: T.garamond,
                fontSize: 12,
                fontStyle: "italic",
                color: T.clay,
                letterSpacing: "0.06em",
              }}
            >
              Autonomous Multi-Agent Synthesis &middot; Audit Report
            </div>
            <div
              style={{
                fontFamily: T.playfair,
                fontSize: 22,
                fontWeight: 700,
                color: T.ink,
              }}
            >
              {plan?.goal || "Analysis Results"}
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button
              onClick={exportJSON}
              style={{
                padding: "6px 14px",
                fontFamily: T.inter,
                fontSize: 12,
                background: "transparent",
                border: `1px solid ${T.sepia}`,
                color: T.ink,
                cursor: "pointer",
                transition: "background 0.2s",
              }}
            >
              &darr; Export JSON
            </button>
            <button
              onClick={onClose}
              style={{
                width: 32,
                height: 32,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: "transparent",
                border: `1px solid ${T.rule}`,
                cursor: "pointer",
                fontFamily: T.inter,
                fontSize: 18,
                color: T.ink,
              }}
            >
              &times;
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div
          style={{
            display: "flex",
            alignItems: "stretch",
            flexWrap: "nowrap",
            flexShrink: 0,
            borderBottom: `1px solid ${T.rule}`,
            background: T.cream,
            padding: "0 16px",
            overflowX: "auto",
            overflowY: "hidden",
            whiteSpace: "nowrap",
            minWidth: 0,
            scrollbarWidth: "thin",
          }}
        >
          {[
            { id: "overview", label: "Synthesis Overview" },
            { id: "profile", label: "Stage I · Ingest & Profile" },
            { id: "plan", label: "Stage II · Planner Agent" },
            { id: "security", label: "Stage III · Security" },
            { id: "eda", label: "Stage IV · EDA" },
            { id: "statistics", label: "Stage V · Statistics" },
            { id: "preprocessing", label: "Stage VI · Preprocessing" },
            { id: "models", label: "Stage VII · Evidence & Models" },
            { id: "explainability", label: "Stage VIII · Explainability" },
            { id: "critic", label: "Stage IX · Critic Gate" },
            { id: "replanning", label: "Stage X · Replanner" },
            { id: "research", label: "Stage XI · Research" },
            { id: "report", label: "Stage XII · Final Report" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: "12px 15px",
                flex: "0 0 auto",
                width: "max-content",
                minWidth: "max-content",
                whiteSpace: "nowrap",
                fontFamily: T.garamond,
                fontSize: 14,
                fontWeight: activeTab === tab.id ? 600 : 400,
                color: activeTab === tab.id ? T.ink : T.sepia,
                background: "transparent",
                border: "none",
                borderBottom: activeTab === tab.id ? `2px solid ${T.clay}` : "2px solid transparent",
                cursor: "pointer",
                transition: "all 0.15s",
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Scrollable Content Body */}
        <div
          style={{
            padding: "24px 28px",
            overflowY: "auto",
            flex: 1,
            fontFamily: T.garamond,
            color: T.ink,
          }}
        >
          {/* TAB 1: OVERVIEW */}
          {activeTab === "overview" && (
            <div>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr 1fr",
                  gap: 16,
                  marginBottom: 24,
                }}
              >
                <div
                  style={{
                    padding: 18,
                    background: T.creamDark,
                    border: `1px solid ${T.ruleMid}`,
                  }}
                >
                  <div style={{ fontSize: 11, fontStyle: "italic", color: T.clay }}>
                    Target & Problem Type
                  </div>
                  <div style={{ fontFamily: T.playfair, fontSize: 18, fontWeight: 700, marginTop: 4 }}>
                    {plan?.target_column ? `Column: ${plan.target_column}` : "Unsupervised / Exploratory"}
                  </div>
                  <div style={{ fontSize: 13, color: T.sepia, textTransform: "capitalize", marginTop: 2 }}>
                    Type: {plan?.problem_type || "N/A"}
                  </div>
                </div>

                <div
                  style={{
                    padding: 18,
                    background: T.creamDark,
                    border: `1px solid ${T.ruleMid}`,
                  }}
                >
                  <div style={{ fontSize: 11, fontStyle: "italic", color: T.clay }}>
                    Critic Quality Gate
                  </div>
                  <div
                    style={{
                      fontFamily: T.playfair,
                      fontSize: 18,
                      fontWeight: 700,
                      marginTop: 4,
                      color: isSatisfactory ? "#2D6A4F" : "#A8422B",
                    }}
                  >
                    {isSatisfactory ? "Gate Passed" : "Action Required"}
                  </div>
                  <div style={{ fontSize: 13, color: T.sepia, marginTop: 2 }}>
                    Readiness Score: <strong>{scorePct}%</strong>
                  </div>
                </div>

                <div
                  style={{
                    padding: 18,
                    background: T.creamDark,
                    border: `1px solid ${T.ruleMid}`,
                  }}
                >
                  <div style={{ fontSize: 11, fontStyle: "italic", color: T.clay }}>
                    Evaluated Models
                  </div>
                  <div style={{ fontFamily: T.playfair, fontSize: 18, fontWeight: 700, marginTop: 4 }}>
                    {models?.length || 0} Models Tested
                  </div>
                  <div style={{ fontSize: 13, color: T.sepia, marginTop: 2 }}>
                    Metric: {plan?.primary_metric || "accuracy/rmse"}
                  </div>
                </div>
              </div>

              {/* Critic Verdict Banner */}
              <div
                style={{
                  padding: 18,
                  border: `1.5px solid ${isSatisfactory ? "#2D6A4F" : T.clay}`,
                  background: isSatisfactory ? "rgba(45,106,79,0.06)" : "rgba(167,122,101,0.08)",
                  marginBottom: 24,
                }}
              >
                <div style={{ fontFamily: T.playfair, fontSize: 16, fontWeight: 600, marginBottom: 6 }}>
                  Critic Agent Quality Gate Assessment
                </div>
                {critic?.issues?.length > 0 ? (
                  <div style={{ marginBottom: 10 }}>
                    <strong style={{ color: "#A8422B", fontSize: 13 }}>Identified Concerns:</strong>
                    <ul style={{ margin: "4px 0 0 16px", padding: 0 }}>
                      {critic.issues.map((iss, i) => (
                        <li key={i} style={{ fontSize: 14, color: T.ink }}>{iss}</li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <p style={{ margin: "0 0 10px 0", fontSize: 14, color: "#2D6A4F" }}>
                    &check; All model evidence and validation constraints satisfy the acceptance threshold.
                  </p>
                )}

                {critic?.recommendations?.length > 0 && (
                  <div>
                    <strong style={{ color: T.sepia, fontSize: 13 }}>Declarative Next Steps:</strong>
                    <ul style={{ margin: "4px 0 0 16px", padding: 0 }}>
                      {critic.recommendations.map((rec, i) => (
                        <li key={i} style={{ fontSize: 14, color: T.ink }}>{rec}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {/* Pipeline sequence visual */}
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontFamily: T.playfair, fontSize: 16, fontWeight: 600, marginBottom: 10 }}>
                  Autonomous Execution Trace
                </div>
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                  {plan?.steps?.map((st, i) => (
                    <div
                      key={i}
                      style={{
                        padding: "6px 12px",
                        background: T.creamDark,
                        border: `1px solid ${T.rule}`,
                        fontSize: 12,
                        fontFamily: T.inter,
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                      }}
                    >
                      <span style={{ color: T.clay, fontWeight: 600 }}>{i + 1}.</span>
                      <span style={{ textTransform: "capitalize" }}>{st.replace(/_/g, " ")}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: PROFILE */}
          {activeTab === "profile" && (
            <div>
              <div style={{ display: "flex", gap: 24, marginBottom: 20 }}>
                <div><strong>Total Rows:</strong> {dataset_summary?.rows}</div>
                <div><strong>Columns:</strong> {dataset_summary?.columns_count}</div>
                <div><strong>Duplicate Rows:</strong> {dataset_summary?.duplicate_rows}</div>
                {dataset_summary?.class_imbalance_ratio !== null && (
                  <div><strong>Imbalance Ratio:</strong> {dataset_summary?.class_imbalance_ratio}</div>
                )}
              </div>

              {dataset_summary?.warnings?.length > 0 && (
                <div
                  style={{
                    padding: 12,
                    background: "rgba(168,66,43,0.06)",
                    border: `1px solid rgba(168,66,43,0.3)`,
                    marginBottom: 16,
                  }}
                >
                  <strong style={{ color: "#A8422B" }}>Profiler Warnings:</strong>
                  <ul style={{ margin: "4px 0 0 16px" }}>
                    {dataset_summary.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div style={{ fontFamily: T.playfair, fontSize: 16, fontWeight: 600, marginBottom: 8 }}>
                Column Profiles
              </div>
              <div style={{ overflowX: "auto", marginBottom: 24 }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, fontFamily: T.inter }}>
                  <thead>
                    <tr style={{ background: T.creamDark, borderBottom: `1.5px solid ${T.rule}` }}>
                      <th style={{ padding: "8px 12px", textAlign: "left" }}>Column</th>
                      <th style={{ padding: "8px 12px", textAlign: "left" }}>Type</th>
                      <th style={{ padding: "8px 12px", textAlign: "right" }}>Unique Values</th>
                      <th style={{ padding: "8px 12px", textAlign: "right" }}>Missing Count</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dataset_summary?.columns?.map((c, i) => (
                      <tr key={i} style={{ borderBottom: `1px solid ${T.ruleMid}` }}>
                        <td style={{ padding: "8px 12px", fontWeight: 500 }}>{c.name}</td>
                        <td style={{ padding: "8px 12px", color: T.sepia, textTransform: "capitalize" }}>{c.kind}</td>
                        <td style={{ padding: "8px 12px", textAlign: "right" }}>{c.unique_count}</td>
                        <td style={{ padding: "8px 12px", textAlign: "right", color: c.missing_count > 0 ? "#A8422B" : "inherit" }}>
                          {c.missing_count}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {dataset_summary?.preview?.length > 0 && (
                <div>
                  <div style={{ fontFamily: T.playfair, fontSize: 16, fontWeight: 600, marginBottom: 8 }}>
                    Dataset Sample Preview
                  </div>
                  <div style={{ overflowX: "auto" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, fontFamily: T.inter }}>
                      <thead>
                        <tr style={{ background: T.creamDark, borderBottom: `1px solid ${T.rule}` }}>
                          {Object.keys(dataset_summary.preview[0]).map((k) => (
                            <th key={k} style={{ padding: "6px 10px", textAlign: "left" }}>{k}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {dataset_summary.preview.map((row, i) => (
                          <tr key={i} style={{ borderBottom: `1px solid ${T.ruleMid}` }}>
                            {Object.values(row).map((v, j) => (
                              <td key={j} style={{ padding: "6px 10px", color: T.sepia }}>{String(v)}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: PLAN */}
          {activeTab === "plan" && (
            <div>
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 12, fontStyle: "italic", color: T.clay }}>Dataset Question</div>
                <div style={{ fontFamily: T.playfair, fontSize: 20, fontWeight: 700, margin: "4px 0 12px" }}>
                  {plan?.goal}
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                  <div><strong>Analysis Mode:</strong> {plan?.problem_type && plan.problem_type !== "unknown" ? plan.problem_type : "Exploratory / question answering"}</div>
                  {plan?.problem_type && plan.problem_type !== "unknown" && <div><strong>Validation Strategy:</strong> {plan?.validation_strategy}</div>}
                  {plan?.problem_type && plan.problem_type !== "unknown" && <div><strong>Primary Metric:</strong> {plan?.primary_metric || "N/A"}</div>}
                  {plan?.target_column && <div><strong>Model Target:</strong> {plan.target_column}</div>}
                </div>
              </div>

              {plan?.assumptions?.length > 0 && (
                <div style={{ marginBottom: 20 }}>
                  <div style={{ fontFamily: T.playfair, fontSize: 16, fontWeight: 600, marginBottom: 6 }}>
                    Planner Assumptions
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 20 }}>
                    {plan.assumptions.map((asm, i) => (
                      <li key={i} style={{ fontSize: 14, marginBottom: 4 }}>{asm}</li>
                    ))}
                  </ul>
                </div>
              )}

              {plan?.warnings?.length > 0 && (
                <div style={{ marginBottom: 20 }}>
                  <div style={{ fontFamily: T.playfair, fontSize: 16, fontWeight: 600, color: "#A8422B", marginBottom: 6 }}>
                    Planner Warnings
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 20 }}>
                    {plan.warnings.map((w, i) => (
                      <li key={i} style={{ fontSize: 14, marginBottom: 4 }}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div>
                <div style={{ fontFamily: T.playfair, fontSize: 16, fontWeight: 600, marginBottom: 6 }}>
                  Recommended Model Families
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {plan?.recommended_models?.map((m, i) => (
                    <span
                      key={i}
                      style={{
                        padding: "4px 10px",
                        background: T.creamDark,
                        border: `1px solid ${T.rule}`,
                        fontFamily: T.inter,
                        fontSize: 12,
                        textTransform: "capitalize",
                      }}
                    >
                      {m.replace(/_/g, " ")}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: SECURITY GUARDIAN */}
          {activeTab === "security" && (
            <div>
              <StatusPanel
                title="Pre-execution Security Guardian"
                tone={securityResult?.allowed ? "safe" : "danger"}
                value={securityResult?.allowed ? "Execution Allowed" : "Execution Blocked"}
                subtitle={`Risk level: ${(securityResult?.risk_level || "unknown").toUpperCase()} · Guardrail runs before model execution.`}
              />
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
                <InfoCard title="Decision" value={securityResult?.decision || "N/A"} />
                <InfoCard title="Validated Target" value={securityResult?.validated_target || plan?.target_column || "None"} />
              </div>
              {securityResult?.violations?.length > 0 && (
                <ListBlock title="Blocked / Suspicious Conditions" items={securityResult.violations} danger />
              )}
              {securityResult?.warnings?.length > 0 && (
                <ListBlock title="Security Warnings" items={securityResult.warnings} />
              )}
              {securityResult?.checked_steps?.length > 0 && (
                <div style={{ marginTop: 18 }}>
                  <SectionTitle>Allowlisted Execution Steps</SectionTitle>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                    {securityResult.checked_steps.map((step, i) => <Pill key={i}>{step.replace(/_/g, " ")}</Pill>)}
                  </div>
                </div>
              )}
              {status === "blocked" && (
                <div style={{ marginTop: 20, padding: 14, border: "1px solid #A8422B", background: "rgba(168,66,43,0.06)" }}>
                  <strong style={{ color: "#A8422B" }}>Pipeline stopped at {blocked_at || "security_guardian"}.</strong>
                  <div style={{ marginTop: 4, fontSize: 13 }}>No model execution should occur after a security block.</div>
                </div>
              )}
            </div>
          )}

          {/* TAB 5: EDA */}
          {activeTab === "eda" && (
            <div>
              <SectionTitle>Exploratory Data Analysis Agent</SectionTitle>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 20 }}>
                <MetricCard label="Rows" value={eda?.shape?.rows ?? dataset_summary?.rows ?? "—"} />
                <MetricCard label="Columns" value={eda?.shape?.columns ?? dataset_summary?.columns_count ?? "—"} />
                <MetricCard label="Numeric" value={eda?.numeric_columns?.length ?? 0} />
                <MetricCard label="Categorical" value={eda?.categorical_columns?.length ?? 0} />
              </div>
              {eda?.missing_values && <JsonTable title="Missing Values" data={eda.missing_values} />}
              {eda?.target_distribution && <MiniBars title="Target Distribution" values={eda.target_distribution} />}
              {eda?.histograms && <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 10 }}>{Object.entries(eda.histograms).slice(0, 8).map(([name, histogram]) => <HistogramCard key={name} title={name} histogram={histogram} />)}</div>}
              {eda?.correlations && <JsonTable title="Strong Correlations" data={eda.correlations} />}
              {eda?.outliers && <JsonTable title="IQR Outlier Summary" data={eda.outliers} />}
              {eda?.categorical_top_values && <JsonTable title="Categorical Top Values" data={eda.categorical_top_values} />}
            </div>
          )}

          {/* TAB 6: STATISTICAL ANALYSIS */}
          {activeTab === "statistics" && (
            <div>
              <SectionTitle>Statistical Analysis Agent</SectionTitle>
              <StatusPanel title={data.statistics?.status === "success" ? "Statistical analysis completed" : "Statistics unavailable"} value={`${Object.keys(data.statistics?.descriptive || {}).length} numeric variables`} subtitle="Descriptive statistics and assumption-aware two-group tests. P-values are evidence of association, not causation." tone="safe" />
              {data.statistics?.descriptive && <JsonTable title="Descriptive Statistics (mean, std, quantiles, variance, skewness, kurtosis)" data={data.statistics.descriptive} />}
              {data.statistics?.correlation && <JsonTable title="Pearson Correlation Matrix" data={data.statistics.correlation} />}
              <JsonArrayBlock title="Inferential Tests" items={data.statistics?.tests || []} />
              <JsonArrayBlock title="Statistical Notes" items={data.statistics?.notes || []} />
            </div>
          )}

          {/* TAB 6: PREPROCESSING */}
          {activeTab === "preprocessing" && (
            <div>
              <SectionTitle>Preprocessing Agent Strategy</SectionTitle>
              {!preprocessing || Object.keys(preprocessing).length === 0 ? (
                <div style={{ padding: 16, background: T.creamDark, border: `1px solid ${T.rule}` }}>
                  <div style={{ fontFamily: T.playfair, fontSize: 18, fontWeight: 600 }}>No preprocessing strategy returned.</div>
                  <div style={{ marginTop: 6, fontSize: 13, color: T.sepia }}>The analysis may have been blocked before specialist agents ran.</div>
                </div>
              ) : (
                <>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))", gap: 10, marginBottom: 18 }}>
                    <InfoCard title="Target" value={preprocessing.target_column || "None"} />
                    <InfoCard title="Numeric" value={preprocessing.numeric_columns?.length ?? 0} />
                    <InfoCard title="Categorical" value={preprocessing.categorical_columns?.length ?? 0} />
                    <InfoCard title="Datetime" value={preprocessing.datetime_columns?.length ?? 0} />
                  </div>
                  <JsonArrayBlock title="Recommended Operations" items={preprocessing.strategies} />
                  {preprocessing.execution && typeof preprocessing.execution === "object" && (
                    <div style={{ marginTop: 14, padding: 14, background: T.creamDark, border: `1px solid ${T.rule}` }}>
                      <div style={{ fontFamily: T.playfair, fontSize: 18, fontWeight: 600, marginBottom: 10 }}>Actual preprocessing executed</div>
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))", gap: 10 }}>
                        <InfoCard title="Transformer" value={preprocessing.execution.transformer || "—"} />
                        <InfoCard title="Fit rows" value={preprocessing.execution.fit_rows ?? "—"} />
                        <InfoCard title="Validation rows" value={preprocessing.execution.validation_rows ?? "—"} />
                        <InfoCard title="Features after transform" value={preprocessing.execution.transformed_feature_count ?? "—"} />
                      </div>
                      <div style={{ marginTop: 10, fontSize: 12, color: T.sepia }}>
                        Fitted on: <strong>{preprocessing.execution.fit_scope || "training data only"}</strong>
                      </div>
                      {preprocessing.execution.transformed_features_preview?.length > 0 && (
                        <JsonArrayBlock title="Transformed Feature Names" items={preprocessing.execution.transformed_features_preview} />
                      )}
                    </div>
                  )}
                  <JsonArrayBlock title="Leakage Protection" items={preprocessing.notes} />
                  <div style={{ marginTop: 12, padding: 12, background: T.creamDark, border: `1px solid ${T.rule}` }}>
                    <strong style={{ fontFamily: T.inter, fontSize: 13 }}>Leakage protection: </strong>
                    <span style={{ fontSize: 13 }}>{preprocessing.data_leakage_protection ? "Enabled" : "Not enabled"}</span>
                  </div>
                </>
              )}
            </div>
          )}

          {/* TAB 7: MODELS */}
          {activeTab === "models" && (
            <div>
              {models?.length === 0 ? (
                <p style={{ fontStyle: "italic", color: T.sepia }}>
                  No predictive models were trained (exploratory or profiling plan).
                </p>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                  {models.map((m, i) => (
                    <div
                      key={i}
                      style={{
                        padding: 16,
                        border: `1px solid ${T.rule}`,
                        background: T.creamDark,
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          marginBottom: 10,
                        }}
                      >
                        <div
                          style={{
                            fontFamily: T.playfair,
                            fontSize: 16,
                            fontWeight: 600,
                            textTransform: "capitalize",
                          }}
                        >
                          {m.model_name.replace(/_/g, " ")}
                        </div>
                        <div style={{ fontSize: 12, fontFamily: T.inter, color: T.sepia }}>
                          Train Score: <strong>{m.train_score}</strong> &middot; Val Score:{" "}
                          <strong>{m.validation_score}</strong>
                        </div>
                      </div>

                      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                        {Object.entries(m.metrics).map(([k, v]) => (
                          <div
                            key={k}
                            style={{
                              padding: "4px 8px",
                              background: T.cream,
                              border: `1px solid ${T.ruleMid}`,
                              fontSize: 12,
                              fontFamily: T.inter,
                            }}
                          >
                            <span style={{ color: T.clay, textTransform: "uppercase" }}>{k}: </span>
                            <strong>{typeof v === "object" ? JSON.stringify(v) : String(v)}</strong>
                          </div>
                        ))}
                      </div>

                      {m.train_score && m.validation_score && (m.train_score - m.validation_score >= 0.15) && (
                        <div style={{ marginTop: 8, fontSize: 12, color: "#A8422B", fontStyle: "italic" }}>
                          &bull; Potential overfitting: training performance exceeds validation performance by {Math.round((m.train_score - m.validation_score) * 100)}%.
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 8: EXPLAINABILITY */}
          {activeTab === "explainability" && (
            <div>
              <SectionTitle>Explainability Agent</SectionTitle>
              {!explainability || Object.keys(explainability).length === 0 ? (
                <div style={{ padding: 16, background: T.creamDark, border: `1px solid ${T.rule}` }}>
                  <div style={{ fontFamily: T.playfair, fontSize: 18, fontWeight: 600 }}>No explainability result returned.</div>
                  <div style={{ marginTop: 6, fontSize: 13, color: T.sepia }}>
                    This happens when no predictive model was trained, for example when the planner selects an exploratory/profile-only analysis.
                  </div>
                </div>
              ) : (
                <div style={{ padding: 16, background: T.creamDark, border: `1px solid ${T.rule}` }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 14, flexWrap: "wrap" }}>
                    <div>
                      <div style={{ fontSize: 12, color: T.sepia, marginBottom: 4 }}>Best model</div>
                      <div style={{ fontFamily: T.playfair, fontSize: 20, fontWeight: 600, textTransform: "capitalize" }}>
                        {(explainability.best_model || "Unknown").replace(/_/g, " ")}
                      </div>
                    </div>
                    <Pill>{explainability.method || "model explanation"}</Pill>
                  </div>
                  <div style={{ fontSize: 13, color: T.sepia, marginBottom: 14 }}>
                    Estimator: <strong>{explainability.model_type || "Unknown"}</strong>
                  </div>
                  {Object.keys(explainability.feature_importance || {}).length > 0 ? (
                    <>
                      <div style={{ fontSize: 11, color: T.sepia, marginBottom: 8 }}>Mean absolute SHAP contribution magnitude · top features</div>
                      <ContributionBars values={explainability.feature_importance} />
                    </>
                  ) : (
                    <div style={{ fontSize: 13, color: T.sepia }}>No native feature-level importance is available for this model.</div>
                  )}
                  {explainability.warnings?.length > 0 && <ListBlock title="Explanation Warnings" items={explainability.warnings} />}
                </div>
              )}
            </div>
          )}

          {/* TAB 9: CRITIC */}
          {activeTab === "critic" && (
            <div>
              {execution_errors?.length > 0 && <ListBlock title="Execution Errors Captured" items={execution_errors.map((e) => typeof e === "string" ? e : `${e.model || e.stage || "execution"}: ${e.error || JSON.stringify(e)}`)} danger />}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 20,
                  marginBottom: 20,
                  padding: 16,
                  background: T.creamDark,
                  border: `1px solid ${T.rule}`,
                }}
              >
                <div
                  style={{
                    width: 72,
                    height: 72,
                    borderRadius: "50%",
                    border: `3px solid ${isSatisfactory ? "#2D6A4F" : T.clay}`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontFamily: T.playfair,
                    fontSize: 22,
                    fontWeight: 700,
                    color: isSatisfactory ? "#2D6A4F" : T.clay,
                  }}
                >
                  {scorePct}%
                </div>
                <div>
                  <div style={{ fontFamily: T.playfair, fontSize: 18, fontWeight: 600 }}>
                    {isSatisfactory ? "Satisfactory Quality Threshold Met" : "Autonomous Quality Gate Intercepted Issues"}
                  </div>
                  <div style={{ fontSize: 13, color: T.sepia, marginTop: 4 }}>
                    Evaluated by CriticAgent rule-based quality gate.
                  </div>
                </div>
              </div>

              {critic?.issues?.length > 0 && (
                <div style={{ marginBottom: 20 }}>
                  <div style={{ fontFamily: T.playfair, fontSize: 16, fontWeight: 600, color: "#A8422B", marginBottom: 6 }}>
                    Identified Issues
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 20 }}>
                    {critic.issues.map((iss, i) => (
                      <li key={i} style={{ fontSize: 14, marginBottom: 4 }}>{iss}</li>
                    ))}
                  </ul>
                </div>
              )}

              {critic?.recommendations?.length > 0 && (
                <div style={{ marginBottom: 20 }}>
                  <div style={{ fontFamily: T.playfair, fontSize: 16, fontWeight: 600, color: T.ink, marginBottom: 6 }}>
                    Critic Recommendations
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 20 }}>
                    {critic.recommendations.map((rec, i) => (
                      <li key={i} style={{ fontSize: 14, marginBottom: 4 }}>{rec}</li>
                    ))}
                  </ul>
                </div>
              )}

              {critic?.next_plan_overrides && Object.keys(critic.next_plan_overrides).length > 0 && (
                <div>
                  <div style={{ fontFamily: T.playfair, fontSize: 16, fontWeight: 600, marginBottom: 6 }}>
                    Declarative Next-Iteration Overrides
                  </div>
                  <pre
                    style={{
                      background: T.creamDark,
                      padding: 12,
                      fontSize: 12,
                      border: `1px solid ${T.ruleMid}`,
                      fontFamily: "monospace",
                      overflowX: "auto",
                    }}
                  >
                    {JSON.stringify(critic.next_plan_overrides, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* TAB 10: REPLANNING */}
          {activeTab === "replanning" && (
            <div>
              <SectionTitle>Bounded Autonomous Replanning</SectionTitle>
              <StatusPanel
                title={replanning?.history?.some((item) => item.attempted) ? "A retry was attempted" : "No retry required or possible"}
                value={`${replanning?.history?.filter((item) => item.attempted).length || 0} / ${replanning?.max_retries || 1} retries used`}
                subtitle="The Replanner uses Critic feedback, selects only untried allowlisted models, and re-runs the Security Guardian before retrying."
                tone="safe"
              />
              <JsonArrayBlock title="Replanning decisions" items={replanning?.history || []} />
              <ListBlock title="Models attempted" items={replanning?.attempted_models || []} />
              <div style={{ fontSize: 12, color: T.sepia }}>Retry policy is deliberately bounded to one retry to prevent unbounded loops and runaway compute.</div>
            </div>
          )}

          {/* TAB 11: RESEARCH */}
          {activeTab === "research" && (
            <div>
              <SectionTitle>Research & Methodology Agent</SectionTitle>
              <StatusPanel
                title={research?.external_sources_used ? "External literature records retrieved" : research?.retrieval_mode === "local_rag" ? "Indexed local evidence retrieved" : "Offline methodology guidance"}
                value={research?.external_sources_used ? `${[...new Set((research?.sources || []).map((source) => source.provider).filter(Boolean))].join(" + ")} records attached` : research?.retrieval_mode === "local_rag" ? "User-indexed documents attached" : "No external papers were verified for this run"}
                subtitle={research?.disclaimer || "Guidance derived from profiler and model diagnostics."}
                tone="safe"
              />
              {research?.research_query && <div style={{ fontSize: 11, color: T.sepia, marginBottom: 10 }}>Search query: {research.research_query}</div>}
              <SectionTitle>Retrieved research papers and records</SectionTitle>
              <ResearchSourceCards sources={research?.sources || []} />
              <SectionTitle>Methodology guidance (separate from retrieved papers)</SectionTitle>
              <ResearchFindingCards findings={research?.findings || []} />
              {research?.error_type && <div style={{ fontSize: 11, color: "#A8422B", marginTop: 8 }}>External research lookup was unavailable ({research.error_type}); offline guidance is kept separate.</div>}
            </div>
          )}

          {/* TAB 12: REPORT */}
          {activeTab === "report" && (
            <div>
              <SectionTitle>Generated Analysis Report</SectionTitle>
              {data.artifact?.status === "saved" && <div style={{ fontSize: 12, color: T.sepia, marginBottom: 10 }}>Model artifact saved: {data.artifact.artifact_id}</div>}
              {data.cross_validation?.performed && <div style={{ fontSize: 12, color: T.sepia, marginBottom: 10 }}>Cross-validation: {data.cross_validation.summary}</div>}
              <div style={{ fontSize: 12, color: T.sepia, marginBottom: 12 }}>Experiment ID: {experiment_id || "Not persisted"} · Report narrative: {visibleReport?.llm?.status || "unknown"} · Model: {visibleReport?.llm?.model || "deterministic fallback"}</div>
              {visibleReport?.markdown ? (
                <>
                  {experiment_id && <button disabled={reportBusy} onClick={handleRegenerateReport} style={{ padding: "9px 14px", background: T.clay, color: "white", border: "none", cursor: reportBusy ? "wait" : "pointer", margin: "0 8px 14px 0" }}>{reportBusy ? "Regenerating…" : "Regenerate with configured LLM"}</button>}
                  {reportError && <div style={{ color: "#A8422B", fontSize: 12, marginBottom: 10 }}>{reportError}</div>}
                  <button onClick={() => { const blob = new Blob([visibleReport.markdown], { type: "text/markdown;charset=utf-8" }); const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = "datapilot-analysis-report.md"; a.click(); URL.revokeObjectURL(url); }} style={{ padding: "9px 14px", background: T.ink, color: T.cream, border: "none", cursor: "pointer", marginBottom: 14 }}>Export Markdown Report</button>
                  {experiment_id && <a href={`/api/history/${encodeURIComponent(experiment_id)}/report.pdf`} target="_blank" rel="noreferrer" style={{ display: "inline-block", padding: "9px 14px", background: T.clay, color: "white", textDecoration: "none", margin: "0 0 14px 8px", fontSize: 12 }}>Export PDF Report</a>}
                  {visibleReport.question_answer && (
                    <div style={{ display: "flex", flexDirection: "column", gap: 10, padding: 18, marginBottom: 16, background: "#20392D", color: "#FDFBF7", borderRadius: 10 }}>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
                        <div>
                          <div style={{ fontSize: 11, letterSpacing: 1, color: "#CFE77B", textTransform: "uppercase" }}>Direct answer · computed from uploaded data</div>
                          <div style={{ fontFamily: T.playfair, fontSize: 18, marginTop: 5 }}>
                            {visibleReport.question_answer.answer_type === "scalar_metric"
                              ? `${visibleReport.question_answer.operation?.toUpperCase()} ${visibleReport.question_answer.target_column}: ${Number(visibleReport.question_answer.answer_value).toLocaleString()}`
                              : `${visibleReport.question_answer.category} · ${Number(visibleReport.question_answer.count || 0).toLocaleString()} of ${Number(visibleReport.question_answer.total || 0).toLocaleString()}`}
                          </div>
                          {visibleReport.question_answer.summary && <div style={{ fontSize: 12, opacity: 0.9, marginTop: 4 }}>{visibleReport.question_answer.summary}</div>}
                          <div style={{ fontSize: 11, opacity: 0.8, marginTop: 4 }}>
                            Column: {visibleReport.question_answer.target_column || "dataset"}
                            {visibleReport.question_answer.filters_applied?.length > 0 && ` · Filters: ${visibleReport.question_answer.filters_applied.map((f) => `${f.column} ${f.op} ${f.value}`).join(", ")}`}
                          </div>
                        </div>
                        <div style={{ fontFamily: T.playfair, fontSize: 34, fontWeight: 700, color: "#CFE77B", whiteSpace: "nowrap" }}>
                          {visibleReport.question_answer.answer_type === "scalar_metric"
                            ? Number(visibleReport.question_answer.answer_value).toLocaleString()
                            : `${Number(visibleReport.question_answer.percentage || 0).toFixed(2)}%`}
                        </div>
                      </div>
                    </div>
                  )}
                  {(visibleReport.charts || []).map((chart) => <ReportChart key={chart.id || chart.title} chart={chart} />)}
                  <MarkdownReport markdown={visibleReport.markdown} />
                </>
              ) : <div>No report was generated for this run.</div>}
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: "14px 28px",
            borderTop: `1px solid ${T.rule}`,
            background: T.creamDark,
            display: "flex",
            justifyContent: "flex-end",
            gap: 12,
          }}
        >
          <button
            onClick={onClose}
            style={{
              padding: "8px 22px",
              background: T.ink,
              color: T.cream,
              border: "none",
              cursor: "pointer",
              fontFamily: T.inter,
              fontSize: 13,
              fontWeight: 500,
            }}
          >
            Close Audit View
          </button>
        </div>
      </div>
    </div>
  );
}
