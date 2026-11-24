import { useEffect, useRef, useState } from "react";
import AnalyticsStudio from "./AnalyticsStudio";
import DataPilot from "./DataPilot";
import { fetchExperiment } from "./api";
import "./App.css";

const NAV = [
  ["Overview", "◫"],
  ["Analytics Studio", "✦"],
  ["Workspace", "⌘"],
  ["Datasets", "▤"],
  ["Experiments", "◷"],
  ["Agent graph", "◇"],
  ["Integrations", "⊞"],
  ["Settings", "⚙"],
];

const API = "/api";

async function get(path) {
  const r = await fetch(`${API}${path}`);
  if (!r.ok) throw new Error(`Request failed (${r.status})`);
  return r.json();
}

function Stat({ label, value, hint }) {
  return (
    <div className="stat-card">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{hint}</small>
    </div>
  );
}

function Panel({ title, action, children }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h3>{title}</h3>
        {action}
      </div>
      {children}
    </section>
  );
}

export default function App() {
  const quickFileInputRef = useRef(null);
  const [page, setPage] = useState("Overview");
  const [health, setHealth] = useState(null);
  const [samples, setSamples] = useState([]);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");
  const [selectedTrace, setSelectedTrace] = useState(null);
  const [workspaceSampleId, setWorkspaceSampleId] = useState(null);
  const [workspaceFile, setWorkspaceFile] = useState(null);
  const [workspaceResult, setWorkspaceResult] = useState(null);
  const [draggingQuickDrop, setDraggingQuickDrop] = useState(false);

  async function refresh() {
    try {
      const [h, s, e] = await Promise.all([get("/health"), get("/samples"), get("/history")]);
      setHealth(h);
      setSamples(s);
      setHistory(e.items || []);
      setError("");
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (page !== "Experiments") return undefined;
    const timer = window.setInterval(() => {
      get("/history")
        .then((data) => setHistory(data.items || []))
        .catch(() => {});
    }, 5000);
    return () => window.clearInterval(timer);
  }, [page]);

  const capabilities = health?.orchestration || {};
  const completed = history.filter((x) => x.status === "success").length;
  const healthy = health?.status === "healthy";

  async function loadTrace(id) {
    try {
      setSelectedTrace(await get(`/history/${encodeURIComponent(id)}/agents`));
    } catch (e) {
      setError(e.message);
    }
  }

  async function openExperimentReport(id) {
    try {
      const exp = await fetchExperiment(id);
      setWorkspaceResult(exp);
      setPage("Analytics Studio");
    } catch (e) {
      setError(e.message);
    }
  }

  function launchSampleInWorkspace(sampleId) {
    setWorkspaceResult(null);
    setWorkspaceFile(null);
    setWorkspaceSampleId(sampleId);
    setPage("Analytics Studio");
  }

  function launchFileInWorkspace(file) {
    if (!file) return;
    setWorkspaceResult(null);
    setWorkspaceSampleId(null);
    setWorkspaceFile(file);
    setPage("Analytics Studio");
  }

  if (page === "Workspace") {
    return (
      <div className="workspace-shell">
        <div className="workspace-top">
          <button type="button" onClick={() => setPage("Overview")}>
            ← Back to Data Pilot
          </button>
          <span>ANALYSIS WORKSPACE</span>
        </div>
        <DataPilot />
      </div>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <img src="/data-pilot-logo.svg" alt="Data Pilot logo" />
          </div>
          <div>
            <b>Data Pilot</b>
            <small>Autonomous data science</small>
          </div>
        </div>
        <div className="side-label">Navigation</div>
        <nav aria-label="Primary sections">
          {NAV.map(([label, icon]) => (
            <button
              key={label}
              type="button"
              className={page === label ? "nav-item active" : "nav-item"}
              onClick={() => setPage(label)}
            >
              <span>{icon}</span>
              {label}
            </button>
          ))}
        </nav>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div>
            <span className="eyebrow">Data Pilot Workbench</span>
            <h1>{page}</h1>
          </div>
          <div className="top-actions">
            <button
              type="button"
              className="primary-btn"
              onClick={() => {
                setWorkspaceResult(null);
                setPage("Analytics Studio");
              }}
            >
              ＋ New analysis
            </button>
          </div>
        </header>

        {error && <div className="notice error">{error}</div>}

        {page === "Overview" && (
          <>
            <section className="overview-strip">
              <div>
                <span className="eyebrow">Quick start</span>
                <h2>Analyze tabular data or train guarded baselines</h2>
                <p>
                  Profile schemas, ask natural-language questions, run leakage-safe models, and export verified Markdown or PDF reports.
                </p>
                <div className="overview-actions">
                  <button
                    type="button"
                    className="primary-btn"
                    onClick={() => {
                      setWorkspaceResult(null);
                      setPage("Analytics Studio");
                    }}
                  >
                    Open Analytics Studio →
                  </button>
                  <button type="button" className="secondary-btn" onClick={() => setPage("Datasets")}>
                    Browse sample datasets
                  </button>
                </div>
              </div>

              <div
                className={`quick-drop ${draggingQuickDrop ? "dragging" : ""}`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDraggingQuickDrop(true);
                }}
                onDragLeave={() => setDraggingQuickDrop(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDraggingQuickDrop(false);
                  launchFileInWorkspace(e.dataTransfer?.files?.[0]);
                }}
                onClick={() => quickFileInputRef.current?.click()}
                role="button"
                tabIndex={0}
                aria-label="Quick upload CSV, Excel, or JSON dataset"
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    quickFileInputRef.current?.click();
                  }
                }}
              >
                <input
                  ref={quickFileInputRef}
                  type="file"
                  accept=".csv,.xlsx,.xls,.json"
                  style={{ display: "none" }}
                  onChange={(e) => launchFileInWorkspace(e.target.files?.[0])}
                />
                <div>
                  <strong>Quick-drop dataset</strong>
                  <small>Drop CSV, XLSX, XLS, or JSON to open Analytics Studio with instant profiling</small>
                </div>
                <span className="secondary-btn">↑ Browse</span>
              </div>
            </section>

            <div className="stats-grid">
              <Stat label="Experiments" value={history.length} hint="Saved & active analysis runs" />
              <Stat label="Successful runs" value={completed} hint="Completed without errors" />
              <Stat label="Sample datasets" value={samples.length} hint="Ready for exploration" />
            </div>

            <div className="content-grid">
              <Panel
                title="Recent experiments"
                action={
                  <button type="button" className="text-btn" onClick={() => setPage("Experiments")}>
                    View all →
                  </button>
                }
              >
                {history.length ? (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Dataset</th>
                          <th>Status</th>
                          <th className="num">Created</th>
                          <th className="num">Report</th>
                        </tr>
                      </thead>
                      <tbody>
                        {history.slice(0, 6).map((x) => (
                          <tr key={x.id}>
                            <td>
                              <b>{x.dataset_name}</b>
                              <span className="sub-id">{x.id.slice(0, 8)}</span>
                            </td>
                            <td>
                              <span className={`status-pill ${x.status}`}>{x.status}</span>
                            </td>
                            <td className="num">{new Date(x.created_at).toLocaleString()}</td>
                            <td className="num">
                              {!x.is_job ? (
                                <button type="button" className="text-btn" onClick={() => openExperimentReport(x.id)}>
                                  Open →
                                </button>
                              ) : (
                                <span className="muted">{x.progress_percent || 0}%</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="empty-state">No experiments yet. Start your first analysis in Analytics Studio.</div>
                )}
              </Panel>

              <Panel
                title="System capabilities"
                action={
                  <button type="button" className="text-btn" onClick={() => setPage("Integrations")}>
                    Details →
                  </button>
                }
              >
                <div className="cap-list">
                  <div>
                    <span>LangGraph orchestration</span>
                    <b className={capabilities.available ? "yes" : "no"}>
                      {capabilities.available ? "Ready" : "Python fallback"}
                    </b>
                  </div>
                  <div>
                    <span>LLM narrative</span>
                    <b className={health?.reporting?.llm_configured ? "yes" : ""}>
                      {health?.reporting?.llm_configured
                        ? `${health.reporting.provider} · ${health.reporting.model}`
                        : "Deterministic fallback"}
                    </b>
                  </div>
                  <div>
                    <span>Research retrieval</span>
                    <b className="yes">{health?.research_rag?.retriever || "Local retrieval"}</b>
                  </div>
                  <div>
                    <span>Deep learning</span>
                    <b>{health?.deep_learning?.enabled ? "Enabled" : "Optional"}</b>
                  </div>
                  <div>
                    <span>Data engine</span>
                    <b>{health?.data_engine?.configured || "auto"}</b>
                  </div>
                </div>
              </Panel>
            </div>
          </>
        )}

        {page === "Analytics Studio" && (
          <AnalyticsStudio
            samples={samples}
            initialSampleId={workspaceSampleId}
            initialFile={workspaceFile}
            selectedResult={workspaceResult}
            onConsumeInitial={() => {
              setWorkspaceSampleId(null);
              setWorkspaceFile(null);
            }}
            onClearSelectedResult={() => setWorkspaceResult(null)}
            onHistoryUpdated={() =>
              get("/history")
                .then((data) => setHistory(data.items || []))
                .catch(() => {})
            }
          />
        )}

        {page === "Datasets" && (
          <>
            <p className="page-intro">
              Select any bundled dataset to pre-load it in Analytics Studio with instant schema profiling, or upload your own CSV, Excel, or JSON file.
            </p>
            <div className="dataset-grid">
              {samples.map((s) => (
                <article className="dataset-card" key={s.id}>
                  <div className="dataset-icon">▤</div>
                  <span className="eyebrow">{s.problem_type || "Tabular data"}</span>
                  <h3>{s.title}</h3>
                  <p>{s.description}</p>
                  <div className="dataset-meta">
                    <span>
                      Target: <b>{s.target_column || "Auto-detect"}</b>
                      {s.rows ? ` · ${s.rows.toLocaleString()} rows` : ""}
                    </span>
                    <button type="button" className="text-btn" onClick={() => launchSampleInWorkspace(s.id)}>
                      Analyze →
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </>
        )}

        {page === "Experiments" && (
          <>
            <Panel
              title="Experiment history"
              action={
                <button type="button" className="text-btn" onClick={refresh}>
                  Refresh ↻
                </button>
              }
            >
              {history.length ? (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Dataset</th>
                        <th>Status</th>
                        <th>Progress</th>
                        <th className="num">Created</th>
                        <th className="num">ID</th>
                        <th className="num">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {history.map((x) => (
                        <tr key={x.id}>
                          <td><b>{x.dataset_name}</b></td>
                          <td><span className={`status-pill ${x.status}`}>{x.status}</span></td>
                          <td>
                            {x.is_job ? (
                              <div className="history-progress">
                                <div>
                                  <span>{x.progress_percent || 0}%</span>
                                  <small>{x.current_stage || "Queued"}</small>
                                </div>
                                <div className="progress-track">
                                  <div className="progress-fill" style={{ width: `${x.progress_percent || 0}%` }} />
                                </div>
                              </div>
                            ) : (
                              <span className="muted">Complete</span>
                            )}
                          </td>
                          <td className="num">{new Date(x.created_at).toLocaleString()}</td>
                          <td className="num mono">{x.id.slice(0, 8)}</td>
                          <td className="num">
                            {x.is_job ? (
                              <span className="muted">
                                {x.error_code
                                  ? `Error: ${x.error_code}`
                                  : `${x.completed_steps || 0}/${x.total_steps || 11} stages`}
                              </span>
                            ) : (
                              <div style={{ display: "inline-flex", gap: 6 }}>
                                <button type="button" className="text-btn" onClick={() => openExperimentReport(x.id)}>
                                  Report →
                                </button>
                                <button type="button" className="text-btn" onClick={() => loadTrace(x.id)}>
                                  Trace
                                </button>
                              </div>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="empty-state">Your saved experiments will appear here.</div>
              )}
            </Panel>

            {selectedTrace && (
              <Panel
                title="Saved agent execution trace"
                action={
                  <button type="button" className="text-btn" onClick={() => setSelectedTrace(null)}>
                    Close ×
                  </button>
                }
              >
                <div className="trace-list">
                  {(selectedTrace.agents || []).map((a, i) => (
                    <div className="trace-row" key={`${a.agent}-${i}`}>
                      <b>{a.agent}</b>
                      <span>{a.detail}</span>
                      <span className={`status-pill ${a.status}`}>{a.status}</span>
                    </div>
                  ))}
                </div>
                <small className="muted">Orchestrator: {selectedTrace.orchestration?.framework || "legacy"}</small>
              </Panel>
            )}
          </>
        )}

        {page === "Agent graph" && (
          <>
            <p className="page-intro">
              LangGraph controls the analysis lifecycle. Specialist agents remain deterministic Python components, with LLM assistance reserved for intent routing and report narrative synthesis.
            </p>
            <div className="graph-board">
              <div className="graph-node root"><b>Input & validation</b><small>Dataset + objective</small></div>
              <div className="graph-connector" />
              <div className="graph-node planner"><b>Planner Agent</b><small>Structured workflow plan</small></div>
              <div className="graph-connector" />
              <div className="graph-node security"><b>Security Guardian</b><small>Pre-execution policy gate</small></div>
              <div className="graph-connector" />
              <div className="graph-split">
                <div className="graph-node"><b>Data Agent</b><small>Profiling · EDA · statistics</small></div>
                <div className="graph-node"><b>ML Agent</b><small>Preprocessing · training · CV</small></div>
              </div>
              <div className="graph-connector" />
              <div className="graph-node critic"><b>Critic + Replanner</b><small>Quality evaluation · bounded retry</small></div>
              <div className="graph-connector" />
              <div className="graph-split">
                <div className="graph-node"><b>Explainability</b><small>SHAP · feature importance</small></div>
                <div className="graph-node"><b>Research RAG</b><small>Evidence retrieval · citations</small></div>
              </div>
              <div className="graph-connector" />
              <div className="graph-node finish"><b>Reporting Agent</b><small>Verified metrics · Markdown · PDF</small></div>
            </div>
            <div className="graph-footnote">
              Execution detail is attached to each saved experiment and inspectable from the Experiments tab.
            </div>
          </>
        )}

        {page === "Integrations" && (
          <>
            <p className="page-intro">
              Optional capabilities are isolated so the core application remains usable without external credentials or GPU hardware.
            </p>
            <div className="integration-grid">
              {[
                ["LangGraph", "StateGraph orchestration, conditional routing and per-invocation checkpoints", capabilities.available],
                ["MCP server", "Allowlisted tools over stdio transport; run backend/mcp_server.py", health?.integrations?.mcp_available],
                ["DuckDB", "Adaptive SQL engine for larger in-memory tabular workloads", health?.data_engine?.duckdb_available],
                ["PyTorch", "Optional MLP classifier and regressor; CPU supported", health?.integrations?.torch_available ? (health?.deep_learning?.enabled ? true : null) : false],
                ["MLflow", "Experiment metrics and metadata artifact tracking", health?.integrations?.mlflow_available ? null : false],
                ["PDF extraction", "Text extraction from uploaded research PDFs", health?.integrations?.pymupdf_available],
                ["Semantic embeddings", "Optional Sentence Transformers retrieval", health?.integrations?.sentence_transformers_available],
                ["Research RAG", "Local TF-IDF retrieval over indexed text with source excerpts", true],
              ].map(([name, desc, available]) => (
                <article className="integration-card" key={name}>
                  <div className="integration-status">
                    {available === true ? "Available" : available === false ? "Not installed" : "Optional"}
                  </div>
                  <h3>{name}</h3>
                  <p>{desc}</p>
                </article>
              ))}
            </div>
            <div style={{ marginTop: 18 }}>
              <Panel title="MCP stdio server">
                <p className="muted" style={{ marginTop: 0 }}>
                  The MCP server exposes allowlisted sample listing, profiling, EDA, full sample analysis, research retrieval, report retrieval, security self-test, and capability discovery.
                </p>
                <code>cd backend &amp;&amp; python mcp_server.py</code>
              </Panel>
            </div>
          </>
        )}

        {page === "Settings" && (
          <div className="settings-grid">
            <Panel title="Runtime configuration">
              <div className="cap-list">
                <div><span>API status</span><b>{health?.status || "Unknown"}</b></div>
                <div><span>API version</span><b>{health?.version || "—"}</b></div>
                <div><span>LangGraph</span><b>{capabilities.available ? "Installed" : "Missing dependency"}</b></div>
                <div>
                  <span>LLM provider</span>
                  <b>
                    {health?.reporting?.llm_configured
                      ? `${health.reporting.provider} · ${health.reporting.model}`
                      : "Deterministic fallback"}
                  </b>
                </div>
              </div>
            </Panel>
            <Panel title="Optional feature flags">
              <p className="muted" style={{ marginTop: 0 }}>
                Configure these in <code>backend/.env</code>, then restart the backend server.
              </p>
              <pre>
                {`DATAPILOT_DATA_ENGINE=auto\nDATAPILOT_DUCKDB_THRESHOLD_MB=100\nDATAPILOT_ENABLE_DEEP_LEARNING=false\nDATAPILOT_ENABLE_MLFLOW=false\nDATAPILOT_ENABLE_LIVE_RESEARCH=true`}
              </pre>
            </Panel>
          </div>
        )}

        <footer className="footer">
          <span>DATA PILOT · V{health?.version || "4.5.0"}</span>
          <span>Evidence-first autonomous data science</span>
        </footer>
      </main>
    </div>
  );
}
