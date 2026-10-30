// Dashboard logic. All calculations happen on the server (/api/calculate);
// this file only holds state, renders, and calls the API.

const state = {
  employees: [],
  results: [],
  summary: null,
  baseline: null, // { total, label }
  sort: { key: "severance", asc: false },
  query: "",
  selected: null,
};

const $ = (id) => document.getElementById(id);
const eur = new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
const eur2 = new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" });
const num = new Intl.NumberFormat("de-DE");

function params() {
  return {
    divisor: Number($("divisor").value),
    child_bonus: Number($("childBonus").value || 0),
    disability_bonus: Number($("disabilityBonus").value || 0),
    minimum: Number($("minimum").value || 0),
    maximum: Number($("maximum").value || 0),
    cutoff: $("cutoff").value,
  };
}

async function api(path, body, as = "json") {
  const res = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: body instanceof FormData || body === undefined ? {} : { "Content-Type": "application/json" },
    body: body instanceof FormData ? body : body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const err = await res.json();
      msg = typeof err.detail === "string" ? err.detail : err.detail?.[0]?.msg || msg;
    } catch (_) { /* keep generic message */ }
    throw new Error(msg);
  }
  return as === "blob" ? res.blob() : res.json();
}

function toast(text) {
  const t = $("toast");
  t.textContent = text;
  t.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (t.hidden = true), 3200);
}

function download(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  a.click();
  URL.revokeObjectURL(url);
}

// ---------- data loading ----------

async function loadSample() {
  const data = await api("/api/sample");
  setDataset(data);
}

function setDataset(data) {
  state.employees = data.employees;
  state.baseline = null;
  $("client").textContent = data.client;
  $("kDelta").textContent = "";
  $("baselineHint").textContent = "Save the current settings, then change parameters to compare the cost.";
  recalc();
}

let recalcTimer;
function scheduleRecalc() {
  clearTimeout(recalcTimer);
  recalcTimer = setTimeout(recalc, 120);
}

async function recalc() {
  $("divisorOut").textContent = $("divisor").value;
  $("cutoffLabel").textContent = new Date($("cutoff").value).toLocaleDateString("de-DE");
  try {
    const data = await api("/api/calculate", { employees: state.employees, params: params() });
    $("paramError").hidden = true;
    state.results = data.results;
    state.summary = data.summary;
    render();
  } catch (e) {
    $("paramError").textContent = e.message;
    $("paramError").hidden = false;
  }
}

// ---------- rendering ----------

function rows() {
  const byId = new Map(state.results.map((r) => [r.employee_id, r]));
  const q = state.query.trim().toLowerCase();
  const list = state.employees
    .map((e) => ({ ...e, ...byId.get(e.id), name: `${e.first_name} ${e.last_name}` }))
    .filter((r) => !q || `${r.name} ${r.id} ${r.department}`.toLowerCase().includes(q));
  const { key, asc } = state.sort;
  list.sort((a, b) => {
    const x = a[key], y = b[key];
    const cmp = typeof x === "string" ? x.localeCompare(y) : x - y;
    return asc ? cmp : -cmp;
  });
  return list;
}

function render() {
  const s = state.summary;
  $("kCount").textContent = num.format(s.count);
  $("kTotal").textContent = eur.format(s.total);
  $("kAvg").textContent = eur.format(s.average);
  $("kMedian").textContent = eur.format(s.median);
  $("kLimits").textContent = `${s.at_maximum} / ${s.at_minimum}`;

  const delta = $("kDelta");
  if (state.baseline) {
    const diff = s.total - state.baseline.total;
    const pct = state.baseline.total ? (diff / state.baseline.total) * 100 : 0;
    delta.textContent = diff === 0 ? "same as baseline"
      : `${diff > 0 ? "+" : "−"}${eur.format(Math.abs(diff))} (${pct > 0 ? "+" : ""}${pct.toFixed(1)}%) vs baseline`;
    delta.className = "kpi-delta " + (diff > 0 ? "up" : diff < 0 ? "down" : "");
  }

  renderBars($("deptChart"), s.by_department.map((d) => ({ label: d.department, value: d.total, note: `${d.count}` })), eur);
  renderColumns($("histChart"), s.histogram.map((h) => ({ label: h.label, value: h.count })));
  renderTable();
  if (state.selected) openDrawer(state.selected);
}

function renderBars(el, data, fmt) {
  const w = 560, rowH = 30, labelW = 130, valueW = 110;
  const h = data.length * rowH + 4;
  const max = Math.max(...data.map((d) => d.value), 1);
  const barMax = w - labelW - valueW;
  el.innerHTML = `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Severance volume by department">
    ${data.map((d, i) => {
      const y = i * rowH + 4, bw = Math.max(2, (d.value / max) * barMax);
      return `<text x="0" y="${y + 15}">${escapeHtml(d.label)} (${d.note})</text>
        <rect x="${labelW}" y="${y + 3}" width="${bw}" height="16" rx="3" fill="#2f5bd3" opacity="${0.55 + 0.45 * (d.value / max)}"></rect>
        <text class="val" x="${labelW + bw + 8}" y="${y + 15}">${fmt.format(d.value)}</text>`;
    }).join("")}
  </svg>`;
}

function renderColumns(el, data) {
  const w = 440, h = 190, base = 160, top = 18;
  const max = Math.max(...data.map((d) => d.value), 1);
  const slot = w / data.length, bw = slot * 0.62;
  el.innerHTML = `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Distribution of severance payments">
    <line x1="0" x2="${w}" y1="${base}" y2="${base}" stroke="#e5e7eb"></line>
    ${data.map((d, i) => {
      const bh = (d.value / max) * (base - top), x = i * slot + (slot - bw) / 2;
      return `<rect x="${x}" y="${base - bh}" width="${bw}" height="${bh}" rx="3" fill="#1f2a44"></rect>
        <text class="val" x="${x + bw / 2}" y="${base - bh - 5}" text-anchor="middle">${d.value}</text>
        <text x="${x + bw / 2}" y="${base + 16}" text-anchor="middle">${d.label}</text>`;
    }).join("")}
  </svg>`;
}

function renderTable() {
  const tbody = document.querySelector("#table tbody");
  tbody.innerHTML = rows().map((r) => {
    const badges = [
      r.limit_applied === "maximum" ? '<span class="badge max">capped</span>' : "",
      r.limit_applied === "minimum" ? '<span class="badge min">minimum</span>' : "",
      r.severely_disabled ? '<span class="badge sb">SB</span>' : "",
    ].join(" ");
    return `<tr data-id="${escapeHtml(r.id)}">
      <td>${escapeHtml(r.name)}<span class="id">${escapeHtml(r.id)}</span></td>
      <td>${escapeHtml(r.department)}</td>
      <td class="num">${r.age}</td>
      <td class="num">${r.years_of_service}</td>
      <td class="num">${eur2.format(r.monthly_gross)}</td>
      <td class="num">${r.children}</td>
      <td class="num"><strong>${eur2.format(r.severance)}</strong></td>
      <td>${badges}</td>
    </tr>`;
  }).join("");
  document.querySelectorAll("#table th[data-key]").forEach((th) => {
    th.classList.toggle("sorted", th.dataset.key === state.sort.key);
    th.classList.toggle("asc", th.dataset.key === state.sort.key && state.sort.asc);
  });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ---------- detail drawer ----------

function openDrawer(id) {
  const emp = state.employees.find((e) => e.id === id);
  const res = state.results.find((r) => r.employee_id === id);
  if (!emp || !res) return closeDrawer();
  state.selected = id;
  $("dId").textContent = emp.id;
  $("dName").textContent = `${emp.first_name} ${emp.last_name}`;
  $("dMeta").textContent = `${emp.department} · ${emp.location} · ${res.age} years old · ${res.years_of_service} years of service`;
  $("dAmount").textContent = eur2.format(res.severance);
  $("dSteps").innerHTML = res.explanation_steps.map((s) => `<li>${escapeHtml(s)}</li>`).join("");
  $("drawer").classList.add("open");
  $("drawer").setAttribute("aria-hidden", "false");
  $("backdrop").hidden = false;
}

function closeDrawer() {
  state.selected = null;
  $("drawer").classList.remove("open");
  $("drawer").setAttribute("aria-hidden", "true");
  $("backdrop").hidden = true;
}

function selectedEmployee() {
  return state.employees.find((e) => e.id === state.selected);
}

// ---------- events ----------

["divisor", "childBonus", "disabilityBonus", "minimum", "maximum", "cutoff"].forEach((id) =>
  $(id).addEventListener("input", scheduleRecalc));

$("search").addEventListener("input", (e) => { state.query = e.target.value; renderTable(); });

document.querySelectorAll("#table th[data-key]").forEach((th) =>
  th.addEventListener("click", () => {
    const key = th.dataset.key;
    state.sort = { key, asc: state.sort.key === key ? !state.sort.asc : key === "name" || key === "department" };
    renderTable();
  }));

document.querySelector("#table tbody").addEventListener("click", (e) => {
  const tr = e.target.closest("tr[data-id]");
  if (tr) openDrawer(tr.dataset.id);
});

$("closeDrawer").addEventListener("click", closeDrawer);
$("backdrop").addEventListener("click", closeDrawer);
document.addEventListener("keydown", (e) => e.key === "Escape" && closeDrawer());

$("setBaseline").addEventListener("click", () => {
  state.baseline = { total: state.summary.total };
  $("baselineHint").textContent = `Baseline saved at divisor ${$("divisor").value}: ${eur.format(state.summary.total)}.`;
  render();
});

$("fileInput").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append("file", file);
  try {
    setDataset(await api("/api/upload", fd));
    toast(`Loaded ${file.name}`);
  } catch (err) {
    toast(err.message);
  }
  e.target.value = "";
});

$("resetSample").addEventListener("click", () => loadSample().then(() => toast("Sample data loaded")));

$("downloadAll").addEventListener("click", async (e) => {
  const btn = e.currentTarget;
  btn.disabled = true;
  btn.textContent = "Generating…";
  try {
    download(await api("/api/pdf/all", { employees: state.employees, params: params() }, "blob"), "severance_statements.zip");
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Download all PDFs";
  }
});

$("dPdf").addEventListener("click", async () => {
  const emp = selectedEmployee();
  try {
    download(await api("/api/pdf", { employee: emp, params: params() }, "blob"), `severance_${emp.id}.pdf`);
  } catch (err) {
    toast(err.message);
  }
});

loadSample().catch((e) => toast(e.message));
