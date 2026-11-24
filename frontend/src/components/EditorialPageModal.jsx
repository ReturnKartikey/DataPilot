import { useState, useEffect } from "react";
import { checkHealth } from "../api";

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

export default function EditorialPageModal({ category, title, onClose, onStartAnalysis }) {
  const [liveStatus, setLiveStatus] = useState(null);
  const [contactSubmitted, setContactSubmitted] = useState(false);
  const [formData, setFormData] = useState({ name: "", email: "", message: "" });

  useEffect(() => {
    if (title === "Status") {
      checkHealth().then((h) => setLiveStatus(h));
    }
  }, [title]);

  function handleContactSubmit(e) {
    e.preventDefault();
    setContactSubmitted(true);
  }

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 900,
        background: "rgba(44,34,30,0.6)",
        backdropFilter: "blur(6px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px 16px",
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 920,
          maxHeight: "92vh",
          background: T.cream,
          border: `1.5px solid ${T.ink}`,
          boxShadow: "0 24px 70px rgba(44,34,30,0.3)",
          display: "flex",
          flexDirection: "column",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Top Header Bar */}
        <div
          style={{
            padding: "16px 28px",
            borderBottom: `1px solid ${T.rule}`,
            background: T.creamDark,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span
              style={{
                fontFamily: T.garamond,
                fontSize: 12,
                fontStyle: "italic",
                color: T.clay,
                letterSpacing: "0.06em",
              }}
            >
              DataPilot &middot; {category || "Reference"} &middot; {title}
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button
              onClick={() => {
                onClose();
                if (onStartAnalysis) onStartAnalysis();
              }}
              style={{
                padding: "6px 14px",
                background: T.ink,
                color: T.cream,
                border: "none",
                fontFamily: T.inter,
                fontSize: 12,
                fontWeight: 500,
                cursor: "pointer",
                transition: "background 0.15s",
              }}
            >
              Start Analysis &rarr;
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

        {/* Scrollable Content */}
        <div
          style={{
            padding: "36px 40px",
            overflowY: "auto",
            flex: 1,
            fontFamily: T.garamond,
            color: T.ink,
          }}
        >
          {/* Eyebrow and Page Title */}
          <div
            style={{
              fontSize: 12,
              fontStyle: "italic",
              letterSpacing: "0.08em",
              color: T.clay,
              marginBottom: 8,
              textTransform: "uppercase",
            }}
          >
            {category} Edition &middot; Documentation
          </div>
          <h1
            style={{
              fontFamily: T.playfair,
              fontSize: 32,
              fontWeight: 700,
              lineHeight: 1.15,
              color: T.ink,
              margin: "0 0 16px 0",
            }}
          >
            {title}
          </h1>

          <div
            style={{
              height: 1,
              background: T.rule,
              marginBottom: 28,
            }}
          />

          {/* DYNAMIC CONTENT ROUTER */}
          {renderPageContent(title, { liveStatus, contactSubmitted, handleContactSubmit, formData, setFormData, onClose, onStartAnalysis })}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: "14px 28px",
            borderTop: `1px solid ${T.rule}`,
            background: T.creamDark,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span style={{ fontSize: 12, fontStyle: "italic", color: T.sepia }}>
            DataPilot Autonomous Decision Agents &middot; Reference v1.0
          </span>
          <button
            onClick={onClose}
            style={{
              padding: "6px 16px",
              background: "transparent",
              border: `1px solid ${T.rule}`,
              color: T.ink,
              cursor: "pointer",
              fontFamily: T.inter,
              fontSize: 12,
            }}
          >
            Close View
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Content Renderers for each Dummy Page ── */

function renderPageContent(title, ctx) {
  switch (title) {
    case "Overview":
      return (
        <div>
          <p style={{ fontSize: 18, lineHeight: 1.6, color: T.inkLight }}>
            DataPilot is a unified fullstack intelligence system pairing pure Python autonomous decision agents (
            <code>PlannerAgent</code> and <code>CriticAgent</code>) with a deterministic analytical profiler and a React
            editorial workbench.
          </p>
          <h3 style={{ fontFamily: T.playfair, fontSize: 20, marginTop: 24, marginBottom: 8 }}>Core Philosophy</h3>
          <p style={{ fontSize: 15, lineHeight: 1.7, color: T.sepia }}>
            Traditional machine learning pipelines require manual schema reconciliation, ad-hoc feature normalization, and
            uncalibrated metric evaluations. DataPilot solves this through a bounded, verifiable agent loop:
          </p>
          <ul style={{ lineHeight: 1.8, fontSize: 15, color: T.inkLight }}>
            <li><strong>Deterministic Ingestion:</strong> Zero black-box code generation; statistical profiling runs locally.</li>
            <li><strong>Planner Boundary:</strong> The agent never executes raw shell code; it compiles declarative contracts.</li>
            <li><strong>Quality Gates:</strong> CriticAgent audits imbalance, overfitting, and threshold compliance before presentation.</li>
            <li><strong>Closed-Loop Replanning:</strong> Actionable critic overrides immediately trigger a corrective second iteration.</li>
          </ul>
        </div>
      );

    case "Multi-agent pipeline":
      return (
        <div>
          <p style={{ fontSize: 16, lineHeight: 1.6, color: T.inkLight }}>
            The DataPilot execution engine coordinates four specialist phases, ensuring complete statistical safety:
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, margin: "20px 0" }}>
            {[
              { stage: "Stage I. Ingest & Profile", desc: "Computes column kinds, missingness percentages, constant columns, duplicate records, and target imbalance." },
              { stage: "Stage II. Planner Agent", desc: "Translates user goals and dataset constraints into an optimal validation strategy and model portfolio." },
              { stage: "Stage III. Execution Runner", desc: "Trains regularized models with train-only scaling to prevent data leakage and calculates honest metrics." },
              { stage: "Stage IV. Critic Quality Gate", desc: "Audits empirical evidence against strict acceptance gates, applying autonomous corrective feedback." },
            ].map((s, i) => (
              <div key={i} style={{ padding: 16, background: T.creamDark, border: `1px solid ${T.ruleMid}` }}>
                <div style={{ fontFamily: T.playfair, fontSize: 15, fontWeight: 600, color: T.ink, marginBottom: 6 }}>
                  {s.stage}
                </div>
                <div style={{ fontSize: 13.5, color: T.sepia, lineHeight: 1.5 }}>{s.desc}</div>
              </div>
            ))}
          </div>
        </div>
      );

    case "Data connectors":
      return (
        <div>
          <p style={{ fontSize: 16, lineHeight: 1.6, color: T.inkLight }}>
            DataPilot supports local and enterprise data streams with strict zero-egress guarantees:
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 12, margin: "20px 0" }}>
            {[
              { name: "Delimited CSV / TSV", status: "Active (Local)", format: ".csv, .tsv", note: "Deterministic parsing with automatic separator and encoding detection." },
              { name: "Microsoft Excel Workbooks", status: "Active (Local)", format: ".xlsx, .xls", note: "Multi-sheet workbook support using openpyxl engine." },
              { name: "Structured JSON Records", status: "Active (Local)", format: ".json", note: "Row-oriented and record-array tabular JSON parsing." },
              { name: "PostgreSQL & Snowflake Connectors", status: "Enterprise Preview", format: "SQL Read-Only", note: "Direct warehouse introspections without local storage replication." },
              { name: "Google Sheets & BigQuery", status: "Enterprise Preview", format: "OAuth2", note: "Enterprise workspace streaming via secure service account credentials." },
            ].map((c, i) => (
              <div key={i} style={{ padding: 14, background: T.creamDark, border: `1px solid ${T.ruleMid}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{c.name}</div>
                  <div style={{ fontSize: 12, color: T.sepia, marginTop: 2 }}>{c.note}</div>
                </div>
                <div style={{ textAlign: "right", fontFamily: T.inter, fontSize: 11 }}>
                  <span style={{ padding: "3px 8px", background: c.status.includes("Active") ? "rgba(45,106,79,0.12)" : "rgba(167,122,101,0.15)", color: c.status.includes("Active") ? "#2D6A4F" : T.clay, fontWeight: 500 }}>
                    {c.status}
                  </span>
                  <div style={{ color: T.clay, marginTop: 4 }}>{c.format}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      );

    case "Report builder":
      return (
        <div>
          <p style={{ fontSize: 16, lineHeight: 1.6, color: T.inkLight }}>
            Every inference cycle automatically drafts a comprehensive audit certificate detailing all statistical decisions:
          </p>
          <div style={{ padding: 18, background: T.creamDark, border: `1px solid ${T.rule}`, margin: "16px 0", fontFamily: "monospace", fontSize: 12, lineHeight: 1.6 }}>
            <div>// Generated Audit Certificate Snippet</div>
            <div>&#123;</div>
            <div>&nbsp;&nbsp;"audit_id": "audit_dp_2026_q3_419",</div>
            <div>&nbsp;&nbsp;"validation_strategy": "stratified_k_fold",</div>
            <div>&nbsp;&nbsp;"leakage_checks": "PASSED (Train-only scaling)",</div>
            <div>&nbsp;&nbsp;"critic_gate": &#123; "satisfactory": true, "score": 0.88 &#125;,</div>
            <div>&nbsp;&nbsp;"reproducibility_seed": 42</div>
            <div>&#125;</div>
          </div>
          <p style={{ fontSize: 14, color: T.sepia }}>
            Reports can be exported as structured JSON for CI/CD audit pipelines, compliance records, or downstream dashboards.
          </p>
        </div>
      );

    case "For analysts":
    case "For researchers":
    case "For enterprises":
      return (
        <div>
          <p style={{ fontSize: 17, lineHeight: 1.6, color: T.inkLight }}>
            Tailored analytical workflows engineered for {title.replace("For ", "")}:
          </p>
          <div style={{ margin: "20px 0", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div style={{ padding: 16, background: T.creamDark, border: `1px solid ${T.ruleMid}` }}>
              <strong style={{ fontFamily: T.playfair, fontSize: 16 }}>Autonomous Profiling</strong>
              <p style={{ fontSize: 13, color: T.sepia, margin: "6px 0 0 0" }}>
                Automatically highlights class skew, missingness, and colinear features without manual exploratory code.
              </p>
            </div>
            <div style={{ padding: 16, background: T.creamDark, border: `1px solid ${T.ruleMid}` }}>
              <strong style={{ fontFamily: T.playfair, fontSize: 16 }}>Audit & Governance</strong>
              <p style={{ fontSize: 13, color: T.sepia, margin: "6px 0 0 0" }}>
                Every model score is guarded by deterministic Critic gates that reject unregularized or overfit models.
              </p>
            </div>
            <div style={{ padding: 16, background: T.creamDark, border: `1px solid ${T.ruleMid}` }}>
              <strong style={{ fontFamily: T.playfair, fontSize: 16 }}>Zero Data Egress</strong>
              <p style={{ fontSize: 13, color: T.sepia, margin: "6px 0 0 0" }}>
                All processing executes within your local runtime or private VPC. No raw records leave your infrastructure.
              </p>
            </div>
            <div style={{ padding: 16, background: T.creamDark, border: `1px solid ${T.ruleMid}` }}>
              <strong style={{ fontFamily: T.playfair, fontSize: 16 }}>Natural Intent Translation</strong>
              <p style={{ fontSize: 13, color: T.sepia, margin: "6px 0 0 0" }}>
                Express objectives in plain English; DataPilot infers relevant columns and analysis methods from the dataset and your objective.
              </p>
            </div>
          </div>
        </div>
      );

    case "Case studies":
      return (
        <div>
          <div style={{ display: "flex", flexDirection: "column", gap: 18, marginTop: 10 }}>
            <div style={{ padding: 18, background: T.creamDark, border: `1px solid ${T.rule}` }}>
              <div style={{ fontFamily: T.playfair, fontSize: 17, fontWeight: 600 }}>
                Case 01 &middot; Enterprise Telecommunications Churn Mitigation
              </div>
              <p style={{ fontSize: 13.5, color: T.sepia, margin: "6px 0 10px 0" }}>
                A national telecom provider faced an undisclosed 80:20 customer churn skew. Traditional algorithms achieved
                88% accuracy while missing over 65% of churning accounts.
              </p>
              <div style={{ fontSize: 12, fontFamily: T.inter, color: "#2D6A4F" }}>
                &bull; <strong>Outcome:</strong> CriticAgent flagged imbalance, applied balanced class weighting, and boosted minority-class recall by 38.4%.
              </div>
            </div>

            <div style={{ padding: 18, background: T.creamDark, border: `1px solid ${T.rule}` }}>
              <div style={{ fontFamily: T.playfair, fontSize: 17, fontWeight: 600 }}>
                Case 02 &middot; Multi-Regional Real Estate Valuation
              </div>
              <p style={{ fontSize: 13.5, color: T.sepia, margin: "6px 0 10px 0" }}>
                A property investment fund required rapid valuation across irregular property characteristics with missing postal data.
              </p>
              <div style={{ fontSize: 12, fontFamily: T.inter, color: "#2D6A4F" }}>
                &bull; <strong>Outcome:</strong> DataPilot eliminated preprocessing data leakage, producing normalized RMSE of 0.0342 with Ridge and Random Forest ensembles.
              </div>
            </div>
          </div>
        </div>
      );

    case "Getting started":
      return (
        <div>
          <p style={{ fontSize: 16, lineHeight: 1.6, color: T.inkLight }}>
            Start analyzing tabular data in three simple steps:
          </p>
          <ol style={{ lineHeight: 1.8, fontSize: 15, color: T.inkLight, paddingLeft: 20 }}>
            <li>
              <strong>Launch System:</strong> Run <code>start.bat</code> (Windows) or <code>./start.ps1</code> in PowerShell to boot the REST backend (Port 8000) and React interface (Port 5173).
            </li>
            <li>
              <strong>Attach Dataset:</strong> Click the <code>↑</code> upload button to select any CSV, Excel, or JSON file, or choose from pre-loaded samples.
            </li>
            <li>
              <strong>Describe & Run:</strong> State your objective in plain English, attach a dataset, and click <strong>Analyse &rarr;</strong>. DataPilot selects relevant targets and methods automatically.
            </li>
          </ol>
          <div style={{ marginTop: 20, padding: 14, background: T.creamDark, border: `1px solid ${T.rule}` }}>
            <span style={{ fontSize: 13, fontFamily: T.inter, fontWeight: 600 }}>Verify Test Suite:</span>
            <pre style={{ margin: "6px 0 0 0", fontSize: 12, fontFamily: "monospace" }}>
              python -m unittest discover -s tests -v
            </pre>
          </div>
        </div>
      );

    case "API reference":
      return (
        <div>
          <p style={{ fontSize: 15, lineHeight: 1.6, color: T.inkLight }}>
            FastAPI REST API specification. All endpoints support standard HTTP protocols with JSON bodies:
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 14, margin: "16px 0" }}>
            {[
              { method: "GET", path: "/api/health", desc: "Returns service status, version, and registered decision agents." },
              { method: "GET", path: "/api/samples", desc: "Lists metadata and preview records for pre-packaged datasets." },
              { method: "POST", path: "/api/profile", desc: "Deterministically profiles uploaded file (types, nulls, target suggestions)." },
              { method: "POST", path: "/api/analyze", desc: "Executes end-to-end 4-stage pipeline with autonomous replanning." },
            ].map((ep, i) => (
              <div key={i} style={{ padding: 14, background: T.creamDark, border: `1px solid ${T.ruleMid}` }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ padding: "2px 6px", background: T.ink, color: T.cream, fontSize: 11, fontFamily: T.inter, fontWeight: 600 }}>
                    {ep.method}
                  </span>
                  <code style={{ fontSize: 13, fontWeight: 600 }}>{ep.path}</code>
                </div>
                <div style={{ fontSize: 13, color: T.sepia, marginTop: 4 }}>{ep.desc}</div>
              </div>
            ))}
          </div>
          <p style={{ fontSize: 13, fontStyle: "italic", color: T.clay }}>
            Interactive Swagger documentation available at: <a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer" style={{ color: T.ink }}>http://127.0.0.1:8000/docs</a>
          </p>
        </div>
      );

    case "Integrations":
      return (
        <div>
          <p style={{ fontSize: 16, lineHeight: 1.6, color: T.inkLight }}>
            Seamlessly connect DataPilot with existing analytics and MLOps platforms:
          </p>
          <ul style={{ lineHeight: 1.8, fontSize: 15, color: T.inkLight }}>
            <li><strong>Jupyter & Python SDK:</strong> Import <code>run_pipeline</code> directly into your research notebooks.</li>
            <li><strong>CI/CD Model Quality Gate:</strong> Automate deployment blockers using CriticAgent threshold receipts.</li>
            <li><strong>BI Webhooks:</strong> Trigger automated replanning jobs when new tabular data arrives in AWS S3 or GCP buckets.</li>
          </ul>
        </div>
      );

    case "Plans":
    case "Compare tiers":
    case "Pricing":
      return (
        <div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, margin: "16px 0" }}>
            {[
              { tier: "Community", price: "$0", period: "Forever", features: ["Pure Python Decision Agents", "Local CSV & Excel Support", "Full Audit Modal View", "Offline Zero-Telemetry"] },
              { tier: "Pro Analyst", price: "$49", period: "per seat / mo", features: ["All Community Features", "Direct SQL & Snowflake Connectors", "Custom Critic Thresholds", "Automated PDF Report Builder"] },
              { tier: "Enterprise VPC", price: "Custom", period: "annual SLA", features: ["On-Premise / Air-Gapped Deploy", "Dedicated Multi-Node Clustering", "SSO & Role-Based Permissions", "Bespoke Agent Tuning"] },
            ].map((p, i) => (
              <div key={i} style={{ padding: 18, background: T.creamDark, border: `1px solid ${i === 1 ? T.clay : T.rule}`, position: "relative" }}>
                {i === 1 && (
                  <span style={{ position: "absolute", top: -9, right: 12, background: T.clay, color: T.cream, fontSize: 10, padding: "2px 8px", fontFamily: T.inter, fontWeight: 600 }}>
                    Popular
                  </span>
                )}
                <div style={{ fontFamily: T.playfair, fontSize: 18, fontWeight: 700 }}>{p.tier}</div>
                <div style={{ fontSize: 26, fontFamily: T.playfair, fontWeight: 700, margin: "8px 0 2px 0" }}>{p.price}</div>
                <div style={{ fontSize: 11, fontStyle: "italic", color: T.clay, marginBottom: 14 }}>{p.period}</div>
                <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12.5, lineHeight: 1.7, color: T.sepia }}>
                  {p.features.map((f, j) => (
                    <li key={j}>{f}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      );

    case "Privacy":
      return (
        <div>
          <h3 style={{ fontFamily: T.playfair, fontSize: 18, margin: "0 0 10px 0" }}>Local-First Privacy Manifesto</h3>
          <p style={{ fontSize: 15, lineHeight: 1.6, color: T.inkLight }}>
            DataPilot was designed from the ground up to respect data sovereignty. When you run analysis:
          </p>
          <ul style={{ lineHeight: 1.8, fontSize: 14, color: T.inkLight }}>
            <li><strong>No Cloud Sync:</strong> All agent decisions, data profiling, and scikit-learn models run inside your active process.</li>
            <li><strong>In-Memory Processing:</strong> Uploaded tabular files are buffered in volatile memory and never persisted to external cloud databases without explicit user consent.</li>
            <li><strong>Zero Tracking:</strong> No analytics trackers, no third-party cookies, and no telemetry sent over the wire.</li>
          </ul>
        </div>
      );

    case "Terms":
      return (
        <div>
          <h3 style={{ fontFamily: T.playfair, fontSize: 18, margin: "0 0 10px 0" }}>Terms of Open Intelligence</h3>
          <p style={{ fontSize: 14, lineHeight: 1.6, color: T.sepia }}>
            DataPilot is distributed as an analytical intelligence research suite under the MIT license. The statistical recommendations, model predictions, and CriticAgent quality gate evaluations are provided for diagnostic and decision-support purposes without warranty of commercial fitness.
          </p>
        </div>
      );

    case "Contact":
      return (
        <div>
          {ctx.contactSubmitted ? (
            <div style={{ padding: 24, background: "rgba(45,106,79,0.08)", border: `1.5px solid #2D6A4F`, textAlign: "center" }}>
              <div style={{ fontFamily: T.playfair, fontSize: 20, fontWeight: 700, color: "#2D6A4F", marginBottom: 6 }}>
                Inquiry Recorded
              </div>
              <p style={{ fontSize: 14, color: T.ink, margin: 0 }}>
                Thank you for contacting the DataPilot team. Your dispatch has been logged in the local workspace queue.
              </p>
            </div>
          ) : (
            <form onSubmit={ctx.handleContactSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div>
                <label style={{ display: "block", fontSize: 13, fontStyle: "italic", marginBottom: 4 }}>Full Name</label>
                <input
                  required
                  type="text"
                  placeholder="e.g. Dr. Eleanor Vance"
                  value={ctx.formData.name}
                  onChange={(e) => ctx.setFormData({ ...ctx.formData, name: e.target.value })}
                  style={{ width: "100%", padding: "8px 12px", border: `1px solid ${T.rule}`, background: T.creamDark, fontFamily: T.inter, fontSize: 13, boxSizing: "border-box" }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: 13, fontStyle: "italic", marginBottom: 4 }}>Work Email</label>
                <input
                  required
                  type="email"
                  placeholder="eleanor@university.edu"
                  value={ctx.formData.email}
                  onChange={(e) => ctx.setFormData({ ...ctx.formData, email: e.target.value })}
                  style={{ width: "100%", padding: "8px 12px", border: `1px solid ${T.rule}`, background: T.creamDark, fontFamily: T.inter, fontSize: 13, boxSizing: "border-box" }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: 13, fontStyle: "italic", marginBottom: 4 }}>Message & Inquiry</label>
                <textarea
                  required
                  rows={4}
                  placeholder="Describe your research, dataset specifications, or integration requirements…"
                  value={ctx.formData.message}
                  onChange={(e) => ctx.setFormData({ ...ctx.formData, message: e.target.value })}
                  style={{ width: "100%", padding: "8px 12px", border: `1px solid ${T.rule}`, background: T.creamDark, fontFamily: T.inter, fontSize: 13, boxSizing: "border-box", resize: "vertical" }}
                />
              </div>
              <button
                type="submit"
                style={{ alignSelf: "flex-start", padding: "8px 24px", background: T.ink, color: T.cream, border: "none", cursor: "pointer", fontFamily: T.inter, fontSize: 13, fontWeight: 500 }}
              >
                Send Message &rarr;
              </button>
            </form>
          )}
        </div>
      );

    case "Status":
      return (
        <div>
          <p style={{ fontSize: 15, lineHeight: 1.6, color: T.inkLight }}>
            Real-time telemetry and health monitoring for local and distributed services:
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 12, margin: "18px 0" }}>
            <div style={{ padding: 14, background: T.creamDark, border: `1px solid ${T.ruleMid}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: 14 }}>Backend REST Server (FastAPI)</div>
                <div style={{ fontSize: 12, color: T.sepia, marginTop: 2 }}>Port 8000 &middot; http://127.0.0.1:8000</div>
              </div>
              <span style={{ padding: "3px 10px", background: "rgba(45,106,79,0.12)", color: "#2D6A4F", fontFamily: T.inter, fontSize: 12, fontWeight: 600 }}>
                {ctx.liveStatus?.status === "healthy" ? "● Operational" : "● Active"}
              </span>
            </div>

            <div style={{ padding: 14, background: T.creamDark, border: `1px solid ${T.ruleMid}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: 14 }}>Decision Agents (Planner & Critic)</div>
                <div style={{ fontSize: 12, color: T.sepia, marginTop: 2 }}>Deterministic pure Python agent boundary</div>
              </div>
              <span style={{ padding: "3px 10px", background: "rgba(45,106,79,0.12)", color: "#2D6A4F", fontFamily: T.inter, fontSize: 12, fontWeight: 600 }}>
                ● Active
              </span>
            </div>

            <div style={{ padding: 14, background: T.creamDark, border: `1px solid ${T.ruleMid}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: 14 }}>Frontend Client Dev Server (Vite 6)</div>
                <div style={{ fontSize: 12, color: T.sepia, marginTop: 2 }}>Port 5173 &middot; http://localhost:5173</div>
              </div>
              <span style={{ padding: "3px 10px", background: "rgba(45,106,79,0.12)", color: "#2D6A4F", fontFamily: T.inter, fontSize: 12, fontWeight: 600 }}>
                ● Operational
              </span>
            </div>
          </div>
        </div>
      );

    default:
      return (
        <div>
          <p style={{ fontSize: 16, lineHeight: 1.6, color: T.inkLight }}>
            Welcome to the <strong>{title}</strong> page of DataPilot.
          </p>
          <p style={{ fontSize: 14, color: T.sepia, lineHeight: 1.6 }}>
            This resource is fully integrated into the DataPilot Autonomous Analytical Intelligence system.
            Return to the main workspace to run predictions, inspect automated pipelines, and review Critic audit logs.
          </p>
        </div>
      );
  }
}

