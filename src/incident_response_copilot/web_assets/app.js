const state = { active: null };

const SAMPLE_TRIAGE = {
  title: "Suspicious production admin login spike",
  signal_source: "siem.alert",
  description: "Multiple failed admin logins followed by a successful production login from a new ASN",
  metadata: {
    environment: "production",
    failed_logins: 37,
    asset: "admin-portal"
  }
};

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed: ${response.status}`);
  }
  return response.json();
}

function metric(key, value) {
  return `<div class="metric"><span>${key}</span><b>${value}</b></div>`;
}

function incidentCard(incident) {
  return `<div class="incident ${state.active === incident.id ? "active" : ""}" data-id="${incident.id}">
    <strong class="${incident.severity}">${incident.title}</strong>
    <p>${incident.severity} · ${incident.status}</p>
  </div>`;
}

function card(title, body) {
  return `<div class="card"><strong>${title}</strong><p>${body}</p></div>`;
}

async function load(id = null) {
  const [summary, incidents] = await Promise.all([api("/api/summary"), api("/api/incidents")]);
  const incidentIds = incidents.map((incident) => incident.id);
  state.active = id || (incidentIds.includes(state.active) ? state.active : incidents[0]?.id);

  document.querySelector("#hero").textContent = `${summary.incident_count} incidents under review`;
  document.querySelector("#risk").textContent = `${summary.critical_count} critical`;
  document.querySelector("#metrics").innerHTML =
    metric("Incidents", summary.incident_count) +
    metric("Critical", summary.critical_count) +
    metric("Open tasks", summary.open_task_count) +
    metric("Approvals", summary.approval_task_count) +
    metric("Evidence", summary.evidence_count);
  document.querySelector("#incidents").innerHTML = incidents.map(incidentCard).join("");
  document.querySelectorAll("[data-id]").forEach((element) => {
    element.addEventListener("click", () => load(element.dataset.id));
  });

  if (state.active) {
    const detail = await api(`/api/incidents/${state.active}`);
    document.querySelector("#evidence").innerHTML = detail.evidence
      .map((evidence) => card(evidence.source, `${evidence.description} · confidence ${evidence.confidence}`))
      .join("");
    document.querySelector("#tasks").innerHTML =
      detail.tasks
        .map((task) => card(task.title, `${task.status} · owner ${task.owner} · approval ${task.requires_approval}`))
        .join("") + detail.playbook.map((step) => card(step.title, step.human_review_note)).join("");
  }
}

function initTriageForm() {
  const textarea = document.querySelector("#triage-json");
  const status = document.querySelector("#triage-status");
  textarea.value = JSON.stringify(SAMPLE_TRIAGE, null, 2);
  document.querySelector("#triage").addEventListener("click", async () => {
    status.textContent = "Triaging alert...";
    status.className = "";
    try {
      const payload = JSON.parse(textarea.value);
      const detail = await api("/api/incidents/triage", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      status.textContent = `Created ${detail.incident.severity} incident: ${detail.incident.title}.`;
      status.className = "success";
      await load(detail.incident.id);
    } catch (error) {
      status.textContent = error.message;
      status.className = "error";
    }
  });
}

document.querySelector("#reset").addEventListener("click", async () => {
  await api("/api/demo/reset", { method: "POST" });
  state.active = null;
  await load();
});

initTriageForm();
load().catch((error) => {
  document.querySelector("#hero").textContent = error.message;
});
