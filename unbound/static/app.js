const $ = (id) => document.getElementById(id);
const phases = [
  "INPUT_RECEIVED",
  "INTENT_CLASSIFIED",
  "IDEAS_GENERATED",
  "WILDCARDS_IDENTIFIED",
  "HYBRIDS_GENERATED",
  "META_HYBRIDS_GENERATED",
  "EVIDENCE_REVIEWED",
  "CANDIDATES_SCORED",
  "EXPERIMENT_DEFINED",
  "OUTPUT_VALIDATED",
];
let active = new URLSearchParams(location.search).get("run"),
  timer;
async function api(path, options = {}) {
  const r = await fetch(path, options);
  if (!r.ok) {
    let d;
    try {
      d = await r.json();
    } catch {
      d = { detail: r.statusText };
    }
    throw new Error(
      typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail),
    );
  }
  return r.json();
}
function text(tag, value, className) {
  const e = document.createElement(tag);
  e.textContent = value;
  if (className) e.className = className;
  return e;
}
function json(parent, value) {
  parent.append(text("pre", JSON.stringify(value, null, 2)));
}
function concept(parent, c) {
  const d = text("article", "", "concept");
  d.append(
    text("span", `${c.id} / ${c.primary_technique}`, "badge"),
    text("h3", c.name),
    text("p", c.mechanism),
  );
  if (c.parents.length)
    d.append(text("p", "Parents: " + c.parents.join(" + ")));
  d.append(text("p", "Differentiation: " + c.differentiation));
  if (c.speculative) d.append(text("p", "Speculative — requires validation"));
  if (c.commercial) json(d, c.commercial);
  if (c.category_shift)
    d.append(text("p", "Category shift: " + c.category_shift));
  parent.append(d);
}
function details(parent, title, value) {
  const d = document.createElement("details");
  d.append(text("summary", title));
  json(d, value);
  parent.append(d);
}
function render(run) {
  $("progress").hidden = false;
  $("run-meta").textContent = `${run.status} · ${run.phase} · ${run.id}`;
  $("phases").replaceChildren();
  phases.forEach((p, i) =>
    $("phases").append(
      text(
        "li",
        p.replaceAll("_", " "),
        i <= phases.indexOf(run.phase) ? "done" : "",
      ),
    ),
  );
  $("workers").replaceChildren();
  for (let i = 0; i < 4; i++) {
    const events = run.events.filter((e) => e.worker === `creative-${i}`),
      last = events.at(-1);
    $("workers").append(
      text(
        "div",
        `Worker ${i + 1}: ${last ? last.status + " · " + last.message : "Waiting"}`,
        "worker",
      ),
    );
  }
  $("error").textContent = run.error || "";
  $("retry").hidden = run.status !== "FAILED";
  const o = run.outputs;
  $("results").hidden = !Object.keys(o).length;
  $("result-note").textContent =
    run.provider === "mock"
      ? "OFFLINE MOCK — deterministic fixtures, not live inference or validated innovation."
      : run.status === "COMPLETED"
        ? "Structurally validated report. Review evidence and assumptions before acting."
        : "Partial results — execution is not complete.";
  $("report").replaceChildren();
  const report = $("report");
  if (o.INTENT_CLASSIFIED)
    details(report, "① Input interpretation", o.INTENT_CLASSIFIED);
  for (const [phase, title] of [
    ["IDEAS_GENERATED", "② Raw idea universe"],
    ["HYBRIDS_GENERATED", "④ First-order hybrids"],
    ["META_HYBRIDS_GENERATED", "⑤ Second-order meta-hybrids"],
  ]) {
    if (!o[phase]) continue;
    if (phase === "HYBRIDS_GENERATED" && o.WILDCARDS_IDENTIFIED)
      details(report, "③ Five wildcards", o.WILDCARDS_IDENTIFIED);
    const d = document.createElement("details");
    d.append(text("summary", `${title} (${o[phase].concepts.length})`));
    o[phase].concepts.forEach((c) => concept(d, c));
    report.append(d);
  }
  if (o.CANDIDATES_SCORED) {
    const all = [
      "IDEAS_GENERATED",
      "HYBRIDS_GENERATED",
      "META_HYBRIDS_GENERATED",
    ].flatMap((p) => o[p].concepts);
    report.append(text("h3", "⑥ Final shortlist"));
    o.CANDIDATES_SCORED.shortlist.forEach((a, i) => {
      report.append(
        text(
          "h3",
          `${i + 1}. ${a.concept_id} · ${a.composite.toFixed(2)} / 10`,
        ),
      );
      concept(
        report,
        all.find((c) => c.id === a.concept_id),
      );
      json(report, a);
    });
    details(
      report,
      "Scoring weights and unconventional retention",
      o.CANDIDATES_SCORED,
    );
  }
  if (o.EXPERIMENT_DEFINED) {
    details(report, "⑦ Recommended innovation", {
      concept_id: o.EXPERIMENT_DEFINED.concept_id,
      advantages: o.EXPERIMENT_DEFINED.advantages,
      uncertainties: o.EXPERIMENT_DEFINED.uncertainties,
    });
    details(report, "⑧ Execution blueprint", o.EXPERIMENT_DEFINED);
  }
  if (o.EVIDENCE_REVIEWED)
    details(report, "Research evidence", o.EVIDENCE_REVIEWED);
  if (o.OUTPUT_VALIDATED)
    details(report, "⑨ Validation summary", o.OUTPUT_VALIDATED);
  $("json").href = `/runs/${run.id}/export.json`;
  $("md").href = `/runs/${run.id}/export.md`;
}
async function loadHistory() {
  const rows = await api("/runs");
  $("history").replaceChildren();
  rows.forEach((r) => {
    const b = text(
      "button",
      `${r.input.slice(0, 90)} · ${r.status} · ${r.provider}`,
    );
    b.onclick = () => select(r.id);
    $("history").append(b);
  });
  if (!rows.length)
    $("history").append(text("p", "Your first exploration starts here."));
}
async function poll() {
  clearTimeout(timer);
  if (!active) return;
  try {
    const run = await api(`/runs/${active}`);
    render(run);
    $("notice").textContent = "";
    if (["QUEUED", "RUNNING"].includes(run.status))
      timer = setTimeout(poll, 1000);
    else await loadHistory();
  } catch (e) {
    $("notice").textContent =
      "Controller unreachable or request failed: " +
      e.message +
      "; status is unknown.";
    timer = setTimeout(poll, 5000);
  }
}
function select(id) {
  active = id;
  window.history.replaceState(null, "", `?run=${id}`);
  poll();
}
$("run-form").onsubmit = async (e) => {
  e.preventDefault();
  $("start").disabled = true;
  try {
    const r = await api("/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        input: $("input").value,
        configuration: { mode: $("mode").value, research: $("research").value },
      }),
    });
    select(r.run_id);
    await loadHistory();
  } catch (e) {
    $("notice").textContent = e.message;
  } finally {
    $("start").disabled = false;
  }
};
$("refresh").onclick = poll;
$("retry").onclick = async () => {
  try {
    await api(`/runs/${active}/retry`, { method: "POST" });
    poll();
  } catch (e) {
    $("notice").textContent = e.message;
  }
};
api("/health")
  .then((h) => {
    $("provider").textContent = h.mock
      ? "OFFLINE MOCK MODE — no live model execution"
      : `Provider: ${h.provider} · ${h.model}`;
  })
  .catch((e) => ($("notice").textContent = e.message));
loadHistory().catch((e) => ($("notice").textContent = e.message));
if (active) poll();
