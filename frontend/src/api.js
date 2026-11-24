/**
 * DataPilot REST API Client
 */

const API_BASE = "/api";

export async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("Backend health check failed:", err);
    return null;
  }
}

export async function fetchSamples() {
  const res = await fetch(`${API_BASE}/samples`);
  if (!res.ok) throw new Error("Failed to fetch sample datasets");
  return await res.json();
}

export async function profileDataset({ file, sampleId, targetColumn }) {
  const formData = new FormData();
  if (file) formData.append("file", file);
  if (sampleId) formData.append("sample_id", sampleId);
  if (targetColumn) formData.append("target_column", targetColumn);

  const res = await fetch(`${API_BASE}/profile`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Profiling failed with status ${res.status}`);
  }

  return await res.json();
}

export async function runAnalysis({ file, sampleId, inquiry, onProgress }) {
  const formData = new FormData();
  if (file) formData.append("file", file);
  if (sampleId) formData.append("sample_id", sampleId);
  if (inquiry) formData.append("inquiry", inquiry);

  const start = await fetch(`${API_BASE}/analysis/start`, { method: "POST", body: formData });
  if (!start.ok) {
    const errorData = await start.json().catch(() => ({}));
    throw new Error(errorData.detail || `Could not start analysis (${start.status})`);
  }
  const { job_id } = await start.json();
  // Long-running analyses are tracked by the backend; poll gently rather than
  // flooding the API with near-identical status GET requests.
  const deadline = Date.now() + 90 * 60 * 1000;
  let pollDelay = 2500;
  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, pollDelay));
    pollDelay = Math.min(8000, Math.round(pollDelay * 1.25));
    const response = await fetch(`${API_BASE}/analysis/${encodeURIComponent(job_id)}`);
    if (!response.ok) throw new Error(`Could not retrieve analysis status (${response.status})`);
    const job = await response.json();
    if (typeof onProgress === "function") onProgress({
      status: job.status,
      percent: Number(job.progress_percent || 0),
      stage: job.current_stage || "Queued",
      completedSteps: Number(job.completed_steps || 0),
      totalSteps: Number(job.total_steps || 11),
      updatedAt: job.updated_at,
    });
    if (job.status === "completed") return job.result;
    if (job.status === "failed") throw new Error(`Analysis failed (${job.error_code || "internal_error"}). Check backend logs.`);
  }
  throw new Error("This analysis is still running in the background. Its job ID is " + job_id + ". Refresh Experiment History to inspect its latest stage; do not start a duplicate run.");
}

export async function runSecuritySelfTest() {
  const res = await fetch(`${API_BASE}/security/self-test`, {
    method: "POST",
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(
      errorData.detail || `Security self-test failed with status ${res.status}`
    );
  }

  return await res.json();
}

export async function fetchHistory() {
  const res = await fetch(`${API_BASE}/history`);
  if (!res.ok) throw new Error("Failed to fetch experiment history");
  return await res.json();
}

export async function fetchExperiment(experimentId) {
  const res = await fetch(`${API_BASE}/history/${encodeURIComponent(experimentId)}`);
  if (!res.ok) throw new Error("Failed to fetch experiment");
  return await res.json();
}


export async function regenerateReport(experimentId) {
  const res = await fetch(`${API_BASE}/history/${encodeURIComponent(experimentId)}/report/regenerate`, { method: "POST" });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Report regeneration failed (${res.status})`);
  }
  return await res.json();
}


export async function runV4Analytics({ file, sampleId, inquiry, analyticsType }) {
  const body = new FormData();
  if (file) body.append("file", file);
  if (sampleId) body.append("sample_id", sampleId);
  body.append("inquiry", inquiry);
  if (analyticsType) body.append("analytics_type", analyticsType);
  const response = await fetch(`${API_BASE}/v4/analytics/query`, { method: "POST", body });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `Analytics failed (${response.status})`);
  return payload;
}
