import { useEffect, useMemo, useState } from "react";
import DataPilot from "./DataPilot";
import "./App.css";

const NAV = [
  ["Overview", "◫"], ["Workspace", "⌘"], ["Datasets", "▤"], ["Experiments", "◷"],
  ["Agent graph", "◇"], ["Integrations", "⌘"], ["Settings", "⚙"],
];
const API = "/api";
async function get(path) { const r = await fetch(`${API}${path}`); if (!r.ok) throw new Error(`Request failed (${r.status})`); return r.json(); }

function Stat({ label, value, hint }) { return <div className="stat-card"><span>{label}</span><strong>{value}</strong><small>{hint}</small></div>; }
function Panel({ title, action, children }) { return <section className="panel"><div className="panel-head"><h3>{title}</h3>{action}</div>{children}</section>; }

export default function App() {
  const [page, setPage] = useState("Overview");
  const [health, setHealth] = useState(null);
  const [samples, setSamples] = useState([]);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");
  const [selectedTrace, setSelectedTrace] = useState(null);

  async function refresh() {
    try {
      const [h, s, e] = await Promise.all([get("/health"), get("/samples"), get("/history")]);
      setHealth(h); setSamples(s); setHistory(e.items || []); setError("");
    } catch (e) { setError(e.message); }
  }
  useEffect(() => { refresh(); }, []);
  useEffect(() => {
    if (page !== "Experiments") return undefined;
    const timer = window.setInterval(() => {
      get("/history").then((data) => setHistory(data.items || [])).catch(() => {});
    }, 5000);
    return () => window.clearInterval(timer);
  }, [page]);
  const capabilities = health?.orchestration || {};
  const completed = history.filter((x) => x.status === "success").length;
  const activePage = useMemo(() => page, [page]);

  async function loadTrace(id) {
    try { setSelectedTrace(await get(`/history/${encodeURIComponent(id)}/agents`)); } catch (e) { setError(e.message); }
  }


  if (page === "Workspace") return <div className="workspace-shell"><div className="workspace-top"><button onClick={() => setPage("Overview")}>← Back to Data Pilot</button><span>ANALYSIS WORKSPACE</span></div><DataPilot /></div>;

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><img src="/data-pilot-logo.svg" alt="Data Pilot logo" /></div><div><b>data pilot</b><small>Autonomous data science</small></div></div>
      <div className="side-label">WORKSPACE</div>
      <nav>{NAV.map(([label, icon]) => <button key={label} className={page === label ? "nav-item active" : "nav-item"} onClick={() => setPage(label)}><span>{icon}</span>{label}</button>)}</nav>
      <div className="sidebar-bottom"><div className="health-dot"/><span>{health?.status === "healthy" ? "Backend connected" : "Backend unavailable"}</span><small>v4.5.0</small></div>
    </aside>
    <main className="main-area">
      <header className="topbar"><div><span className="eyebrow">AUTONOMOUS ANALYTICS PLATFORM</span><h1>{activePage}</h1></div><div className="top-actions"><span className="connection"><b/> {health?.status === "healthy" ? "System operational" : "Connecting"}</span><button className="primary-btn" onClick={() => setPage("Workspace")}>＋ New analysis</button></div></header>
      {error && <div className="notice error">{error}</div>}
      {page === "Overview" && <>
        <div className="welcome"><div><span className="eyebrow light">YOUR DATA SCIENCE COMMAND CENTRE</span><h2>From raw data to<br/><em>defensible decisions.</em></h2><p>Plan, execute, evaluate and explain machine-learning workflows through a coordinated agent system.</p><button className="light-btn" onClick={() => setPage("Workspace")}>Start an analysis <span>↗</span></button></div><div className="welcome-art"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="orbit-core"><img src="/data-pilot-logo.svg" alt="" /></div><span className="orbit-node node-a">ML</span><span className="orbit-node node-b">AI</span><span className="orbit-node node-c">R</span></div></div>
        <div className="stats-grid"><Stat label="EXPERIMENTS" value={history.length} hint="Saved analysis runs"/><Stat label="SUCCESSFUL RUNS" value={completed} hint="Completed without errors"/><Stat label="SAMPLE DATASETS" value={samples.length} hint="Ready to explore"/></div>
        <div className="content-grid"><Panel title="Recent experiments" action={<button className="text-btn" onClick={() => setPage("Experiments")}>View all →</button>}>{history.length ? <div className="table-wrap"><table><thead><tr><th>DATASET</th><th>STATUS</th><th>CREATED</th></tr></thead><tbody>{history.slice(0,5).map(x => <tr key={x.id}><td><b>{x.dataset_name}</b><small className="sub-id">{x.id.slice(0,8)}</small></td><td><span className={`status-pill ${x.status}`}>{x.status}</span></td><td>{new Date(x.created_at).toLocaleString()}</td></tr>)}</tbody></table></div> : <div className="empty-state">No experiments yet. Start your first analysis.</div>}</Panel>
          <Panel title="System capabilities"><div className="cap-list"><div><span>LangGraph orchestration</span><b className={capabilities.available ? "yes" : "no"}>{capabilities.available ? "Ready" : "Unavailable"}</b></div><div><span>Research retrieval</span><b className="yes">{health?.research_rag?.retriever || "Local retrieval"}</b></div><div><span>Deep learning</span><b>{health?.deep_learning?.enabled ? "Enabled" : "Optional"}</b></div><div><span>Data engine</span><b>{health?.data_engine?.configured || "auto"}</b></div></div><button className="text-btn" onClick={() => setPage("Integrations")}>Integration details →</button></Panel></div>
      </>}
      {page === "Datasets" && <><p className="page-intro">Explore the bundled datasets or open the workspace to upload your own CSV, Excel or JSON file.</p><div className="dataset-grid">{samples.map(s => <article className="dataset-card" key={s.id}><div className="dataset-icon">▤</div><span className="eyebrow">{s.problem_type?.toUpperCase() || "TABULAR DATA"}</span><h3>{s.title}</h3><p>{s.description}</p><div className="dataset-meta"><span>Target: <b>{s.target_column || "Auto-detect"}</b></span><button onClick={() => setPage("Workspace")}>Analyze →</button></div></article>)}</div></>}
      {page === "Experiments" && <><Panel title="Experiment history" action={<button className="text-btn" onClick={refresh}>Refresh ↻</button>}>{history.length ? <div className="table-wrap"><table><thead><tr><th>DATASET</th><th>STATUS</th><th>PROGRESS</th><th>CREATED</th><th>ID</th><th>TRACE</th></tr></thead><tbody>{history.map(x => <tr key={x.id}><td><b>{x.dataset_name}</b></td><td><span className={`status-pill ${x.status}`}>{x.status}</span></td><td>{x.is_job ? <div className="history-progress"><div><span>{x.progress_percent || 0}%</span><small>{x.current_stage || "Queued"}</small></div><div className="progress-track"><div className="progress-fill" style={{width:`${x.progress_percent || 0}%`}}/></div></div> : <span className="muted">—</span>}</td><td>{new Date(x.created_at).toLocaleString()}</td><td className="mono">{x.id.slice(0,12)}</td><td>{x.is_job ? <span className="muted">{x.error_code ? `Error: ${x.error_code}` : `${x.completed_steps || 0}/${x.total_steps || 11} stages`}</span> : <button className="text-btn" onClick={() => loadTrace(x.id)}>View agents →</button>}</td></tr>)}</tbody></table></div> : <div className="empty-state">Your saved experiments will appear here.</div>}</Panel>{selectedTrace && <Panel title="Saved agent execution trace"><div className="trace-list">{(selectedTrace.agents || []).map((a,i)=><div className="trace-row" key={`${a.agent}-${i}`}><span className={`trace-dot ${a.status}`}/><b>{a.agent}</b><span>{a.detail}</span><small>{a.status}</small></div>)}</div><small className="muted">Orchestrator: {selectedTrace.orchestration?.framework || "legacy"}</small></Panel>}</>}
      {page === "Agent graph" && <><p className="page-intro">LangGraph controls the analysis lifecycle. Specialist agents remain deterministic Python components, with LLM assistance reserved for selected reasoning and narrative tasks.</p><div className="graph-board"><div className="graph-node root"><b>Input & validation</b><small>Dataset + objective</small></div><div className="graph-connector"/><div className="graph-node planner"><b>Planner Agent</b><small>Structured workflow plan</small></div><div className="graph-connector"/><div className="graph-node security"><b>Security Guardian</b><small>Pre-execution policy gate</small></div><div className="graph-connector"/><div className="graph-split"><div className="graph-node"><b>Data Agent</b><small>Profiling · EDA · statistics</small></div><div className="graph-node"><b>ML Agent</b><small>Preprocessing · training · CV</small></div></div><div className="graph-connector"/><div className="graph-node critic"><b>Critic + Replanner</b><small>Quality evaluation · bounded retry</small></div><div className="graph-connector"/><div className="graph-split"><div className="graph-node"><b>Explainability</b><small>SHAP · feature importance</small></div><div className="graph-node"><b>Research RAG</b><small>Evidence retrieval · citations</small></div></div><div className="graph-connector"/><div className="graph-node finish"><b>Reporting Agent</b><small>Verified metrics · Markdown · PDF</small></div></div><div className="graph-footnote">Execution detail is attached to each saved experiment. This diagram describes the current workflow; specialist agents are coordinated components, not necessarily separate LLMs.</div></>}
      {page === "Integrations" && <><p className="page-intro">Optional capabilities are isolated so the core application remains usable without external credentials or GPU hardware.</p><div className="integration-grid">{[["LangGraph","StateGraph orchestration, conditional routing and per-invocation checkpoints",capabilities.available],["MCP server","External tool access over stdio; run backend/mcp_server.py",true],["DuckDB","Adaptive SQL engine for larger in-memory tabular workloads",health?.data_engine?.duckdb_available],["PyTorch","Optional MLP classifier and regressor; CPU supported",health?.integrations?.torch_available ? (health?.deep_learning?.enabled ? true : null) : false],["MLflow","Experiment metrics and metadata artifact tracking",health?.integrations?.mlflow_available ? null : false],["MCP server","Allowlisted tools over stdio transport",health?.integrations?.mcp_available],["PDF extraction","Text extraction from uploaded research PDFs",health?.integrations?.pymupdf_available],["Semantic embeddings","Optional Sentence Transformers retrieval",health?.integrations?.sentence_transformers_available],["Research RAG","Local TF-IDF retrieval over indexed text with source excerpts",true]].map(([n,d,v])=><article className="integration-card" key={n}><div className="integration-status">{v===true?"AVAILABLE":v===false?"NOT INSTALLED":"OPTIONAL"}</div><h3>{n}</h3><p>{d}</p></article>)}</div><Panel title="MCP tools"><p className="muted">The MCP server exposes allowlisted sample listing, profiling, EDA, full sample analysis, research retrieval, report retrieval, security self-test and capability discovery.</p><code>cd backend &amp;&amp; python mcp_server.py</code></Panel></>}
      {page === "Settings" && <><div className="settings-grid"><Panel title="Runtime configuration"><div className="cap-list"><div><span>API status</span><b>{health?.status || "Unknown"}</b></div><div><span>API version</span><b>{health?.version || "—"}</b></div><div><span>LangGraph</span><b>{capabilities.available ? "Installed" : "Missing dependency"}</b></div><div><span>LLM provider</span><b>{health?.reporting?.llm_configured ? `${health.reporting.provider} · ${health.reporting.model}` : "Deterministic fallback"}</b></div></div></Panel><Panel title="Optional feature flags"><p className="muted">Configure these in <code>backend/.env</code>, then restart the backend.</p><pre>DATAPILOT_DATA_ENGINE=auto{"\n"}DATAPILOT_DUCKDB_THRESHOLD_MB=100{"\n"}DATAPILOT_ENABLE_DEEP_LEARNING=false{"\n"}DATAPILOT_ENABLE_MLFLOW=false{"\n"}DATAPILOT_ENABLE_LIVE_RESEARCH=false</pre></Panel></div></>}
      <footer className="footer"><span>DATA PILOT · V4.5</span><span>Evidence-first autonomous data science</span></footer>
    </main>
  </div>;
}
