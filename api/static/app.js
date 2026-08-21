/* SIGNAL Command Center — dependency-free UI */
"use strict";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const CLS_COLORS = {
  CRITICAL: "#ff5d73", SIGNIFICANT: "#ffb454", EMERGING: "#ffe28a",
  WEAK: "#4da3ff", NOISE: "#647489",
};

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function toast(msg, ms = 2600) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.add("hidden"), ms);
}

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) {
    let detail = r.statusText;
    try { const j = await r.json(); detail = j.detail || JSON.stringify(j); } catch {}
    throw new Error(`${r.status}: ${detail}`);
  }
  return r.json();
}

/* ---------------- health ---------------- */
async function refreshHealth() {
  const dot = $("#health-dot");
  try {
    const h = await api("/api/health");
    const ok = h.db === "ok" && h.n8n === "ok";
    dot.className = "dot " + (ok ? "ok" : "bad");
    dot.title = `db:${h.db} n8n:${h.n8n}`;
  } catch {
    dot.className = "dot bad";
    dot.title = "api unreachable";
  }
}

/* ---------------- stats + signals ---------------- */
async function loadStats() {
  try {
    const s = await api("/api/stats");
    const cards = [
      ["Signals tracked", s.total_signals ?? 0, `${s.demo_signals ?? 0} demo`],
      ["Critical", s.critical ?? 0, "score > 85"],
      ["Significant", s.significant ?? 0, "score 71-85"],
      ["Emerging", s.emerging ?? 0, "score 51-70"],
      ["Dismissed", s.dismissed ?? 0, "human decisions"],
      ["Runs · 24h", s.runs_24h ?? 0, `${s.completed_runs ?? 0} completed total`],
      ["Avg score", s.avg_score ?? "—", "all signals"],
    ];
    $("#stat-cards").innerHTML = cards.map(([k, v, sub]) =>
      `<div class="card"><div class="k">${k}</div><div class="v" style="color:${k.includes("Critical") && v ? CLS_COLORS.CRITICAL : "var(--text)"}">${v}</div><div class="s">${sub}</div></div>`).join("");
  } catch (e) { toast("stats failed: " + e.message); }
}

async function loadSignals() {
  const cls = $("#f-class").value;
  const status = $("#f-status").value;
  const demoOnly = $("#f-demo").checked;
  const params = new URLSearchParams({ limit: 100 });
  if (cls) params.set("classification", cls);
  if (status) params.set("status", status);
  try {
    let data = await api(`/api/signals?${params}`);
    let rows = data.signals;
    if (demoOnly) rows = rows.filter(r => r.is_demo);
    if (!rows.length) {
      $("#signals-table").innerHTML = `<div class="muted" style="padding:22px">No signals yet — hit <b>⚡ INVESTIGATE</b> to run the pipeline.</div>`;
      return;
    }
    $("#signals-table").innerHTML = `
      <table class="grid"><thead><tr>
        <th>Signal</th><th>Classification</th><th>Score</th><th>Velocity</th>
        <th>Sources</th><th>Status</th><th>DNA</th><th>Updated</th>
      </tr></thead><tbody>
      ${rows.map(r => {
        const c = r.classification || "WEAK";
        const color = CLS_COLORS[c] || "#888";
        const score = Math.round(r.signal_score ?? 0);
        return `<tr class="rowlink" data-id="${r.signal_id}">
          <td><div style="font-weight:700">${esc(r.title)}</div>
              <div class="muted" style="font-size:11px">${esc(r.topic)}${r.is_demo ? ' · <span style="color:#7d8bb5">DEMO</span>' : ""}</div></td>
          <td><span class="badge b-${c}">${c}</span></td>
          <td><span class="scorebar"><i style="width:${score}%;background:${color}"></i></span>${score}</td>
          <td>${r.velocity != null ? (r.velocity > 0 ? "+" : "") + Math.round(r.velocity) + "%" : "—"}</td>
          <td>${r.articles_found ?? 0} → ${r.independent_sources ?? 0}</td>
          <td class="st ${r.status}">${r.status}</td>
          <td class="mini-dna" data-id="${r.signal_id}"></td>
          <td class="muted" style="font-size:11px">${(r.last_updated_at || "").slice(0, 16).replace("T", " ")}</td>
        </tr>`;
      }).join("")}
      </tbody></table>`;
    $$("#signals-table tr.rowlink").forEach(tr => tr.onclick = () => openSignal(tr.dataset.id));
    $$("#signals-table .mini-dna").forEach(td => {
      const row = rows.find(r => r.signal_id === td.dataset.id);
      td.innerHTML = miniDna(row.dna);
    });
  } catch (e) { toast("signals failed: " + e.message); }
}

function miniDna(dna) {
  if (!dna) return "";
  const keys = ["source_quality", "independence", "acceleration", "novelty", "cross_domain"];
  return `<div style="display:flex;gap:3px;align-items:flex-end;height:26px">${
    keys.map(k => {
      const v = Math.max(2, Math.min(100, dna[k] ?? 0));
      return `<i title="${k}: ${v}" style="width:9px;height:${v * 0.26}px;background:${CLS_COLORS.SIGNIFICANT};border-radius:2px;display:inline-block;opacity:.9"></i>`;
    }).join("")}</div>`;
}

/* ---------------- signal detail drawer ---------------- */
let CURRENT = null;

async function openSignal(id) {
  let d;
  try { d = await api(`/api/signals/${id}`); } catch (e) { return toast(e.message); }
  CURRENT = d;
  const s = d.signal;
  $("#drawer-title").innerHTML = `
    <h2>${esc(s.title)}</h2>
    <div class="chips">
      <span class="badge b-${s.classification}">${s.classification}</span>
      <span class="chip">score ${Math.round(s.signal_score ?? 0)} · conf ${Math.round(s.confidence ?? 0)}</span>
      <span class="chip">status ${s.status}</span>
      <span class="chip">${s.is_demo ? "DEMO fixtures" : "live sensors"}</span>
      ${s.scenario_key ? `<span class="chip">scenario: ${esc(s.scenario_key)}</span>` : ""}
    </div>`;
  $("#drawer-actions").innerHTML = ["INVESTIGATE", "WATCH", "CONFIRM", "DISMISS"]
    .map(x => `<button class="btn mini ${x === "DISMISS" ? "danger" : ""}" data-decision="${x}">${x}</button>`).join("");
  $$("#drawer-actions [data-decision]").forEach(b => b.onclick = () => decide(b.dataset.decision));
  showTab("overview");
  $("#drawer").classList.remove("hidden");
  $("#scrim").classList.remove("hidden");
}

function closeDrawer() {
  $("#drawer").classList.add("hidden");
  $("#scrim").classList.add("hidden");
  CURRENT = null;
  loadSignals(); loadStats(); loadTimeline();
}

async function decide(decision) {
  if (!CURRENT) return;
  try {
    await api(`/api/signals/${CURRENT.signal.signal_id}/decision`, {
      method: "POST", body: JSON.stringify({ decision }),
    });
    toast(`${decision} recorded — human-in-the-loop persisted`);
    openSignal(CURRENT.signal.signal_id);
  } catch (e) { toast(e.message); }
}

function showTab(tab) {
  $$(".dtab").forEach(t => t.classList.toggle("active", t.dataset.tab === tab));
  const body = $("#drawer-body");
  if (!CURRENT) return body.innerHTML = "";
  const d = CURRENT, s = d.signal;
  if (tab === "overview") {
    const inv = d.investigation || {};
    body.innerHTML = `
      <div class="ov-grid">
        <div class="ov-side">
          ${scoreRing(s.signal_score, s.classification)}
          ${radarSvg(s.dna)}
        </div>
        <div>
          <section class="sub" style="margin-top:0"><h3>Pipeline summary</h3>
            <div class="kv">
              <div><div class="k">articles</div><div class="v">${inv.pages_retrieved ?? s.articles_found ?? 0}</div></div>
              <div><div class="k">underlying events</div><div class="v">${s.underlying_events ?? 0}</div></div>
              <div><div class="k">independent sources</div><div class="v">${s.independent_sources ?? 0}</div></div>
              <div><div class="k">velocity</div><div class="v">${s.velocity != null ? Math.round(s.velocity) + "%" : "—"}</div></div>
              <div><div class="k">red-team searches</div><div class="v">${inv.redteam_searches ?? 0}</div></div>
              <div><div class="k">duplicates removed</div><div class="v">${inv.duplicates_removed ?? 0}</div></div>
            </div>
          </section>
          <section class="sub"><h3>Sensor health (last run)</h3>
            <div class="chips">${Object.entries(inv.sensor_health || {}).map(([k, v]) =>
              `<span class="chip">${k}: <b style="color:${v === "AVAILABLE" ? "var(--good)" : v === "DEGRADED" ? "var(--warn)" : "var(--dim)"}">${v}</b></span>`).join("") || '<span class="muted">no run data</span>'}</div>
          </section>
          <section class="sub"><h3>Score history</h3>${sparkline(d.history.map(h => h.score), 420, 60)}</section>
          <section class="sub"><h3>Channel observations</h3>
            <table class="grid claim-table"><tbody>
            ${(d.observations || []).slice(0, 10).map(o => `<tr><td>${o.channel}</td><td>${o.metric}</td><td>${o.value}</td><td class="muted">${String(o.observed_at).slice(0, 16).replace("T", " ")}</td></tr>`).join("") || '<tr><td class="muted">none recorded</td></tr>'}
            </tbody></table>
          </section>
        </div>
      </div>`;
  } else if (tab === "evidence") {
    body.innerHTML = `
      <section class="sub" style="margin-top:0"><h3>Atomic claims (${d.claims.length}) — every claim traces to a source</h3>
        <table class="grid claim-table"><thead><tr><th>Actor</th><th>Action</th><th>Statement</th><th>Qty</th><th>Verification</th></tr></thead><tbody>
        ${d.claims.map(c => `<tr>
          <td>${esc(c.actor || "—")}</td><td class="act">${esc(c.action)}</td>
          <td>${esc(c.statement)}</td><td>${c.quantity ?? ""}${c.quantity_unit ? " " + esc(c.quantity_unit) : ""}</td>
          <td class="verif-${esc(c.verification)}">${esc(c.verification)}</td></tr>`).join("") || '<tr><td colspan="5" class="muted">no claims</td></tr>'}
        </tbody></table>
      </section>
      <section class="sub"><h3>Underlying events (normalized)</h3>
        <table class="grid claim-table"><tbody>
        ${(d.events || []).map(e => `<tr><td>${esc(e.actor)} <span class="act">${esc(e.action)}</span> ${esc(e.object)}</td><td>${e.quantity ?? ""}</td><td class="muted">conf ${e.confidence != null ? Number(e.confidence).toFixed(2) : "—"}</td></tr>`).join("") || '<tr><td class="muted">none</td></tr>'}
        </tbody></table>
      </section>
      <section class="sub"><h3>Source forensics (${d.sources.length} sources)</h3>
        <table class="grid claim-table"><thead><tr><th>Title</th><th>Publisher</th><th>Type</th><th>Class</th><th>Cred</th><th>Event group</th></tr></thead><tbody>
        ${d.sources.map(src => `<tr>
          <td><a href="${esc(src.source_url)}" target="_blank" rel="noopener" style="color:var(--accent)">${esc((src.title || src.source_url).slice(0, 70))}</a></td>
          <td>${esc(src.publisher || "—")}</td><td>${esc(src.source_type)}</td>
          <td>${esc(src.primary_or_secondary)}</td><td>${src.credibility_score != null ? Number(src.credibility_score).toFixed(2) : "—"}</td>
          <td class="muted">${esc(src.independence_group || "")}</td></tr>`).join("") || '<tr><td colspan="6" class="muted">no sources</td></tr>'}
        </tbody></table>
      </section>`;
  } else if (tab === "hypotheses") {
    body.innerHTML = d.hypotheses.length ? d.hypotheses.map(h => `
      <div class="hyp">
        <div class="stmt">${esc(h.statement)}
          ${h.status === "leading" ? ' <span class="tag-leading">★ LEADING</span>' : ""}
          ${h.status === "disproved" ? ' <span class="tag-disproved">✕ DISPROVED</span>' : ""}</div>
        <div class="bars">
          <div class="bar-row">prior<div class="bar"><i style="width:${h.prior_confidence}%"></i></div>${h.prior_confidence}</div>
          <div class="bar-row">post-red-team<div class="bar post"><i style="width:${h.posterior_confidence ?? h.prior_confidence}%"></i></div>${h.posterior_confidence ?? "?"}</div>
        </div>
        ${h.reasoning ? `<div class="muted" style="margin-top:6px;font-size:12px">${esc(h.reasoning)}</div>` : ""}
      </div>`).join("") : '<p class="muted">no hypotheses stored</p>';
  } else if (tab === "graph") {
    body.innerHTML = `<section class="sub" style="margin-top:0"><h3>Entity relationship graph</h3>${
      graphSvg(d.relationships)}<p class="muted" style="font-size:11px;margin-top:6px">Edge weight = evidence count. Built by the 🔗 RELATIONSHIP GRAPH stage from resolved canonical entities.</p></section>`;
  } else if (tab === "redteam") {
    body.innerHTML = `
      <section class="sub" style="margin-top:0"><h3>Contradictions found by adversarial sweep (${d.contradictions.length})</h3>
      ${d.contradictions.map(c => `<div class="contra"><b>${esc(c.statement.slice(0, 160))}</b>
        <div class="muted" style="font-size:12px;margin-top:4px">strength ${Number(c.strength).toFixed(2)} · via ${esc(c.found_by)} ${c.evidence_url ? `· <a href="${esc(c.evidence_url)}" target="_blank" rel="noopener" style="color:var(--accent)">source</a>` : ""}</div></div>`).join("") || '<p class="muted">No contradictions surfaced.</p>'}
      </section>
      <section class="sub"><h3>Confidence movement</h3>
        ${d.hypotheses.map(h => `<div class="hyp"><div class="stmt">${esc(h.statement)}</div>
        <div class="bars"><div class="bar-row">${h.prior_confidence} → <b style="color:${(h.posterior_confidence ?? 0) >= h.prior_confidence ? "var(--good)" : "var(--bad)"}">${h.posterior_confidence ?? "?"}</b> (${(h.posterior_confidence ?? 0) - h.prior_confidence >= 0 ? "+" : ""}${(h.posterior_confidence ?? 0) - h.prior_confidence})</div></div></div>`).join("")}
      </section>`;
  } else if (tab === "invalidators") {
    body.innerHTML = `
      <p class="muted" style="margin-bottom:12px">Falsification checklist — the pipeline states upfront what would change its mind.</p>
      ${(d.invalidators || []).map(i_row => `<div class="inval"><span class="box">${i_row.still_valid ? "☑" : "☐"}</span><span>${esc(i_row.condition_text)}</span></div>`).join("") || '<p class="muted">none</p>'}`;
  }
}

/* ---------------- svg helpers ---------------- */
function scoreRing(score, cls) {
  const v = Math.max(0, Math.min(100, score ?? 0));
  const r = 52, c = 2 * Math.PI * r;
  const color = CLS_COLORS[cls] || "#4da3ff";
  return `<svg width="140" height="140" viewBox="0 0 140 140">
    <circle cx="70" cy="70" r="${r}" stroke="#1c2743" stroke-width="12" fill="none"/>
    <circle cx="70" cy="70" r="${r}" stroke="${color}" stroke-width="12" fill="none"
      stroke-linecap="round" stroke-dasharray="${(c * v / 100).toFixed(1)} ${c.toFixed(1)}"
      transform="rotate(-90 70 70)"/>
    <text x="70" y="66" text-anchor="middle" fill="#dbe4ff" font-size="30" font-weight="800">${Math.round(v)}</text>
    <text x="70" y="88" text-anchor="middle" fill="#7d8bb5" font-size="11">${cls || ""}</text>
  </svg>`;
}

function radarSvg(dna, size = 200) {
  if (!dna) return "";
  const keys = [["source_quality", "QUALITY"], ["independence", "INDEPENDENCE"], ["acceleration", "ACCEL"], ["novelty", "NOVELTY"], ["cross_domain", "X-DOMAIN"], ["contradiction", "CONTRADICTION"]];
  const cx = size / 2, cy = size / 2, R = size / 2 - 28, n = keys.length;
  const pt = (i, frac) => {
    const a = -Math.PI / 2 + i * 2 * Math.PI / n;
    return [cx + Math.cos(a) * R * frac, cy + Math.sin(a) * R * frac];
  };
  const rings = [0.25, 0.5, 0.75, 1].map(f =>
    `<polygon points="${keys.map((_, i) => pt(i, f).join(",")).join(" ")}" fill="none" stroke="#1c2743"/>`).join("");
  const axes = keys.map((_, i) => {
    const [x, y] = pt(i, 1); return `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="#1c2743"/>`;
  }).join("");
  const vals = keys.map(([k]) => Math.max(0, Math.min(100, dna[k] ?? 0)) / 100);
  const poly = keys.map((_, i) => pt(i, vals[i]).join(",")).join(" ");
  const labels = keys.map(([k, label], i) => {
    const [x, y] = pt(i, 1.24);
    return `<text x="${x}" y="${y}" text-anchor="middle" fill="#7d8bb5" font-size="8.5">${label}</text>`;
  }).join("");
  return `<svg width="${size}" height="${size + 6}" viewBox="0 0 ${size} ${size + 6}">
    ${rings}${axes}
    <polygon points="${poly}" fill="rgba(77,163,255,.28)" stroke="#4da3ff" stroke-width="1.6"/>
    ${labels}</svg>`;
}

function sparkline(values, w = 300, h = 56) {
  if (!values || !values.length) return '<p class="muted">no history yet</p>';
  const min = Math.min(...values), max = Math.max(...values);
  const span = max - min || 1;
  const pts = values.map((v, i) => `${(i / Math.max(values.length - 1, 1)) * (w - 8) + 4},${h - 6 - ((v - min) / span) * (h - 14)}`);
  const last = values[values.length - 1];
  return `<div class="spark-wrap"><svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
    <polyline points="${pts.join(" ")}" fill="none" stroke="#4da3ff" stroke-width="2"/>
    <circle cx="${pts[pts.length - 1].split(",")[0]}" cy="${pts[pts.length - 1].split(",")[1]}" r="3.4" fill="#4da3ff"/>
    <text x="${w - 4}" y="12" text-anchor="end" fill="#7d8bb5" font-size="10">latest ${Math.round(last)}</text>
  </svg></div>`;
}

function graphSvg(rels, size = 560) {
  if (!rels || !rels.length) return '<p class="muted">no relationships mapped</p>';
  const nodes = new Set();
  rels.forEach(r => { nodes.add(r.subject); nodes.add(r.object); });
  const names = [...nodes].slice(0, 18);
  const pos = {};
  names.forEach((n, i) => {
    const a = -Math.PI / 2 + i * 2 * Math.PI / names.length;
    pos[n] = [size / 2 + Math.cos(a) * (size / 2 - 80), size / 2 + Math.sin(a) * (size / 2 - 80)];
  });
  const edges = rels.filter(r => pos[r.subject] && pos[r.object]).slice(0, 40).map(r => {
    const [x1, y1] = pos[r.subject], [x2, y2] = pos[r.object];
    const mx = (x1 + x2) / 2 + (y2 - y1) * 0.12, my = (y1 + y2) / 2 - (x2 - x1) * 0.12;
    return `<path d="M${x1},${y1} Q${mx},${my} ${x2},${y2}" fill="none" stroke="#2c4470" stroke-width="${Math.max(1, (r.evidence_count || 1) * 0.8)}"/>
      <text x="${mx}" y="${my}" text-anchor="middle" fill="#7d8bb5" font-size="8.5">${esc(r.predicate)}</text>`;
  }).join("");
  const dots = names.map(n => {
    const [x, y] = pos[n];
    return `<circle cx="${x}" cy="${y}" r="26" fill="#182238" stroke="#4da3ff"/>
      <text x="${x}" y="${y + 3}" text-anchor="middle" fill="#dbe4ff" font-size="8.6">${esc(n.slice(0, 12))}</text>`;
  }).join("");
  return `<svg width="100%" viewBox="0 0 ${size} ${size}" style="max-height:480px;background:var(--bg);border-radius:12px;border:1px solid var(--line)">${edges}${dots}</svg>`;
}

/* ---------------- timeline view ---------------- */
async function loadTimeline() {
  try {
    const { signals } = await api("/api/signals?limit=30");
    $("#timeline-list").innerHTML = signals.length ? `<div class="legend">
        <span><i style="background:#4da3ff"></i>score evolution</span>
        <span><i style="background:#38d39f"></i>channel volume (right)</span></div>
      <div class="tl-grid">${signals.map(sig => `
        <div class="tl-card" data-id="${sig.signal_id}">
          <div class="tl-title">${esc(sig.title)}</div>
          <div><span class="badge b-${sig.classification}">${sig.classification}</span></div>
          <div id="tl-${sig.signal_id}" class="spark-wrap"><span class="muted" style="font-size:11px">loading…</span></div>
          <div class="tl-meta"><span>${sig.articles_found ?? 0} sources</span><span>v ${sig.velocity != null ? Math.round(sig.velocity) + "%" : "—"}</span></div>
        </div>`).join("")}</div>`
      : '<p class="muted" style="padding:18px">No signals yet.</p>';
    $$(".tl-card").forEach(card => card.onclick = () => openSignal(card.dataset.id));
    for (const sig of signals.slice(0, 12)) {
      api(`/api/signals/${sig.signal_id}`).then(d => {
        const el = $(`#tl-${sig.signal_id}`);
        if (!el) return;
        el.innerHTML = sparkline(d.history.map(h => h.score), 300, 48);
      }).catch(() => {});
    }
  } catch (e) { toast(e.message); }
}

/* ---------------- runs view ---------------- */
async function loadRuns() {
  try {
    const { runs } = await api("/api/runs?limit=40");
    $("#runs-table").innerHTML = !runs.length
      ? '<p class="muted" style="padding:18px">No runs recorded yet.</p>'
      : `<table class="grid"><thead><tr><th>Run</th><th>Status</th><th>Started</th><th>Pages</th><th>Claims</th><th>Events</th><th>Dupes</th><th>Red team</th><th>Score</th><th>Sensors</th></tr></thead><tbody>
        ${runs.map(ru => `<tr>
          <td class="muted" style="font-family:monospace;font-size:11px">${String(ru.run_id).slice(0, 8)}</td>
          <td class="st ${ru.status === "COMPLETED" ? "CONFIRMED" : ru.status === "FAILED" ? "DISMISSED" : ""}">${ru.status}</td>
          <td class="muted" style="font-size:11px">${(ru.started_at || "").slice(0, 19).replace("T", " ")}</td>
          <td>${ru.pages_retrieved ?? 0}</td><td>${ru.claims_extracted ?? 0}</td><td>${ru.events_normalized ?? 0}</td>
          <td>${ru.duplicates_removed ?? 0}</td><td>${ru.redteam_searches ?? 0}</td>
          <td>${ru.final_score != null ? Math.round(ru.final_score) : "—"}</td>
          <td>${Object.values(ru.sensor_health || {}).filter(v => v === "AVAILABLE").length}/${Object.keys(ru.sensor_health || {}).length}</td>
        </tr>`).join("")}</tbody></table>`;
  } catch (e) { toast(e.message); }
}

/* ---------------- investigate modal ---------------- */
function openModal() {
  $("#modal").classList.remove("hidden");
  $("#inv-status").textContent = "";
  setTimeout(() => $("#inv-topic").focus(), 50);
}
function closeModal() { $("#modal").classList.add("hidden"); }

async function runInvestigate() {
  const topic = $("#inv-topic").value.trim();
  const scenario = $("#inv-scenario").value;
  if (!topic && !scenario) return toast("Enter a topic or pick a demo scenario");
  const body = {};
  if (topic) body.topic = topic;
  if (scenario) body.scenario_key = scenario;
  const statusEl = $("#inv-status");
  $("#inv-run").disabled = true;
  statusEl.textContent = "▶ dispatching to n8n Intelligence Pipeline…\nplan → sense ×7 → deep-crawl → hypothesize → red-team → forensics → score";
  const t0 = Date.now();
  try {
    const pkg = await api("/api/investigate", { method: "POST", body: JSON.stringify(body) });
    const secs = ((Date.now() - t0) / 1000).toFixed(1);
    statusEl.textContent += `\n✔ completed in ${secs}s — score ${pkg.score}/100 (${pkg.classification})`;
    toast(`Signal ${pkg.classification} · score ${pkg.score}/100`);
    setTimeout(() => { closeModal(); closeDrawer(); }, 900);
    $("#inv-topic").value = ""; $("#inv-scenario").value = "";
  } catch (e) {
    statusEl.textContent += `\n✖ ${e.message}`;
    toast("investigation failed: " + e.message, 4000);
  } finally { $("#inv-run").disabled = false; }
}

/* ---------------- wiring ---------------- */
$$(".tab").forEach(t => t.onclick = () => {
  $$(".tab").forEach(x => x.classList.toggle("active", x === t));
  $$(".view").forEach(v => v.classList.toggle("active", v.id === `view-${t.dataset.view}`));
  if (t.dataset.view === "timeline") loadTimeline();
  if (t.dataset.view === "runs") loadRuns();
});
$$(".dtab").forEach(t => t.onclick = () => showTab(t.dataset.tab));
$("#drawer-close").onclick = closeDrawer;
$("#scrim").onclick = closeDrawer;
$("#btn-investigate").onclick = openModal;
$("#inv-cancel").onclick = closeModal;
$("#inv-run").onclick = runInvestigate;
$("#f-class").onchange = loadSignals;
$("#f-status").onchange = loadSignals;
$("#f-demo").onchange = loadSignals;

refreshHealth();
setInterval(refreshHealth, 15000);
loadStats();
loadSignals();
