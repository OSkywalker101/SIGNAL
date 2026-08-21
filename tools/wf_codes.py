# All JavaScript snippets executed inside n8n Code nodes.
# Kept as plain strings (no f-strings) to avoid brace escaping issues.

UTILS = r"""
const UTIL = {
  esc(v) { if (v === null || v === undefined) return "''"; return String(v).replace(/'/g, "''"); },
  hash(s) { let h = 5381; s = String(s || ""); for (let i = 0; i < s.length; i++) { h = ((h << 5) + h + s.charCodeAt(i)) | 0; } return (h >>> 0).toString(16); },
  uuid() { return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, c => { const r = Math.random() * 16 | 0; return (c === "x" ? r : (r & 0x3 | 0x8)).toString(16); }); },
  clamp(x, a, b) { return Math.max(a, Math.min(b, x)); },
  tokens(t) { return String(t || "").toLowerCase().replace(/[^a-z0-9 ]/g, " ").split(/\s+/).filter(w => w.length > 2); },
  embed(text) {
    const v = new Array(384).fill(0);
    const toks = this.tokens(text);
    for (const w of toks) {
      let h = 2166136261;
      for (let i = 0; i < w.length; i++) { h ^= w.charCodeAt(i); h = Math.imul(h, 16777619); }
      const a = Math.abs(h) % 384; v[a] += 1;
      const b = Math.abs(Math.imul(h, 41) + 7) % 384; v[b] += 0.5;
    }
    const n = Math.sqrt(v.reduce((s, x) => s + x * x, 0)) || 1;
    return "[" + v.map(x => (x / n).toFixed(5)).join(",") + "]";
  },
  shingles(t, k) { const w = this.tokens(t); const out = []; for (let i = 0; i + k <= w.length; i++) out.push(w.slice(i, i + k).join(" ")); return new Set(out); },
  jaccard(a, b) { let inter = 0; for (const x of a) if (b.has(x)) inter++; const uni = a.size + b.size - inter; return uni ? inter / uni : 0; },
  overlapPct(a, b) { const A = new Set(a), B = new Set(b); if (!A.size) return 0; let hit = 0; for (const x of A) if (B.has(x)) hit++; return hit / A.size * 100; }
};
"""

INIT_RUN = UTILS + r"""
const body = ($input.first().json.body || $input.first().json) || {};
const mode = body.url ? "url" : (body.entities || body.domains ? "structured" : "natural");
return [{ json: {
  run_id: UTIL.uuid(),
  mode,
  topic: String(body.topic || body.query || body.text || "Untitled topic").slice(0, 200),
  url: body.url || null,
  scenario_key: body.scenario_key || null,
  demo_mode: ($env.DEMO_MODE === "true") || !!body.scenario_key,
  sensitivity: body.sensitivity || "standard",
  time_horizon_days: parseInt(body.time_horizon_days || "28", 10),
  requested_at: new Date().toISOString(),
}}];"""

OPEN_RUN_SQL = UTILS + r"""
const r = $input.first().json;
return [{ json: {
  sql: `INSERT INTO investigations (run_id, trigger_mode, input_payload, status)
        VALUES ('${r.run_id}', '${r.mode}', '${UTIL.esc(JSON.stringify({topic:r.topic,url:r.url,scenario:r.scenario_key}))}'::jsonb, 'RUNNING')
        ON CONFLICT (run_id) DO NOTHING RETURNING run_id;`
}}];"""

STRATEGIST_PROMPT = UTILS + r"""
const r = $("Initialize Run").first().json;
const prompt = [
  `Analyze this monitoring request and produce a research plan.`,
  `REQUEST: "${r.topic}"`,
  r.url ? `CONTEXT URL: ${r.url}` : ``,
  ``,
  `Return: topic (canonical), research_domains (4-8 from: companies government research jobs github news infrastructure community finance),`,
  `queries (6-10 search queries mixing DIRECT INDIRECT COMMERCIAL TECHNICAL REGULATORY ACADEMIC CONTRARIAN HISTORICAL angles),`,
  `entities (key organizations/technologies/people/locations to watch), counter_queries (3-5 queries that would DISPROVE an acceleration narrative),`,
  `time_horizon_days. Be specific to the topic's industry and geography.`
].filter(Boolean).join("\n");
return [{ json: { ...r, prompt } }];"""

PARSE_FALLBACK_PLAN = UTILS + r"""
const it = $input.first().json;
let plan = null;
try {
  const txt = it.choices && it.choices[0] && it.choices[0].message ? it.choices[0].message.content : (it.content || "");
  const m = String(txt).match(/\{[\s\S]*\}/);
  if (m) plan = JSON.parse(m[0]);
} catch (e) { plan = null; }
if (!plan || !plan.topic) {
  const t = $('Initialize Run').first().json.topic;
  plan = {
    topic: t,
    research_domains: ["news", "companies", "github", "research", "jobs", "government"],
    queries: [t, `${t} announcement`, `${t} investment`, `${t} hiring`, `${t} research paper`, `${t} regulation policy`],
    entities: [], counter_queries: [`${t} slowdown`, `${t} decline`, `${t} criticism`],
    time_horizon_days: "28"
  };
}
plan.provider = "openrouter";
const qs = (plan.queries || []).map(q => String(q));
plan.plan_topic = plan.topic;
plan.web_query = qs.slice(0, 3).join(" OR ");
plan.counter_query_joined = ((plan.counter_queries && plan.counter_queries.length) ? plan.counter_queries : [`${plan.topic} slowdown`, `${plan.topic} decline`]).join(" OR ");
return [{ json: plan }];"""

NORMALIZE_PLAN = UTILS + r"""
const p = $input.first().json.output || $input.first().json;
const init = $("Initialize Run").first().json;
const topic = p.topic || init.topic;
const queries = (p.queries || []).map(q => String(q)).filter(Boolean);
const counter = (p.counter_queries || []).map(q => String(q)).filter(Boolean);
return [{ json: {
  ...init,
  plan_topic: topic,
  primary_query: queries[0] || topic,
  web_query: queries.slice(0, 3).join(" OR "),
  counter_query_joined: (counter.length ? counter : [`${topic} slowdown`, `${topic} decline`]).join(" OR "),
  plan: {
    topic,
    provider: p.provider || "groq",
    research_domains: p.research_domains || [],
    queries,
    entities: p.entities || [],
    counter_queries: counter,
    time_horizon_days: parseInt(p.time_horizon_days || init.time_horizon_days || "28", 10)
  }
}}];"""

DEMO_FIXTURES = UTILS + r"""
// Deterministic DEMO SIMULATION sensor fixtures. Never presented as live data.
const init = $("Initialize Run").first().json;
const S = init.scenario_key || "infra_accel";
const D = (daysAgo) => new Date(Date.now() - daysAgo * 864e5).toISOString();
function src(title, pub, daysAgo, excerpt, type, extra) {
  return Object.assign({
    source_url: "demo://" + UTIL.hash(title),
    title, publisher: pub, author: null,
    published_at: D(daysAgo), retrieved_at: new Date().toISOString(),
    excerpt: excerpt || title, source_type: type || "news",
    channel: type === "policy" ? "policy" : (type === "research" ? "research" : (type === "github" ? "github" : (type === "community" ? "community" : (type === "jobs" ? "jobs" : "news")))),
    is_demo: true
  }, extra || {});
}
const F = {
  infra_accel: [
    src("YottaGrid announces 40,000-GPU AI compute cluster in Pune", "Reuters", 1, "YottaGrid said it will deploy 40,000 GPUs across two data centers in Pune, hiring 27 CUDA engineers to run inference workloads.", "news"),
    src("YottaGrid 40000 GPU cluster Pune expansion", "Bloomberg", 1, "Bloomberg confirms YottaGrid's Pune AI cluster plans first reported by Reuters.", "news"),
    src("YottaGrid Pune AI cluster: what we know", "TechCrunch", 1, "TechCrunch recaps the YottaGrid announcement circulating widely today.", "news"),
    src("Indian AI ministry clears Rs 10,000 crore compute procurement", "PIB Government", 2, "The cabinet approved national compute procurement including subsidy for private AI data centers.", "policy"),
    src("IndiaAI mission GPU tender attracts 14 bids", "Federal Register India Desk", 3, "Procurement records show 14 qualified bids for the national GPU tender.", "policy"),
    src("Hiring surge: CUDA and inference engineers in Bengaluru", "JobsWire", 2, "Postings for CUDA/inference roles jumped sharply this month across YottaGrid, Sarvam and Krutrim.", "jobs"),
    src("sarvam-2 open-source inference stack hits 5k stars", "GitHub Trending", 2, "Repository activity around Indian inference stacks accelerated; 38 new contributors this week.", "github"),
    src("Efficient low-resource inference for Indic languages", "arXiv", 4, "New paper benchmarks quantized inference on commodity GPUs with Indic language focus.", "research"),
    src("Discussion: is India building too much GPU capacity?", "Reddit r/india", 3, "Community debate on whether the compute build-out is sustainable.", "community"),
    src("YottaGrid partners with NVIDIA on AI factory reference design", "Company Press Release", 1, "Direct press release: partnership to standardize AI factory deployments in India.", "news"),
    src("Copy: YottaGrid partners with NVIDIA on AI factory", "Syndication Daily", 1, "Verbatim copy of the YottaGrid press release.", "news"),
    src("Copy2: YottaGrid-NVIDIA AI factory partnership announced", "Aggregator Hub", 1, "Another syndicated copy of the same press release.", "news")
  ],
  tech_shift: [
    src("Startups pivot from transformer-only stacks to hybrid SSM architectures", "The Information", 1, "Three funded labs confirmed migrating core inference to state-space hybrids.", "news"),
    src("SSM hybrid inference benchmark beats transformers at long context", "arXiv", 2, "Paper shows 3x throughput at 128k context for hybrid SSM models.", "research"),
    src("Hybrid-ssm-inference library crosses 8k stars", "GitHub Trending", 1, "Explosive growth of the reference implementation.", "github"),
    src("Chipmaker launches SSM accelerator block", "SemiAnalysis", 2, "New silicon targets state-space workloads specifically.", "news"),
    src("Are SSMs overhyped? A contrarian view", "Blogosphere", 3, "Argument that transformer inertia will prevail.", "community"),
    src("Agency drafts guidance on novel model architectures", "Policy Desk", 4, "Regulators begin evaluating evaluation criteria for non-transformer models.", "policy")
  ],
  false_signal: [
    src("MegaCorp AI announces massive data center", "Press Release Wire", 1, "Announcement claims 100,000 GPU facility.", "news"),
    src("MegaCorp AI data center announcement", "Syndicated A", 1, "Copy of press release.", "news"),
    src("MegaCorp AI data center press release reposted", "Syndicated B", 1, "Another copy.", "news"),
    src("Analysts doubt MegaCorp funding for announced data center", "Independent Wire", 2, "No permits filed; financing unverified; competitor analysis calls timeline implausible.", "news"),
    src("County records show no MegaCorp permit applications", "Public Records Desk", 2, "Official filings contradict the announcement.", "policy")
  ],
  collapse: [
    src("GPU rental prices slide as capacity outpaces demand", "Market Wire", 1, "Spot prices down 30% quarter-over-quarter.", "news"),
    src("Two AI data center projects quietly shelved", "Trade Journal", 2, "Permits withdrawn; staffing plans frozen.", "news"),
    src("Inference startup layoffs reverse earlier hiring boom", "JobsWire", 1, "Postings fall back toward baseline after Q2 spike.", "jobs"),
    src("Open-source inference activity cools", "GitHub Trending", 2, "Commit velocity down 45% from last month.", "github")
  ],
  reemergence: [
    src("Quantum error correction startup re-emerges with new backing", "Science Business", 1, "Previously dismissed team returns with credible hardware partner.", "news"),
    src("Logical qubit milestone replicated by second lab", "arXiv", 2, "Independent replication strengthens earlier contested claim.", "research"),
    src("Revisiting the dismissed quantum networking signal", "Analyst Blog", 3, "Pattern matches the signal we dismissed last quarter - now with independent confirmation.", "community")
  ]
};
const items = (F[S] || F.infra_accel).map(x => ({ json: x }));
items.forEach(i => { i.json.demo_note = "DEMO SIMULATION"; });
return items;"""

UNIFY_FEEDS = UTILS + r"""
// Normalize every sensor's output shape into one source schema.
const items = $input.all();
const out = [];
const seen = new Set();
const health = {};
for (const it of items) {
  const j = it.json || {};
  const ch = j.channel || "web";
  if (!health[ch]) health[ch] = { channel: ch, count: 0, errors: 0 };
  if (j.error || j.message && !j.title && !j.items && !j.hits) { health[ch].errors++; continue; }
  let batch = [];
  try {
    if (ch === "web") {
      const html = typeof j.data === "string" ? j.data : JSON.stringify(j);
      const re = /<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/g;
      let m, n = 0;
      while ((m = re.exec(html)) && n < 12) {
        let url = m[1];
        const u = url.match(/uddg=([^&]+)/);
        if (u) url = decodeURIComponent(u[1]);
        const title = m[2].replace(/<[^>]+>/g, "").trim();
        if (title && url.startsWith("http")) { batch.push({ title, source_url: url }); n++; }
      }
      batch = batch.map(b => ({ ...b, excerpt: "", publisher: (b.source_url.split("/")[2] || "").replace("www.", "") }));
    } else if (ch === "news") {
      batch = [{ title: j.title, source_url: j.link, publisher: (j.creator || j.link || "").slice(0, 60), published_at: j.pubDate, excerpt: j.contentSnippet || (j.content || "").replace(/<[^>]+>/g, "").slice(0, 300) }];
    } else if (ch === "github") {
      batch = (j.items || []).map(r => ({ title: r.full_name + ": " + (r.description || ""), source_url: r.html_url, publisher: "GitHub", author: r.owner && r.owner.login, published_at: r.pushed_at, excerpt: `stars=${r.stargazers_count} pushed=${r.pushed_at} lang=${r.language}`, source_type: "github" }));
    } else if (ch === "jobs") {
      batch = (j.hits || []).map(h => ({ title: h.title, source_url: h.url || ("https://news.ycombinator.com/item?id=" + h.objectID), publisher: "Hacker News", author: h.author, published_at: h.created_at, excerpt: (h.story_text || h.title || ""), source_type: "jobs" }));
    } else if (ch === "policy") {
      batch = (j.results || []).map(d => ({ title: d.title, source_url: d.html_url, publisher: (d.agencies && d.agencies[0] && d.agencies[0].name) || "Federal Register", published_at: d.publication_date, excerpt: d.abstract || "", source_type: "policy" }));
    } else if (ch === "research") {
      const xml = typeof j.data === "string" ? j.data : "";
      const entries = xml.split("<entry>").slice(1);
      batch = entries.map(e => ({
        title: (e.match(/<title>([\s\S]*?)<\/title>/) || [, ""])[1].trim(),
        source_url: (e.match(/<id>([\s\S]*?)<\/id>/) || [, ""])[1].trim(),
        publisher: "arXiv",
        published_at: (e.match(/<published>([\s\S]*?)<\/published>/) || [, ""])[1].trim(),
        excerpt: ((e.match(/<summary>([\s\S]*?)<\/summary>/) || [, ""])[1] || "").trim().slice(0, 300),
        source_type: "research"
      }));
    } else if (ch === "community") {
      batch = ((j.data || {}).children || []).map(c => ({ title: c.data.title, source_url: "https://reddit.com" + c.data.permalink, publisher: "r/" + c.data.subreddit, author: c.data.author, published_at: c.data.created_utc ? new Date(c.data.created_utc * 1000).toISOString() : null, excerpt: (c.data.selftext || "").slice(0, 300), source_type: "community" }));
    }
  } catch (e) { health[ch].errors++; continue; }
  for (const b of batch) {
    if (!b || !b.title || !b.source_url || !String(b.source_url).startsWith("http")) continue;
    const uh = UTIL.hash(b.source_url);
    if (seen.has(uh)) continue;
    seen.add(uh);
    health[ch].count++;
    out.push({ json: {
      source_url: b.source_url, url_hash: uh,
      title: String(b.title).slice(0, 300),
      publisher: (b.publisher || "").slice(0, 120) || null,
      author: b.author || null,
      published_at: b.published_at || null,
      excerpt: String(b.excerpt || "").slice(0, 500),
      source_type: b.source_type || (ch === "news" ? "news" : ch),
      channel: ch,
      credibility_base: ({ policy: 0.92, research: 0.88, github: 0.80, news: 0.78, jobs: 0.72, community: 0.58, web: 0.62 })[ch] || 0.6,
      fingerprint: UTIL.hash(String(b.title) + "|" + String(b.excerpt || "").slice(0, 200))
    }});
  }
}
if (!out.length) out.push({ json: { _empty_corpus: true, health } });
else out[0].json._health = health;
return out;"""

PREPARE_CRAWL_QUEUE = UTILS + r"""
const corpus = $input.all().filter(i => i.json.source_url && !i.json.is_demo);
corpus.sort((a, b) => String(b.json.excerpt || "").length - String(a.json.excerpt || "").length);
const queue = corpus.slice(0, 8).map(i => ({ json: { ...i.json, crawl_url: i.json.source_url, run_id: $("Initialize Run").first().json.run_id } }));
return queue.length ? queue : [{ json: { _no_crawl: true, run_id: $("Initialize Run").first().json.run_id } }];"""

ENRICH_CORPUS = UTILS + r"""
// Merge cached crawled page text back into the corpus.
let cached = [];
try { cached = $("Load Cached Pages").all().map(i => i.json.payload || {}); } catch (e) {}
const byUrl = {};
for (const c of cached) { if (c && c.source_url) byUrl[c.source_url] = c; }
const corpusIn = $("Cap Corpus").all()
  .filter(i => i.json.source_url)
  .map(i => {
    const c = byUrl[i.json.source_url];
    if (c && c.page_text) {
      i.json.crawled_text = String(c.page_text).slice(0, 1500);
      i.json.page_title = c.page_title || null;
      i.json.crawl_ok = true;
    } else { i.json.crawl_ok = false; }
    return i;
  });
if (!corpusIn.length) throw new Error("Empty corpus after enrichment");
return corpusIn;"""
EVIDENCE_LAB = UTILS + r"""
// Rule-based atomic claim extraction. Every claim references its source.
const corpus = $input.all().filter(i => i.json.title);
const PATTERNS = [
  { action: "hires", re: /\b(hire[sd]?|hiring|recruit(s|ing)?|headcount|job postings?|vacanc(y|ies)|engineers?|roles?)\b/i, objHint: /(?:hiring|hires)\s+([\w\s-]{3,40}?)(?:\s+(?:this|across|to|for|in)\b|$)/i },
  { action: "invests", re: /\b(invest(s|ment)?|funding|raised|series [abc]|round of|crore|billion|million|\$\s?\d)/i },
  { action: "expands", re: /\b(expand(s|ing)?|new facility|data ?center|capacity|cluster|build-?out)\b/i },
  { action: "partners", re: /\b(partner(s|ship|ing)?|collaborat(e|ion)|moU|alliance)\b/i },
  { action: "launches", re: /\b(launch(es|ed)?|unveil(s|ed)?|release[sd]?|ships?|announce[sd]?)\b/i },
  { action: "procures", re: /\b(procure(s|ment)?|tender|rfp|contract awarded|sanction(ed)?)\b/i },
  { action: "publishes_research", re: /\b(paper|study|benchmark|researchers?|arxiv|preprint)\b/i },
  { action: "warns_or_declines", re: /\b(slowdown|decline|layoff|shelved|withdrawn|cool(s|ed)?|slide|falls?)\b/i }
];
const claims = [];
for (const item of corpus) {
  const d = item.json;
  const text = `${d.title}. ${d.excerpt || ""} ${d.crawled_text || ""}`;
  for (const p of PATTERNS) {
    if (!p.re.test(text)) continue;
    const qtyMatch = text.match(/\b(\d{1,3}(?:,\d{3})+|\d{1,6})\s*(k\b|gpu|engineers?|jobs?|crore|million|billion|stars?|contributors?|qubits?|nodes?)?/i);
    const actorGuess = (d.title.match(/^([A-Z][\w&.-]+(?:\s+[A-Z][\w&.-]+){0,3})/) || [])[1] || d.publisher || "Unknown actor";
    claims.push({
      statement: d.title,
      actor: actorGuess.trim(),
      action: p.action,
      object: (p.objHint && (text.match(p.objHint) || [])[1] || d.title).toString().slice(0, 80),
      quantity: qtyMatch ? parseFloat(qtyMatch[1].replace(/,/g, "")) : null,
      quantity_unit: qtyMatch && qtyMatch[2] ? qtyMatch[2].trim() : null,
      claimed_at: d.published_at || new Date().toISOString(),
      source_url: d.source_url,
      channel: d.channel,
      is_demo: !!d.is_demo
    });
    break; // one strongest claim per document keeps precision high
  }
}
if (!claims.length) claims.push({ statement: "(no atomic claims extracted)", actor: null, action: "none", object: null, quantity: null, claimed_at: new Date().toISOString(), source_url: null, channel: "none", is_demo: false });
return [{ json: { claims, corpus: corpus.map(i => i.json) } }];"""

ENTITY_RESOLUTION = UTILS + r"""
// Alias-aware canonical entity resolution.
const ALIAS = {
  "nvidia": ["nvidia corp", "nvidia corporation", "nvda"],
  "alphabet": ["google", "google llc", "google inc"],
  "meta": ["facebook", "meta platforms"],
  "microsoft": ["msft"],
  "tsmc": ["taiwan semiconductor"],
  "yottagrid": ["yotta grid", "yottagrid inc"],
  "openai": ["open ai"]
};
const TYPE_HINTS = [
  [/gpu|cuda|inference|transformer|ssm|quantum|model|chip|stack|framework|library/i, "technology"],
  [/ministry|government|agency|commission|parliament|regulator|cabinet|federal/i, "government"],
  [/university|lab|institute|arxiv|journal/i, "research_topic"],
  [/city|bengaluru|pune|india|valley|county/i, "location"]
];
function canonical(name) {
  let n = String(name || "").toLowerCase().trim()
    .replace(/\b(inc|corp|corporation|ltd|llc|gmbh|pvt|private limited|limited|company|group|holdings|plc)\b\.?/g, "")
    .replace(/[^a-z0-9 ]/g, " ").replace(/\s+/g, " ").trim();
  for (const [canon, alts] of Object.entries(ALIAS)) if (alts.includes(n)) return canon;
  return n || "unknown";
}
function guessType(n) {
  for (const [re, t] of TYPE_HINTS) if (re.test(n)) return t;
  return "company";
}
const src = $input.first().json;
const claims = src.claims;
const ents = {};
for (const c of claims) {
  for (const raw of [c.actor, c.object]) {
    if (!raw || raw.length < 3) continue;
    const can = canonical(raw);
    if (!ents[can]) ents[can] = { canonical_name: can, entity_type: guessType(can), aliases: new Set(), mentions: 0 };
    ents[can].mentions++;
    if (raw.toLowerCase() !== can) ents[can].aliases.add(String(raw).toLowerCase());
  }
  c.actor_canonical = canonical(c.actor);
  c.object_canonical = canonical(c.object);
}
const list = Object.entries(ents).map(([name, e]) => ({ name, type: e.entity_type, mentions: e.mentions, aliases: [...e.aliases] }));
return [{ json: { claims, entities: list, corpus: src.corpus } }];"""

RELATIONSHIP_GRAPH = UTILS + r"""
const { claims, entities, corpus } = $input.first().json;
const VERB = { hires: "hires", invests: "invests_in", expands: "expands", partners: "partners_with", launches: "announces", procures: "procures", publishes_research: "appears_in", warns_or_declines: "contradicts_growth_of" };
const edges = {};
for (const c of claims) {
  if (!c.actor_canonical || !c.object_canonical || c.actor_canonical === c.object_canonical) continue;
  const key = `${c.actor_canonical}|${VERB[c.action] || "relates_to"}|${c.object_canonical}`;
  if (!edges[key]) edges[key] = { subject: c.actor_canonical, predicate: VERB[c.action] || "relates_to", object: c.object_canonical, weight: 0, evidence_count: 0, channels: new Set() };
  edges[key].weight += 0.25; edges[key].evidence_count += 1; edges[key].channels.add(c.channel);
}
const rels = Object.values(edges).map(e => ({ ...e, weight: Math.min(1, e.weight), channels: [...e.channels] }));
rels.sort((a, b) => b.evidence_count - a.evidence_count);
return [{ json: { claims, entities, corpus, relationships: rels.slice(0, 60) } }];"""

TEMPORAL_DELTA = UTILS + r"""
// TIME MACHINE: compare NOW vs PAST observations.
const { claims, entities, relationships, corpus } = $("🔗 RELATIONSHIP GRAPH").first().json;
let history = [];
try { history = $("⏱️ TIME MACHINE — Load History").all().map(i => i.json).filter(h => h && h.week && h.week !== "(no history)" && isFinite(parseFloat(h.avg_val))); } catch (e) {}
let knownRels = [];
try { knownRels = $("Load Known Entities").all().map(i => i.json).filter(r => r && r.subject); } catch (e) {}
const init = $("Initialize Run").first().json;

const curVolume = claims.filter(c => c.action !== "none").length;
const weeklyTotals = {};
for (const h of history) { const w = h.week; weeklyTotals[w] = (weeklyTotals[w] || 0) + parseFloat(h.avg_val || 0); }
const weeks = Object.keys(weeklyTotals).sort();
const baseline = weeks.length ? weeks.reduce((s, w) => s + weeklyTotals[w], 0) / weeks.length : null;
const prevWeek = weeks.length >= 2 ? weeklyTotals[weeks[weeks.length - 2]] : baseline;
const velocity_pct = baseline ? ((curVolume - baseline) / Math.max(baseline, 0.001)) * 100 : (curVolume > 0 ? 100 : 0);
const accel_bonus = prevWeek && baseline ? (((baseline - prevWeek) / Math.max(prevWeek, 0.001)) * 20) : 0;

const knownNames = new Set();
for (const r of knownRels) { knownNames.add(r.subject); knownNames.add(r.object); }
const newEntities = entities.filter(e => !knownNames.has(e.name));
const novelty_score = UTIL.clamp(newEntities.length * 12 + (weeks.length === 0 ? 25 : 0), 0, 100);

const channelsNow = new Set(claims.map(c => c.channel).filter(c => c !== "none"));
const distinct_channels = channelsNow.size;
const newTerms = entities.filter(e => e.type === "technology" && !knownNames.has(e.name)).length;

return [{ json: {
  claims, entities, relationships, corpus,
  probe_embedding: UTIL.embed(`${init.topic} ${(claims[0] && claims[0].statement) || ""}`),
  temporal: {
    current_volume: curVolume,
    historical_baseline: baseline === null ? null : Math.round(baseline * 100) / 100,
    history_weeks: weeks.length,
    velocity_pct: Math.round(velocity_pct * 10) / 10,
    acceleration_bonus: Math.round(accel_bonus * 10) / 10,
    new_entity_count: newEntities.length,
    new_entities: newEntities.slice(0, 12).map(e => e.name),
    new_terms_count: newTerms,
    distinct_channels,
    novelty_score: Math.round(novelty_score)
  },
  init
}}];"""

HYPO_CONTEXT = UTILS + r"""
const d = $input.first().json;
const topClaims = d.claims.filter(c => c.action !== "none").slice(0, 10).map(c => `[${c.channel}] ${c.actor}: ${c.statement}`);
const ctx = [
  `TOPIC: ${d.init.topic}`,
  `CURRENT SIGNAL VOLUME: ${d.temporal.current_volume} claims vs historical baseline ${d.temporal.historical_baseline}`,
  `VELOCITY: ${d.temporal.velocity_pct}% vs baseline; ACCELERATION BONUS: ${d.temporal.acceleration_bonus}`,
  `NEW ENTITIES (${d.temporal.new_entity_count}): ${d.temporal.new_entities.join(", ") || "none"}`,
  `CHANNELS ACTIVE (${d.temporal.distinct_channels}): ${[...new Set(d.claims.map(c => c.channel))].join(", ")}`,
  `TOP EVIDENCE:`,
  topClaims.join("\n")
].join("\n");
return [{ json: { ...d, hypothesis_context: ctx + `\n\nGenerate exactly 3 competing hypotheses as a JSON array. Each item: {"statement": "...", "prior_confidence": <number 5-95>, "reasoning": "one sentence citing the evidence above"}. H1 should be the most consequential interpretation consistent with evidence; H2 a mundane alternative; H3 a skeptical/adversarial alternative. Output ONLY the JSON array.` } }];"""

PARSE_HYPOTHESES = UTILS + r"""
const d = $("Build Hypothesis Context").first().json;
let hyps = null;
try {
  const txt = $input.first().json.text || "";
  const m = String(txt).match(/\[[\s\S]*\]/);
  if (m) hyps = JSON.parse(m[0]);
} catch (e) { hyps = null; }
if (!Array.isArray(hyps) || !hyps.length) {
  hyps = [
    { statement: `${d.init.topic} ecosystem entering a genuine acceleration phase`, prior_confidence: 58, reasoning: "Multiple channels active simultaneously with positive velocity." },
    { statement: `Short-term spike; cyclical or seasonal noise`, prior_confidence: 34, reasoning: "Volume alone does not establish durable change." },
    { statement: `Coordinated publicity inflating perceived momentum`, prior_confidence: 26, reasoning: "Derivative coverage can masquerade as independent confirmation." }
  ];
}
hyps = hyps.slice(0, 3).map((h, i) => ({
  rank: i + 1,
  statement: String(h.statement || "Unnamed hypothesis").slice(0, 240),
  prior_confidence: UTIL.clamp(parseFloat(h.prior_confidence) || 50, 5, 95),
  reasoning: String(h.reasoning || "").slice(0, 400),
  status: "candidate"
}));
return [{ json: { ...d, hypotheses: hyps } }];"""

RANK_HYPOTHESES = UTILS + r"""
// Rank by prior confidence (desc), keep top 3.
const d = $input.first().json;
const hyps = (d.hypotheses || []).slice()
  .sort((a, b) => (b.prior_confidence || 0) - (a.prior_confidence || 0))
  .slice(0, 3)
  .map((h, i) => ({ ...h, rank: i + 1 }));
return [{ json: { ...d, hypotheses: hyps } }];"""

COUNTER_FORGE = UTILS + r"""
const d = $input.first().json;
const lead = d.hypotheses[0];
const t = d.init.topic;
const queries = [
  `${t} slowdown`, `${t} decline`, `${t} layoffs`,
  `${t} cancelled OR postponed`, `${t} criticism OR failure OR doubts`
];
return [{ json: { ...d, leading_hypothesis: lead, redteam_queries: queries } }];"""

COUNTER_SWEEP = UTILS + r"""
// Adversarial search sweep: actively hunt disconfirming evidence.
const d = $input.first().json;
async function ddg(q) {
  try {
    const res = await this.helpers.httpRequest({
      url: "https://html.duckduckgo.com/html/?q=" + encodeURIComponent(q),
      method: "GET", headers: { "User-Agent": "Mozilla/5.0 (compatible; SignalBot/1.0)" }, json: false
    });
    const html = typeof res === "string" ? res : JSON.stringify(res);
    const results = [];
    const re = /<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/g;
    let m, n = 0;
    while ((m = re.exec(html)) && n < 5) {
      let url = m[1]; const u = url.match(/uddg=([^&]+)/); if (u) url = decodeURIComponent(u[1]);
      const title = m[2].replace(/<[^>]+>/g, "").trim();
      if (title && url.startsWith("http")) { results.push({ title, url }); n++; }
    }
    return { query: q, ok: true, results };
  } catch (e) { return { query: q, ok: false, error: String(e).slice(0, 120), results: [] }; }
}
const sweeps = [];
for (const q of d.redteam_queries) sweeps.push(await ddg.call(this, q));
return [{ json: { ...d, redteam_sweeps: sweeps } }];"""

ANALYZE_HOSTILE = UTILS + r"""
const d = $input.first().json;
const HOSTILE = /(slowdown|decline|layoff|cancel|postpone|delay|loss|lawsuit|fraud|recall|den(y|ies)|downturn|cutback|freeze|shelv|withdraw|doubt|fail|slump|plunge)/i;
const SUPPORTIVE = /(growth|expand|record|surge|boost|accelerat|milestone|breakthrough|wins?|soars?)/i;
const contradictions = [], supporting = [], unresolved = [];
for (const sweep of d.redteam_sweeps) {
  for (const r of sweep.results || []) {
    const text = r.title;
    if (HOSTILE.test(text)) contradictions.push({ query: sweep.query, title: text.slice(0, 220), url: r.url, strength: UTIL.clamp(0.45 + (text.match(new RegExp(HOSTILE.source, "gi")) || []).length * 0.12, 0, 0.9) });
    else if (SUPPORTIVE.test(text)) supporting.push({ query: sweep.query, title: text.slice(0, 220), url: r.url });
    else unresolved.push({ query: sweep.query, title: text.slice(0, 160), url: r.url });
  }
}
const searches_executed = d.redteam_sweeps.filter(s => s.ok).length;
return [{ json: { ...d, redteam: {
  searches_planned: d.redteam_queries.length,
  searches_executed,
  contradiction_count: contradictions.length,
  supporting_count: supporting.length,
  unresolved_count: unresolved.length,
  contradictions: contradictions.slice(0, 8),
  supporting: supporting.slice(0, 5),
  unresolved: unresolved.slice(0, 5),
  avg_hostile_strength: contradictions.length ? contradictions.reduce((s, c) => s + c.strength, 0) / contradictions.length : 0
}}}];"""

CONFIDENCE_ADJ = UTILS + r"""
const d = $input.first().json;
const rt = d.redteam;
const hyps = d.hypotheses.map((h, idx) => {
  let posterior = h.prior_confidence;
  if (idx === 0) {
    posterior -= 18 * rt.avg_hostile_strength;
    posterior -= 6 * Math.min(rt.contradiction_count, 3);
    posterior += 4 * Math.min(rt.supporting_count, 2);
  } else {
    posterior += 3 * Math.min(rt.contradiction_count, 2);
  }
  posterior = UTIL.clamp(Math.round(posterior), 3, 97);
  return { ...h, posterior_confidence: posterior, confidence_change: posterior - h.prior_confidence };
});
hyps.sort((a, b) => b.posterior_confidence - a.posterior_confidence);
hyps.forEach((h, i) => { h.rank = i + 1; h.status = i === 0 ? "leading" : "candidate"; if (h.posterior_confidence < 22) h.status = "disproved"; });
return [{ json: { ...d, hypotheses: hyps, redteam: { ...rt, confidence_change: hyps[0].confidence_change } } }];"""

SOURCE_FORENSICS = UTILS + r"""
// Collapse derivative coverage into underlying events.
const d = $input.first().json;
const docs = (d.corpus || []).filter(c => c.title);
const K = 3;
const shingleSets = docs.map(doc => UTIL.shingles(`${doc.title} ${doc.excerpt || ""}`, K));
const parent = docs.map((_, i) => i);
function find(x) { while (parent[x] !== x) { parent[x] = parent[parent[x]]; x = parent[x]; } return x; }
function union(a, b) { parent[find(a)] = find(b); }
for (let i = 0; i < docs.length; i++) {
  for (let j = i + 1; j < docs.length; j++) {
    const sim = UTIL.jaccard(shingleSets[i], shingleSets[j]);
    const di = (docs[i].source_url || "").split("/")[2], dj = (docs[j].source_url || "").split("/")[2];
    const tSim = UTIL.overlapPct(UTIL.tokens(docs[i].title), UTIL.tokens(docs[j].title));
    const near48 = Math.abs((new Date(docs[i].published_at || 0)) - (new Date(docs[j].published_at || 0))) < 48 * 36e5;
    if (sim >= 0.55 || (di && di === dj && tSim >= 60 && near48) || tSim >= 75) union(i, j);
  }
}
const clusters = {};
docs.forEach((doc, i) => { const g = find(i); (clusters[g] = clusters[g] || []).push(i); });
let gid = 0;
const groupOf = {};
const derivative = new Set();
const underlyingEvents = [];
for (const [rootIdx, members] of Object.entries(clusters)) {
  gid++;
  const label = "ev_" + gid;
  members.forEach(mi => { groupOf[mi] = label; });
  if (members.length > 1) {
    const sorted = members.slice().sort((a, b) => new Date(docs[a].published_at || 0) - new Date(docs[b].published_at || 0));
    sorted.slice(1).forEach(mi => derivative.add(mi));
  }
  underlyingEvents.push({ event_group: label, articles: members.length, publishers: [...new Set(members.map(mi => docs[mi].publisher))] });
}
docs.forEach((doc, i) => {
  doc.independence_group = groupOf[i];
  doc.derivative = derivative.has(i);
});
const uniqueDomains = new Set(docs.map(d => (d.source_url || "").split("/")[2]));
return [{ json: { ...d, corpus: docs, forensics: {
  articles_found: docs.length,
  underlying_events: Object.keys(clusters).length,
  independent_sources: Object.keys(clusters).length,
  derivative_articles: derivative.size,
  duplicates_removed: derivative.size,
  unique_domains: uniqueDomains.size,
  clusters: underlyingEvents.slice(0, 10)
}}}];"""

APPLY_CREDIBILITY = UTILS + r"""
const d = $input.first().json;
const ADJ = { primary_announcement: 0.05, independent_analysis: 0.15, aggregator_syndication: -0.20, opinion_discussion: -0.10 };
const corpus = d.corpus.map(c => {
  const cat = c.category || c.class || c.className || c.label || null;
  if (cat && ADJ[cat] !== undefined) {
    c.credibility_score = UTIL.clamp((c.credibility_base || 0.6) + ADJ[cat], 0.05, 0.98);
    c.provenance_class = cat;
  } else { c.credibility_score = c.credibility_base || 0.6; c.provenance_class = cat || "unclassified"; }
  c.primary_or_secondary = (cat === "primary_announcement") ? "primary" : "secondary";
  return c;
});
return [{ json: { ...d, corpus } }];"""

EVIDENCE_VALIDATION = UTILS + r"""
// Every hypothesis must trace to claim-level evidence or be marked unsupported.
const d = $input.first().json;
const claimTexts = d.claims.map(c => UTIL.tokens(c.statement));
const STOP = new Set(["the","and","for","with","that","this","from","are","was","were","has","have","had","not","its","their","will","would","could","into","over","under","about"]);
const hyps = d.hypotheses.map(h => {
  const ht = UTIL.tokens(h.statement).filter(t => !STOP.has(t));
  let best = 0, bestClaim = null;
  claimTexts.forEach((ct, i) => { const o = UTIL.overlapPct(ht, ct); if (o > best) { best = o; bestClaim = d.claims[i]; } });
  h.supported = best >= 30;
  h.support_claim = bestClaim ? bestClaim.statement : null;
  h.support_source = bestClaim ? bestClaim.source_url : null;
  h.evidence_overlap_pct = Math.round(best);
  return h;
});
return [{ json: { ...d, hypotheses: hyps } }];"""

SIGNAL_JUDGE = UTILS + r"""
// ⚖️ DETERMINISTIC SCORING — the LLM never invents the score.
const d = $input.first().json;
let W = { novelty: 0.15, acceleration: 0.20, source_diversity: 0.15, source_quality: 0.15, cross_domain: 0.20, independence: 0.10, contradiction: 0.05 };
try { if ($env.SIGNAL_SCORING_WEIGHTS) { const p = {}; $env.SIGNAL_SCORING_WEIGHTS.split(",").forEach(kv => { const [k, v] = kv.split(":"); p[k.trim()] = parseFloat(v); }); W = { ...W, ...p }; } } catch (e) {}

const f = d.forensics;
const avgCred = f.articles_found ? d.corpus.reduce((s, c) => s + (c.credibility_score || 0.6), 0) / f.articles_found : 0.5;
const source_quality_score = Math.round(avgCred * 100);
const independence_score = Math.round(UTIL.clamp((f.independent_sources / Math.max(f.articles_found, 1)) * 140 + f.unique_domains * 4, 0, 100));
const acceleration_score = Math.round(UTIL.clamp(50 + d.temporal.velocity_pct * 0.55 + d.temporal.acceleration_bonus, 0, 100));
const novelty_score = d.temporal.novelty_score;
const cross_domain_score = Math.min(100, d.temporal.distinct_channels * 22);
const contradiction_score = Math.round(UTIL.clamp(d.redteam.avg_hostile_strength * 100, 0, 100));

const dna = { source_quality: source_quality_score, independence: independence_score, acceleration: acceleration_score, novelty: novelty_score, cross_domain: cross_domain_score, contradiction: contradiction_score };
const score = Math.round(
  W.novelty * novelty_score +
  W.acceleration * acceleration_score +
  W.source_diversity * Math.min(100, f.unique_domains * 12) +
  W.source_quality * source_quality_score +
  W.cross_domain * cross_domain_score +
  W.independence * independence_score +
  W.contradiction * (100 - contradiction_score)
);
const finalScore = UTIL.clamp(score, 0, 100);
const classification = finalScore <= 30 ? "NOISE" : finalScore <= 50 ? "WEAK" : finalScore <= 70 ? "EMERGING" : finalScore <= 85 ? "SIGNIFICANT" : "CRITICAL";

const supportedRate = d.hypotheses.filter(h => h.supported).length / Math.max(d.hypotheses.length, 1);
const confidence = Math.round(UTIL.clamp(0.35 * independence_score + 0.25 * source_quality_score + 0.25 * supportedRate * 100 + 0.15 * (100 - contradiction_score), 0, 99));

const lead = d.hypotheses.find(h => h.rank === 1) || d.hypotheses[0];
const invalidators = [
  `Coverage volume for "${d.init.topic}" returns to historical baseline within one week`,
  `Independent outlets stop adding NEW reporting (only syndicated copies appear)`,
  d.redteam.contradictions[0] ? `Contradicting report proves accurate: "${d.redteam.contradictions[0].title.slice(0, 90)}"` : `No independent confirmation emerges within the time horizon`,
  `Key named entities issue denials or retractions`,
  `Downstream indicators (hiring/GitHub/procurement) flatten or reverse`
];

return [{ json: { ...d, verdict: {
  signal_score: finalScore, classification, confidence, dna, weights_used: W,
  leading_hypothesis: lead ? lead.statement : null,
  invalidators
}}}];"""

PERSIST_SIGNAL_SQL = UTILS + r"""
const d = $input.first().json;
const v = d.verdict;
const title = (v.leading_hypothesis || `${d.init.topic} activity shift`).slice(0, 180);
const status = v.signal_score >= 51 ? "EMERGING" : "DETECTED";
const sql = `INSERT INTO signals
 (title, topic, input_mode, status, classification, signal_score, confidence, dna, velocity, acceleration,
  articles_found, underlying_events, independent_sources, is_demo, scenario_key, embedding, metadata)
 VALUES (
  '${UTIL.esc(title)}', '${UTIL.esc(d.init.topic)}', '${d.init.mode}', '${status}', '${v.classification}',
  ${v.signal_score}, ${v.confidence}, '${UTIL.esc(JSON.stringify(v.dna))}'::jsonb,
  ${d.temporal.velocity_pct}, ${d.temporal.acceleration_bonus},
  ${f0(d)}, ${d.forensics.underlying_events}, ${d.forensics.independent_sources},
  ${d.init.demo_mode}, ${d.init.scenario_key ? `'${UTIL.esc(d.init.scenario_key)}'` : "NULL"},
  '${UTIL.embed(title + " " + d.init.topic)}'::vector,
  '${UTIL.esc(JSON.stringify({ run_id: d.init.run_id, invalidators: v.invalidators }))}'::jsonb
 ) RETURNING signal_id;`;
function f0(dd) { return dd.forensics.articles_found; }
return [{ json: { sql, stage: "signal_core" } }];"""

BUILD_BULK_WRITES = UTILS + r"""
// Build ordered SQL statements for every memory table.
// Context comes from the judge node (the upstream Postgres RETURNING replaces item context).
const d = $("⚖️ SIGNAL JUDGE — Deterministic Score").first().json;
let sigId = null;
try { sigId = $("Persist Signal Core").first().json.signal_id; } catch (e) {}
const stmts = [];
const esc = UTIL.esc;
if (sigId) {
  // sources
  const rows = d.corpus.slice(0, 80).map(c =>
    `('${esc(c.source_url)}','${UTIL.hash(c.source_url)}','${esc(c.source_type)}','${esc(c.publisher)}',${c.author ? `'${esc(c.author)}'` : "NULL"},${c.published_at ? `'${esc(new Date(c.published_at).toISOString())}'` : "NULL"},'${(c.primary_or_secondary === "primary" ? "primary" : "secondary")}',${c.credibility_score || 0.6},'${esc(c.independence_group)}','${esc(c.title)}','${esc((c.excerpt || "").slice(0, 400))}','${esc(c.content_hash || UTIL.hash(String(c.title) + "|" + String(c.excerpt || "")))}','${d.init.run_id}','${esc(JSON.stringify({ derivative: !!c.derivative, is_demo: !!c.is_demo }))}'::jsonb)`);
  for (let i = 0; i < rows.length; i += 40) {
    stmts.push({ sql: `INSERT INTO sources (source_url,url_hash,source_type,publisher,author,published_at,primary_or_secondary,credibility_score,independence_group,title,content_excerpt,content_hash,run_id,metadata) VALUES ${rows.slice(i, i + 40).join(",")} ON CONFLICT (url_hash) DO NOTHING;`, stage: "sources" });
  }
  // claims + events
  const goodClaims = d.claims.filter(c => c.action !== "none").slice(0, 60);
  if (goodClaims.length) {
    const cr = goodClaims.map(c => `('${sigId}','${d.init.run_id}','${esc(c.actor)}','${esc(c.action)}','${esc(c.object)}',${c.quantity === null ? "NULL" : c.quantity},${c.quantity_unit ? `'${esc(c.quantity_unit)}'` : "NULL"},'${esc(c.statement)}','unverified','${UTIL.embed(c.statement)}'::vector)`);
    stmts.push({ sql: `INSERT INTO claims (signal_id,run_id,actor,action,object,quantity,quantity_unit,statement,verification,embedding) VALUES ${cr.join(",")};`, stage: "claims" });
    const er = goodClaims.map(c => `('${sigId}','${esc(c.actor)}','${esc(c.action)}','${esc(c.object)}',${c.quantity === null ? "NULL" : c.quantity},${c.claimed_at ? `'${esc(new Date(c.claimed_at).toISOString())}'` : "NULL"},0.6,'${UTIL.embed(c.statement)}'::vector)`);
    stmts.push({ sql: `INSERT INTO events (signal_id,actor,action,object,quantity,occurred_at,confidence,embedding) VALUES ${er.join(",")};`, stage: "events" });
  }
  // observations per channel
  const byCh = {};
  d.claims.forEach(c => { if (c.channel !== "none") byCh[c.channel] = (byCh[c.channel] || 0) + 1; });
  const obs = Object.entries(byCh).map(([ch, n]) => `('${sigId}','${d.init.run_id}','${esc(ch)}','volume',${n},now(),now(),now(),'{}'::jsonb)`);
  if (obs.length) stmts.push({ sql: `INSERT INTO observations (signal_id,run_id,channel,metric,value,observed_at,window_start,window_end,details) VALUES ${obs.join(",")};`, stage: "observations" });
  // relationships
  if (d.relationships.length) {
    const rr = d.relationships.slice(0, 50).map(r => `('${sigId}','${esc(r.subject)}','${esc(r.predicate)}','${esc(r.object)}',${r.weight},${r.evidence_count},${d.temporal.new_entities.includes(r.subject)})`);
    stmts.push({ sql: `INSERT INTO relationships (signal_id,subject,predicate,object,weight,evidence_count,is_new) VALUES ${rr.join(",")};`, stage: "relationships" });
  }
  // hypotheses
  const hr = d.hypotheses.map(h => `('${sigId}',${h.rank},'${esc(h.statement)}',${h.prior_confidence},${h.posterior_confidence},'${h.status}','${esc(h.reasoning)}')`);
  stmts.push({ sql: `INSERT INTO hypotheses (signal_id,rank,statement,prior_confidence,posterior_confidence,status,reasoning) VALUES ${hr.join(",")};`, stage: "hypotheses" });
  // invalidators
  const ir = d.verdict.invalidators.map(t => `('${sigId}','${esc(t)}')`);
  stmts.push({ sql: `INSERT INTO invalidators (signal_id,condition_text) VALUES ${ir.join(",")};`, stage: "invalidators" });
  // signal history
  stmts.push({ sql: `INSERT INTO signal_history (signal_id,score,confidence,status,note) VALUES ('${sigId}',${d.verdict.signal_score},${d.verdict.confidence},'${d.verdict.classification}','pipeline run ${d.init.run_id.slice(0, 8)}');`, stage: "history" });
  // notifications
  let tgState = "skipped", tgDetail = "TELEGRAM_BOT_TOKEN not configured";
  try { if ($env.TELEGRAM_BOT_TOKEN) { tgState = "sent"; tgDetail = "alert dispatched via HTTP node"; } } catch (e) {}
  stmts.push({ sql: `INSERT INTO notifications (signal_id,channel,severity,message,status,detail,sent_at) VALUES ('${sigId}','telegram','${d.verdict.classification.toLowerCase()}','${esc("Signal " + d.verdict.classification + " (" + d.verdict.signal_score + "/100): " + (d.verdict.leading_hypothesis || ""))}','${tgState}','${esc(tgDetail)}',${tgState === "sent" ? "now()" : "NULL"});`, stage: "notifications" });
  // digest queue for emerging
  if (d.verdict.signal_score >= 51 && d.verdict.signal_score <= 70) {
    stmts.push({ sql: `INSERT INTO actions (signal_id,action_type,payload,status) VALUES ('${sigId}','digest','{"window":"daily"}'::jsonb,'pending');`, stage: "actions" });
  }
  // link the investigation to the persisted signal + close it
  const health = {};
  try { $("Unify Sensor Feeds").all().forEach(i => { const h = i.json._health; if (h) Object.entries(h).forEach(([k, v]) => { health[k] = v.errors > 0 ? "DEGRADED" : (v.count > 0 ? "AVAILABLE" : "EMPTY"); }); }); } catch (e) {}
  if (!Object.keys(health).length) {
    const byCh = {};
    (d.corpus || []).forEach(c => { if (c.channel && c.channel !== "none") byCh[c.channel] = (byCh[c.channel] || 0) + 1; });
    Object.entries(byCh).forEach(([k, v]) => { health[k] = v > 0 ? "AVAILABLE" : "EMPTY"; });
  }
  stmts.push({ sql: `UPDATE investigations SET signal_id='${sigId}' WHERE run_id='${d.init.run_id}';`, stage: "investigation_link" });
  stmts.push({ sql: `UPDATE investigations SET status='COMPLETED', finished_at=now(), pages_retrieved=${d.corpus.filter(c => c.crawl_ok).length}, claims_extracted=${d.claims.filter(c => c.action !== "none").length}, events_normalized=${d.forensics.underlying_events}, duplicates_removed=${d.forensics.duplicates_removed}, independent_sources=${d.forensics.independent_sources}, hypotheses_formed=${d.hypotheses.length}, hypotheses_disproved=${d.hypotheses.filter(h => h.status === "disproved").length}, redteam_searches=${d.redteam.searches_executed}, final_score=${d.verdict.signal_score}, sensor_health='${esc(JSON.stringify(health))}'::jsonb WHERE run_id='${d.init.run_id}';`, stage: "investigation_close" });
}
stmts.forEach((s, i) => s.ord = i);
return stmts.map(s => ({ json: s }));"""

MARK_TG_SKIPPED = UTILS + r"""
return [{ json: { ok: false, skipped: true, channel: "telegram", description: "TELEGRAM_BOT_TOKEN not configured - notification recorded as skipped (demo fallback)" } }];"""

MARK_WA_SKIPPED = UTILS + r"""
return [{ json: { ok: false, skipped: true, channel: "whatsapp", description: "WHATSAPP_TOKEN/WHATSAPP_PHONE_ID/WHATSAPP_TO not configured - notification recorded as skipped" } }];"""

RESTORE_CONTEXT = UTILS + r"""
// Postgres nodes replace item context; restore the judge payload for downstream logic.
return [{ json: $("⚖️ SIGNAL JUDGE — Deterministic Score").first().json }];"""

REEMERGE_CHECK = UTILS + r"""
// RE-EMERGENCE ENGINE: does this pattern resemble signals we previously dismissed?
// Base context comes from the last analysis code node (postgres radar replaces item context).
const d = $("Temporal Delta Engine").first().json;
let rows = [];
try { rows = $("🧬 Re-emergence Radar").all().map(i => i.json).filter(r => r && r.signal_id); } catch (e) {}
const matches = rows.map(r => ({
  signal_id: r.signal_id, title: r.title, prior_classification: r.classification,
  similarity_pct: Math.round(parseFloat(r.similarity || 0) * 1000) / 10
})).sort((a, b) => b.similarity_pct - a.similarity_pct);
const best = matches.length ? matches[0].similarity_pct : 0;
return [{ json: { ...d, reemergence: {
  checked_against_dismissed: rows.length,
  matches: matches.slice(0, 5),
  best_similarity_pct: best,
  is_reemergence: best >= 72
} } }];"""

ESCALATION_LOG_SQL = UTILS + r"""
// Runs inside the Escalation Sub-flow (invoked via Execute Workflow).
const p = $input.first().json || {};
const sql = `INSERT INTO actions (signal_id,action_type,payload,status,detail)
 VALUES ('${UTIL.esc(p.signal_id || "")}','escalation','${UTIL.esc(JSON.stringify({ score: p.score, classification: p.classification }))}'::jsonb,'done','escalated via n8n Execute Workflow');`;
return [{ json: { sql, escalated: true, signal_id: p.signal_id || null } }];"""

CACHE_PAGE_SQL = UTILS + r"""
// Build a safe INSERT per crawled page (or a no-op when extraction failed).
const init = $("Initialize Run").first().json;
let queued = [];
try { queued = $("⏳ Politeness Delay").all(); } catch (e) {}
return $input.all().map((it, idx) => {
  const j = it.json || {};
  const q = queued[idx] ? queued[idx].json : {};
  const pageText = String(j.body_text || "").replace(/\s+/g, " ").slice(0, 1500);
  const pageTitle = j.page_title || null;
  const srcUrl = q.source_url || j.source_url || null;
  if (!srcUrl || !pageText || pageText.length < 40) return { json: { sql: "SELECT 1 AS noop;", stage: "cache_skip" } };
  const payload = UTIL.esc(JSON.stringify({ source_url: srcUrl, page_text: pageText, page_title: pageTitle }));
  return { json: { sql: `INSERT INTO actions (action_type,payload,status,detail) VALUES ('crawled_page','${payload}'::jsonb,'done','${init.run_id}');`, stage: "cache_page" } };
});"""

ASSEMBLE_REPORT = UTILS + r"""
// Path-independent assembly: pull every section from its source node when the
// flowing item lacks it (quiet path skips judge/hypotheses/red-team/forensics).
const g = (n) => { try { const ref = $(n); return ref.all().length ? ref.first().json : null; } catch (e) { return null; } };
const ga = (n) => { try { return $(n).all().map(i => i.json); } catch (e) { return []; } };
const d = ($input.first() && $input.first().json) || {};
const init = d.init || g("Initialize Run") || {};
let plan = d.plan || (g("Normalize Plan") || {}).plan || null;
if (!plan) {
  const p = g("Parse Fallback Plan");
  if (p && p.topic) plan = { topic: p.topic, provider: p.provider || "openrouter", research_domains: p.research_domains || [], queries: p.queries || [], entities: p.entities || [], counter_queries: p.counter_queries || [] };
}
if (!plan) {
  const st = g("🧭 AI RESEARCH STRATEGIST") || {};
  plan = { topic: st.topic || init.topic, provider: "groq", research_domains: st.research_domains || [], queries: st.queries || [], entities: st.entities || [], counter_queries: st.counter_queries || [] };
}
const temporal = d.temporal || (g("Temporal Delta Engine") || {}).temporal ||
  { current_volume: 0, historical_baseline: null, history_weeks: 0, velocity_pct: 0, acceleration_bonus: 0, new_entity_count: 0, new_entities: [], new_terms_count: 0, distinct_channels: 0, novelty_score: 0 };
const forensics = d.forensics || (g("🕵️ SOURCE FORENSICS") || {}).forensics ||
  { articles_found: 0, underlying_events: 0, independent_sources: 0, duplicates_removed: 0, unique_domains: 0 };
const claims = d.claims || (g("🔬 EVIDENCE LAB") || {}).claims || [];
const corpus = d.corpus || ga("Cap Corpus");
const entities = d.entities || (g("🧬 ENTITY RESOLUTION") || {}).entities || [];
const relationships = d.relationships || (g("🔗 RELATIONSHIP GRAPH") || {}).relationships || [];
const hypotheses = d.hypotheses || (g("⚖️ Evidence Validation") || {}).hypotheses || (g("Keep Top 3") || {}).hypotheses || [];
const redteam = d.redteam || (g("Analyze Hostile Evidence") || {}).redteam ||
  { searches_planned: 0, searches_executed: 0, contradiction_count: 0, supporting_count: 0, unresolved_count: 0, contradictions: [], supporting: [], unresolved: [], avg_hostile_strength: 0 };
const verdict = d.verdict || (g("⚖️ SIGNAL JUDGE — Deterministic Score") || {}).verdict || null;
const reemergence = d.reemergence || (g("Re-emergence Check") || {}).reemergence || null;
let sigId = null; try { sigId = $("Persist Signal Core").first().json.signal_id; } catch (e) {}
const sensors = {};
try {
  $("Unify Sensor Feeds").all().forEach(i => { const h = i.json._health; if (h) Object.entries(h).forEach(([k, v]) => { sensors[k] = { state: v.errors > 0 ? "DEGRADED" : (v.count > 0 ? "AVAILABLE" : "EMPTY"), found: v.count }; }); });
} catch (e) {}
if (!Object.keys(sensors).length) {
  const byCh = {};
  (corpus.length ? corpus : claims).forEach(c => { const ch = c.channel; if (ch && ch !== "none") byCh[ch] = (byCh[ch] || 0) + 1; });
  Object.entries(byCh).forEach(([k, v]) => { sensors[k] = { state: "AVAILABLE", found: v }; });
}
const graphNodes = new Set(); const graphEdges = [];
relationships.slice(0, 25).forEach(r => { graphNodes.add(r.subject); graphNodes.add(r.object); graphEdges.push({ from: r.subject, label: r.predicate, to: r.object, weight: r.weight }); });
const fullAnalysis = !!verdict;
return [{ json: {
  product: "SIGNAL — The Internet's Early Warning System",
  orchestrated_by: "n8n",
  workflow: "SIGNAL — Intelligence Pipeline",
  execution_id: $execution.id,
  run_id: init.run_id,
  signal_id: sigId,
  mode: init.mode,
  topic: init.topic,
  demo_simulation: init.demo_mode,
  scenario_key: init.scenario_key,
  analysis_path: fullAnalysis ? "full" : "quiet_observation",
  strategist_provider: plan.provider || "groq",
  score: verdict ? verdict.signal_score : null,
  classification: verdict ? verdict.classification : "BELOW_THRESHOLD",
  confidence: verdict ? verdict.confidence : null,
  dna: verdict ? verdict.dna : null,
  velocity_pct: temporal.velocity_pct,
  forensics: { articles_found: forensics.articles_found, underlying_events: forensics.underlying_events, independent_sources: forensics.independent_sources, duplicates_removed: forensics.duplicates_removed, unique_domains: forensics.unique_domains },
  sensors,
  plan: { domains: plan.research_domains || [], queries: plan.queries || [], counter_queries: plan.counter_queries || [] },
  hypotheses: hypotheses.map(h => ({ statement: h.statement, prior: h.prior_confidence, posterior: h.posterior_confidence, change: h.confidence_change, status: h.status, supported: h.supported, evidence: h.support_claim })),
  red_team: { searches_executed: redteam.searches_executed, contradictions: redteam.contradictions, supporting_count: redteam.supporting_count, unresolved_count: redteam.unresolved_count, confidence_change: redteam.confidence_change },
  evidence: { claims_extracted: claims.filter(c => c.action !== "none").length, top_claims: claims.filter(c => c.action !== "none").slice(0, 8).map(c => ({ statement: c.statement, actor: c.actor, action: c.action, source: c.source_url, channel: c.channel, demo: c.is_demo })) },
  graph: { nodes: [...graphNodes].map(n => ({ id: n })), edges: graphEdges },
  reemergence,
  invalidators: verdict ? verdict.invalidators : [],
  timeline: [
    { stage: "INPUT", detail: `${init.mode} request received` },
    { stage: "THINK", detail: `strategist via ${plan.provider || "groq"}: ${(plan.queries || []).length} queries, ${(plan.counter_queries || []).length} counter-queries` },
    { stage: "SENSE", detail: `${Object.keys(sensors).length} radar channels activated` },
    { stage: "INVESTIGATE", detail: `${forensics.articles_found} articles, ${corpus.filter(c => c.crawl_ok).length} deep-crawled` },
    { stage: "CONNECT", detail: `${entities.length} entities resolved, ${relationships.length} relationships mapped` },
    { stage: "DETECT CHANGE", detail: `velocity ${temporal.velocity_pct}% vs baseline${reemergence && reemergence.is_reemergence ? " · RE-EMERGENCE of a previously dismissed pattern (" + reemergence.best_similarity_pct + "% match)" : ""}` },
    ...(fullAnalysis ? [
      { stage: "FORM HYPOTHESES", detail: `${hypotheses.length} competing hypotheses` },
      { stage: "RED TEAM", detail: `${redteam.searches_executed} adversarial searches, ${redteam.contradiction_count} contradictions found` },
      { stage: "VERIFY", detail: `forensics collapsed ${forensics.articles_found} articles → ${forensics.underlying_events} events` },
      { stage: "SCORE", detail: `deterministic score ${verdict.signal_score}/100 ${verdict.classification}` },
      { stage: "REMEMBER", detail: `persisted to PostgreSQL memory` }
    ] : [
      { stage: "THRESHOLD", detail: `change below meaningfulness threshold — logged as quiet observation, no alert fatigue` }
    ]),
    { stage: "HUMAN LOOP", detail: `notification ${init.demo_mode ? "(demo)" : ""} dispatched; review requested` }
  ],
  next_steps: ["Review the signal in the Command Center", "INVESTIGATE / WATCH / DISMISS via UI or Telegram buttons", "Monitor evolution on the Timeline page"]
}}];"""

TG_PARSE_CALLBACK = UTILS + r"""
const b = $input.first().json.body || $input.first().json;
const cb = b.callback_query || b.callbackQuery;
let decision = null, signalId = null, raw = null;
if (cb && cb.data) {
  raw = cb.data;
  const parts = raw.split(":");
  if (parts.length >= 3 && parts[0] === "signal") { decision = parts[2].toUpperCase(); signalId = parts[1]; }
} else if (b.message && b.message.text) {
  const t = b.message.text.trim();
  if (/^\/signals?/i.test(t)) decision = "SHOW_EVIDENCE";
}
return [{ json: { decision, signal_id: signalId, raw, telegram_user: cb && cb.from ? cb.from.username : (b.message && b.message.from ? b.message.from.username : null), is_callback: !!cb } }];"""

TG_FORMAT_ACK = UTILS + r"""
const d = $input.first().json;
const DEC = { INVESTIGATE: "🔍 Investigation queued - n8n will re-run the pipeline against this signal.", WATCH: "👀 Signal moved to WATCH - daily monitoring continues.", DISMISS: "❌ Signal dismissed and recorded. It will re-alert only if it RE-EMERGES with stronger evidence.", CONFIRM: "✅ Confirmation recorded. Signal escalated to CONFIRMED.", REMIND: "⏰ Reminder scheduled.", SHOW_EVIDENCE: "📚 Evidence package follows." };
return [{ json: { reply: DEC[d.decision] || "Acknowledged.", decision: d.decision, signal_id: d.signal_id } }];"""

BRIEF_FORMAT = UTILS + r"""
const summaryRows = $input.all().map(i => i.json);
let window = "daily";
try { window = $("Load Recent Signals").first().json.window || "daily"; } catch (e) {}
const lines = summaryRows.map(r => `${r.classification}: ${r.signal_count} signal(s), avg score ${Math.round(parseFloat(r.avg_score || 0))}`);
const brief = [`🛰️ SIGNAL ${String(window).toLowerCase() === "weekly" ? "WEEKLY REVIEW" : "MORNING BRIEF"}`, "", ...(lines.length ? lines : ["No meaningful changes detected."]), "", "Orchestrated by n8n"].join("\n");
return [{ json: { brief, has_content: lines.length > 0, window } }];"""

ERROR_SUMMARIZE = UTILS + r"""
const e = $input.first().json;
return [{ json: {
  workflow: e.workflow && e.workflow.name,
  execution_id: e.execution && e.execution.id,
  error_message: e.execution && e.execution.error ? String(e.execution.error.message).slice(0, 300) : "unknown",
  last_node: e.execution && e.execution.lastNodeExecuted,
  at: new Date().toISOString(),
  sql: `INSERT INTO actions (action_type,payload,status,detail) VALUES ('error','${JSON.stringify({ workflow: e.workflow && e.workflow.name, node: e.execution && e.execution.lastNodeExecuted }).replace(/'/g, "''")}'::jsonb,'failed','${String((e.execution && e.execution.error && e.execution.error.message) || "unknown").replace(/'/g, "''").slice(0, 250)}');`
}}];"""
