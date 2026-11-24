import { useEffect, useRef, useState } from "react";
import AnalysisResultsView from "./components/AnalysisResultsView";
import StudioSelect from "./components/StudioSelect";
import {
  fetchExperiment,
  fetchHistory,
  fetchSamples,
  profileDataset,
  runAnalysis,
  runSecuritySelfTest,
} from "./api";

export default function DataPilot({
  samples: propSamples = [],
  initialSampleId = null,
  initialFile = null,
  selectedResult = null,
  onConsumeInitial,
  onClearSelectedResult,
  onHistoryUpdated,
}) {
  const fileInputRef = useRef(null);
  const [samples, setSamples] = useState(propSamples);
  const [prompt, setPrompt] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [selectedSample, setSelectedSample] = useState(null);
  const [targetColumn, setTargetColumn] = useState("");
  const [problemType, setProblemType] = useState("auto");

  const [profileData, setProfileData] = useState(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState("");
  const [dragging, setDragging] = useState(false);

  const [loading, setLoading] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [jobProgress, setJobProgress] = useState({
    percent: 0,
    stage: "Queued",
    completedSteps: 0,
    totalSteps: 11,
  });
  const [errorMessage, setErrorMessage] = useState("");
  const [analysisResult, setAnalysisResult] = useState(selectedResult);

  const [securityTest, setSecurityTest] = useState(null);
  const [securityTestLoading, setSecurityTestLoading] = useState(false);
  const [experimentHistory, setExperimentHistory] = useState([]);
  const [historyError, setHistoryError] = useState("");

  useEffect(() => {
    if (propSamples.length) {
      setSamples(propSamples);
    } else {
      fetchSamples()
        .then((data) => setSamples(data))
        .catch(() => {});
    }
  }, [propSamples]);

  useEffect(() => {
    fetchHistory()
      .then((data) => setExperimentHistory(data.items || []))
      .catch(() => {});
    const timer = window.setInterval(() => {
      fetchHistory()
        .then((data) => setExperimentHistory(data.items || []))
        .catch(() => {});
    }, 5000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (selectedResult) {
      setAnalysisResult(selectedResult);
    }
  }, [selectedResult]);

  useEffect(() => {
    if (initialFile) {
      setSelectedFile(initialFile);
      setSelectedSample(null);
      setTargetColumn("");
      setProblemType("auto");
      setAnalysisResult(null);
      setErrorMessage("");
      if (onConsumeInitial) onConsumeInitial();
    }
  }, [initialFile, onConsumeInitial]);

  useEffect(() => {
    if (!initialSampleId || !samples.length) return;
    const match = samples.find((s) => s.id === initialSampleId);
    if (match) {
      setSelectedSample(match);
      setSelectedFile(null);
      setPrompt(match.suggested_query || "");
      setTargetColumn("");
      setProblemType("auto");
      setAnalysisResult(null);
      setErrorMessage("");
      if (onConsumeInitial) onConsumeInitial();
    }
  }, [initialSampleId, samples, onConsumeInitial]);

  useEffect(() => {
    const activeSampleId = selectedSample?.id || (!selectedFile ? "churn" : null);
    if (!selectedFile && !activeSampleId) return;

    let cancelled = false;
    setProfileLoading(true);
    setProfileError("");
    profileDataset({
      file: selectedFile,
      sampleId: activeSampleId,
      targetColumn: targetColumn || undefined,
    })
      .then((res) => {
        if (!cancelled) {
          setProfileData(res);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setProfileData(null);
          setProfileError(err.message || "Could not profile dataset.");
        }
      })
      .finally(() => {
        if (!cancelled) setProfileLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedFile, selectedSample, targetColumn]);

  useEffect(() => {
    if (!loading) {
      setElapsedSeconds(0);
      return undefined;
    }
    const started = Date.now();
    const timer = window.setInterval(() => setElapsedSeconds(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [loading]);

  function handleFilePicked(file) {
    if (!file) return;
    setSelectedFile(file);
    setSelectedSample(null);
    setTargetColumn("");
    setErrorMessage("");
  }

  function handleSelectSample(sample) {
    setSelectedSample(sample);
    setSelectedFile(null);
    setPrompt(sample.suggested_query || "");
    setTargetColumn("");
    setProblemType("auto");
    setErrorMessage("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function clearSelection() {
    setSelectedFile(null);
    setSelectedSample(null);
    setTargetColumn("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function handleRun(e) {
    e.preventDefault();
    if (loading) return;
    setLoading(true);
    setJobProgress({ percent: 2, stage: "Starting analysis", completedSteps: 0, totalSteps: 11 });
    setErrorMessage("");
    try {
      const result = await runAnalysis({
        file: selectedFile,
        sampleId: selectedSample?.id || (!selectedFile ? "churn" : undefined),
        inquiry: prompt.trim() || "Explore this dataset and summarize its main patterns.",
        targetColumn: targetColumn || undefined,
        problemType,
        onProgress: setJobProgress,
      });
      setAnalysisResult(result);
      const updated = await fetchHistory().catch(() => null);
      if (updated?.items) setExperimentHistory(updated.items);
      if (onHistoryUpdated) onHistoryUpdated();
    } catch (err) {
      setErrorMessage(err.message || "Execution error encountered.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSecuritySelfTest() {
    setSecurityTestLoading(true);
    try {
      setSecurityTest(await runSecuritySelfTest());
    } catch (err) {
      setSecurityTest({ error: err.message || "Failed to run security self-test" });
    } finally {
      setSecurityTestLoading(false);
    }
  }

  async function handleOpenExperiment(id) {
    try {
      const exp = await fetchExperiment(id);
      setAnalysisResult(exp);
    } catch (err) {
      setHistoryError(err.message || "Could not load saved experiment.");
    }
  }

  if (analysisResult) {
    return (
      <AnalysisResultsView
        data={analysisResult}
        backLabel="← Back to Analytics Studio"
        onBack={() => {
          setAnalysisResult(null);
          if (onClearSelectedResult) onClearSelectedResult();
        }}
      />
    );
  }

  const profile = profileData?.profile;
  const preview = profileData?.preview || [];
  const activeDatasetLabel = selectedFile
    ? `File: ${selectedFile.name}`
    : selectedSample
      ? `Sample: ${selectedSample.title}`
      : "Default sample: Customer Churn";

  return (
    <div className="workbench-grid">
      <section className="panel">
        <div className="panel-head">
          <div>
            <h3>Run dataset analysis</h3>
            <span className="muted">Upload CSV, Excel, or JSON, inspect the schema preview, and ask a question or train models.</span>
          </div>
          <div className="selected-badge">
            <span>{activeDatasetLabel}</span>
            {(selectedFile || selectedSample) && (
              <button
                type="button"
                className="icon-btn"
                style={{ width: 22, height: 22, fontSize: 13 }}
                onClick={clearSelection}
                aria-label="Clear selected dataset"
                title="Clear dataset"
              >
                ×
              </button>
            )}
          </div>
        </div>

        <form className="workbench-form" onSubmit={handleRun}>
          <input
            id="dp-file-upload"
            type="file"
            ref={fileInputRef}
            onChange={(e) => handleFilePicked(e.target.files?.[0])}
            accept=".csv,.xlsx,.xls,.json"
            style={{ display: "none" }}
          />

          <div
            className={`quick-drop ${dragging ? "dragging" : ""}`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              handleFilePicked(e.dataTransfer?.files?.[0]);
            }}
            onClick={() => fileInputRef.current?.click()}
            role="button"
            tabIndex={0}
            aria-label="Upload CSV, Excel, or JSON dataset"
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                fileInputRef.current?.click();
              }
            }}
          >
            <div>
              <strong>{selectedFile ? selectedFile.name : "Drop a dataset here or browse files"}</strong>
              <small>Supports .csv, .xlsx, .xls, and .json (up to 25 MB)</small>
            </div>
            <button
              type="button"
              className="secondary-btn"
              disabled={loading}
              aria-label="Attach CSV, Excel, or JSON file"
              onClick={(e) => {
                e.stopPropagation();
                fileInputRef.current?.click();
              }}
            >
              ↑ Upload file
            </button>
          </div>

          {samples.length > 0 && (
            <div className="chip-row">
              <span className="muted">Or load a sample:</span>
              {samples.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className={`sample-chip ${selectedSample?.id === s.id ? "active" : ""}`}
                  onClick={() => handleSelectSample(s)}
                >
                  {s.title} ({s.problem_type})
                </button>
              ))}
            </div>
          )}

          <div className="field-group">
            <label className="field-label" htmlFor="dp-inquiry">
              Analysis question or modeling goal
            </label>
            <textarea
              id="dp-inquiry"
              className="workbench-textarea"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g. Which factors drive customer churn, or summarize regional revenue anomalies…"
              disabled={loading}
              spellCheck={false}
            />
          </div>

          <div className="workbench-controls">
            <div className="field-group">
              <label className="field-label" htmlFor="dp-target">
                Target column (optional)
              </label>
              <StudioSelect
                id="dp-target"
                value={targetColumn}
                onChange={setTargetColumn}
                disabled={loading || !profile?.columns?.length}
                options={[
                  { value: "", label: "Auto-detect from question & schema" },
                  ...(profile?.columns || []).map((col) => ({
                    value: col.name,
                    label: col.name,
                    meta: col.kind,
                    badge: profile.potential_target_columns?.includes(col.name) ? "Suggested" : undefined,
                  })),
                ]}
              />
            </div>

            <div className="field-group">
              <label className="field-label" htmlFor="dp-problem-type">
                Analysis mode
              </label>
              <StudioSelect
                id="dp-problem-type"
                value={problemType}
                onChange={setProblemType}
                disabled={loading}
                options={[
                  { value: "auto", label: "Auto", meta: "infer from question & target" },
                  { value: "unknown", label: "Exploratory", meta: "question answering" },
                  { value: "classification", label: "Classification", meta: "categorical target" },
                  { value: "regression", label: "Regression", meta: "numeric target" },
                ]}
              />
            </div>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <span className="field-hint">
              {profile
                ? `Profiled: ${profile.rows.toLocaleString()} rows × ${profile.columns.length} columns${
                    profile.duplicate_rows ? ` · ${profile.duplicate_rows} duplicates` : ""
                  }`
                : profileLoading
                  ? "Profiling dataset schema…"
                  : ""}
            </span>
            <button type="submit" className="primary-btn" disabled={loading}>
              {loading ? "Analysing…" : "Run analysis →"}
            </button>
          </div>
        </form>

        {loading && (
          <div
            className="progress-card"
            style={{ marginTop: 16 }}
            role="progressbar"
            aria-valuenow={jobProgress.percent}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-live="polite"
          >
            <div className="progress-meta">
              <strong>{jobProgress.stage}</strong>
              <span>
                {Math.floor(elapsedSeconds / 60)}m {elapsedSeconds % 60}s · {jobProgress.percent}% ({jobProgress.completedSteps}/{jobProgress.totalSteps})
              </span>
            </div>
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${jobProgress.percent}%` }} />
            </div>
          </div>
        )}

        {errorMessage && (
          <div className="notice error" style={{ marginTop: 14, marginBottom: 0 }}>
            {errorMessage}
          </div>
        )}
      </section>

      {/* Instant Dataset Preview & Schema Panel */}
      <section className="panel">
        <div className="panel-head">
          <h3>Dataset preview & detected schema</h3>
          {profileLoading && <span className="muted">Refreshing preview…</span>}
        </div>
        {profileError && <div className="notice error">{profileError}</div>}
        {!profile && !profileLoading && !profileError && (
          <div className="empty-state">Select a sample or attach a file to inspect its schema and sample rows.</div>
        )}
        {profile && (
          <>
            {profile.warnings?.length > 0 && (
              <div className="status-banner warn">
                {profile.warnings.map((w, i) => (
                  <div key={i} style={{ fontSize: 13 }}>{w}</div>
                ))}
              </div>
            )}
            <div className="chip-row" style={{ marginBottom: 14 }}>
              {profile.columns.map((c) => (
                <span key={c.name} className="selected-badge">
                  <b>{c.name}</b>
                  <span className="muted">
                    {c.kind}
                    {c.missing_count > 0 ? ` · ${c.missing_count} missing` : ""}
                  </span>
                </span>
              ))}
            </div>
            {preview.length > 0 && (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      {Object.keys(preview[0]).map((key) => {
                        const isNum = profile.columns.find((c) => c.name === key)?.kind === "numeric";
                        return (
                          <th key={key} className={isNum ? "num" : ""}>
                            {key}
                          </th>
                        );
                      })}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.map((row, idx) => (
                      <tr key={idx}>
                        {Object.entries(row).map(([key, val]) => {
                          const isNum = profile.columns.find((c) => c.name === key)?.kind === "numeric";
                          return (
                            <td key={key} className={isNum ? "num" : ""}>
                              {String(val)}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </section>

      {/* Recent Experiments + Security Self-Test */}
      <div className="content-grid">
        <section className="panel" style={{ marginBottom: 0 }}>
          <div className="panel-head">
            <h3>Recent runs</h3>
            <button
              type="button"
              className="text-btn"
              onClick={() =>
                fetchHistory()
                  .then((data) => setExperimentHistory(data.items || []))
                  .catch((err) => setHistoryError(err.message))
              }
            >
              Refresh ↻
            </button>
          </div>
          {historyError && <div className="notice error">{historyError}</div>}
          {experimentHistory.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Dataset</th>
                    <th>Status</th>
                    <th className="num">Created</th>
                    <th className="num">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {experimentHistory.slice(0, 6).map((item) => (
                    <tr key={item.id}>
                      <td>
                        <b>{item.dataset_name}</b>
                        <span className="sub-id">{item.id.slice(0, 8)}</span>
                      </td>
                      <td>
                        <span className={`status-pill ${item.status}`}>{item.status}</span>
                      </td>
                      <td className="num">{new Date(item.created_at).toLocaleString()}</td>
                      <td className="num">
                        {item.is_job ? (
                          <span className="muted">{item.progress_percent || 0}%</span>
                        ) : (
                          <button type="button" className="text-btn" onClick={() => handleOpenExperiment(item.id)}>
                            Open →
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state">No saved analyses yet.</div>
          )}
        </section>

        <section className="panel" style={{ marginBottom: 0 }}>
          <div className="panel-head">
            <h3>Security Guardian self-test</h3>
            <button type="button" className="secondary-btn" onClick={handleSecuritySelfTest} disabled={securityTestLoading}>
              {securityTestLoading ? "Testing…" : "Run self-test"}
            </button>
          </div>
          <p className="muted" style={{ marginTop: 0 }}>
            Runs controlled adversarial plan scenarios through the deterministic pre-execution Security Guardian.
          </p>
          {securityTest && !securityTest.error && (
            <div>
              <div className={`status-banner ${securityTest.all_blocked ? "safe" : "danger"}`} style={{ marginBottom: 10 }}>
                <strong>
                  {securityTest.all_blocked
                    ? "All controlled attack scenarios blocked"
                    : "Guardrail test requires attention"}
                </strong>
              </div>
              <div className="chip-row">
                {(securityTest.scenarios || []).map((scenario, i) => (
                  <span key={i} className="selected-badge">
                    <b>{scenario.risk_type}</b>
                    <span className={`status-pill ${scenario.blocked ? "success" : "danger"}`}>
                      {scenario.blocked ? "Blocked" : "Allowed"}
                    </span>
                  </span>
                ))}
              </div>
            </div>
          )}
          {securityTest?.error && <div className="notice error">{securityTest.error}</div>}
        </section>
      </div>
    </div>
  );
}
