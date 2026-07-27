const API_BASE = "/api/v1";
const MIN_COMPETITORS = 3;
const MAX_COMPETITORS = 8;

const form = document.getElementById("run-form");
const competitorList = document.getElementById("competitor-list");
const competitorHint = document.getElementById("competitor-hint");
const formError = document.getElementById("form-error");
const submitBtn = document.getElementById("submit-btn");

const statusPanel = document.getElementById("status-panel");
const statusDot = document.getElementById("status-dot");
const statusText = document.getElementById("status-text");
const statusSub = document.getElementById("status-sub");
const statusProgress = document.getElementById("status-progress");
const statusPercent = document.getElementById("status-percent");
const statusCounts = document.getElementById("status-counts");
const statusError = document.getElementById("status-error");

const STAGE_LABELS = {
  queued: "Queued",
  intake: "Resolving competitors",
  ingesting: "Fetching Reddit, search, and Hacker News results",
  extracting_claims: "Extracting grounded claims from documents",
  clustering_pain_points: "Clustering domain-wide pain points",
  computing_gaps: "Computing feature and positioning gaps",
  rendering: "Rendering brief and evidence files",
  done: "Done",
  failed: "Failed",
};

const resultsPanel = document.getElementById("results-panel");
const briefLink = document.getElementById("brief-link");
const evidenceLink = document.getElementById("evidence-link");

let eventSource = null;

function makeCompetitorRow(value) {
  const row = document.createElement("div");
  row.className = "competitor-row";

  const input = document.createElement("input");
  input.type = "text";
  input.required = true;
  input.maxLength = 80;
  input.placeholder = "Competitor name";
  input.value = value || "";
  input.setAttribute("aria-label", "Competitor name");

  const removeBtn = document.createElement("button");
  removeBtn.type = "button";
  removeBtn.className = "btn btn-remove";
  removeBtn.textContent = "Remove";
  removeBtn.setAttribute("aria-label", "Remove this competitor");
  removeBtn.addEventListener("click", () => {
    row.remove();
    updateCompetitorHint();
  });

  row.append(input, removeBtn);
  competitorList.appendChild(row);
  updateCompetitorHint();
  return row;
}

function updateCompetitorHint() {
  const count = competitorList.children.length;
  competitorHint.textContent = `${count} of ${MIN_COMPETITORS}–${MAX_COMPETITORS} competitors`;
}

function getCompetitorNames() {
  return Array.from(competitorList.querySelectorAll("input"))
    .map((input) => input.value.trim())
    .filter(Boolean);
}

document.getElementById("add-competitor").addEventListener("click", () => {
  if (competitorList.children.length >= MAX_COMPETITORS) return;
  makeCompetitorRow();
});

document.getElementById("load-sample").addEventListener("click", async () => {
  const response = await fetch("/api/v1/sample-input");
  if (!response.ok) return;
  const sample = await response.json();

  document.getElementById("company_name").value = sample.company_name;
  document.getElementById("company_description").value = sample.company_description;

  competitorList.innerHTML = "";
  sample.competitors.forEach((name) => makeCompetitorRow(name));
});

for (let i = 0; i < MIN_COMPETITORS; i++) makeCompetitorRow();

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  formError.textContent = "";

  const competitors = getCompetitorNames();
  if (competitors.length < MIN_COMPETITORS || competitors.length > MAX_COMPETITORS) {
    formError.textContent = `Please provide between ${MIN_COMPETITORS} and ${MAX_COMPETITORS} competitors.`;
    return;
  }
  if (!form.checkValidity()) {
    form.reportValidity();
    return;
  }

  const payload = {
    company_name: document.getElementById("company_name").value.trim(),
    company_description: document.getElementById("company_description").value.trim(),
    competitors,
  };

  submitBtn.disabled = true;
  submitBtn.textContent = "Starting…";

  try {
    const response = await fetch(`${API_BASE}/runs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(typeof body.detail === "string" ? body.detail : `HTTP ${response.status}`);
    }

    const created = await response.json();
    resultsPanel.hidden = true;
    statusPanel.hidden = false;
    statusPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    subscribeToRun(created.run_id);
  } catch (error) {
    formError.textContent = `Failed to start run: ${error.message}`;
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Run analysis";
  }
});

function subscribeToRun(runId) {
  if (eventSource) eventSource.close();
  statusError.textContent = "";

  eventSource = new EventSource(`${API_BASE}/runs/${runId}/events`);

  eventSource.addEventListener("status", (event) => {
    const data = JSON.parse(event.data);
    renderStatus(data);
    if (["succeeded", "partial", "failed"].includes(data.status)) {
      eventSource.close();
      eventSource = null;
      if (data.status !== "failed") showResults(runId);
    }
  });

  eventSource.onerror = () => {
    statusError.textContent = "Lost connection to the run's status stream.";
  };
}

function renderStatus(data) {
  statusDot.className = `dot ${data.status}`;

  const statusLabels = {
    queued: "Queued",
    running: STAGE_LABELS[data.stage] || "Running",
    succeeded: "Succeeded",
    partial: "Partial — some sources were skipped",
    failed: "Failed",
  };
  statusText.textContent = statusLabels[data.status] || data.status;
  statusSub.textContent = `run ${data.run_id} · stage: ${data.stage}`;
  statusError.textContent = data.error || "";

  const progress = Math.max(0, Math.min(100, data.progress ?? 0));
  statusProgress.value = progress;
  statusPercent.textContent = `${Math.round(progress)}%`;

  statusCounts.innerHTML = "";
  for (const [key, value] of Object.entries(data.counts || {})) {
    const dt = document.createElement("dt");
    dt.textContent = key.replace(/_/g, " ");
    const dd = document.createElement("dd");
    dd.textContent = value;
    statusCounts.append(dt, dd);
  }
}

function showResults(runId) {
  briefLink.href = `${API_BASE}/runs/${runId}/brief`;
  evidenceLink.href = `${API_BASE}/runs/${runId}/evidence`;
  resultsPanel.hidden = false;
  resultsPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}
