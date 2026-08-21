"""Generate all SIGNAL n8n workflow JSONs.
Primary: SIGNAL - Intelligence Pipeline (13 sections + re-emergence + escalation + adapters)
Support: Telegram Command Center, Daily & Weekly Briefs, Error Sentinel, Escalation Sub-flow
"""
import json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import wf_codes as C

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "n8n" / "workflows"
OUT.mkdir(parents=True, exist_ok=True)

CREDS = json.loads((pathlib.Path(__file__).parent / "cred_ids.json").read_text())
PG = CREDS.get("postgres")
GROQ = CREDS.get("openai_groq")

GROQ_BASE = "https://api.groq.com/openai/v1"
GROQ_MODEL = "llama-3.3-70b-versatile"
_nid = 0


def node(name, ntype, tv, pos, params=None, cred=None, cred_type=None, on_error=None,
         webhook_id=None, always_output=False, disabled=False):
    global _nid
    _nid += 1
    n = {"parameters": params or {}, "id": f"{_nid:08x}-0000-4000-8000-{_nid:012d}",
         "name": name, "type": ntype, "typeVersion": tv, "position": list(pos)}
    if cred:
        n["credentials"] = {cred_type: {"id": cred, "name": cred_type}}
    if on_error:
        n["onError"] = on_error
    if webhook_id:
        n["webhookId"] = webhook_id
    if always_output:
        n["alwaysOutputData"] = True
    if disabled:
        n["disabled"] = True
    return n


def sticky(content, pos, w, h, color):
    return {"parameters": {"content": content, "height": h, "width": w, "color": color},
            "id": f"s-{abs(hash(content[:30])) % 10**12:012d}", "name": f"Note {content[:18]}",
            "type": "n8n-nodes-base.stickyNote", "typeVersion": 1, "position": list(pos)}


def iff(name, pos, left, op="equals", right="true"):
    return node(name, "n8n-nodes-base.if", 2.3, pos, {
        "conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                       "conditions": [{"id": f"c{abs(hash(name)) % 9999}", "leftValue": left,
                                       "rightValue": right,
                                       "operator": {"type": "string", "operation": op}}],
                       "combinator": "and"},
        "options": {}})


class WF:
    def __init__(self, name):
        self.name = name
        self.nodes = []
        self.conns = {}

    def add(self, *nodes_):
        self.nodes.extend(nodes_)

    def link(self, src, dst, out=0, inp=0):
        self.conns.setdefault(src, {"main": []})
        mains = self.conns[src]["main"]
        while len(mains) <= out:
            mains.append([])
        mains[out].append({"node": dst, "type": "main", "index": inp})

    def ai_link(self, model_node, consumer):
        self.conns.setdefault(model_node, {}).setdefault(
            "ai_languageModel", [[{"node": consumer, "type": "ai_languageModel", "index": 0}]])

    def dump(self, fname):
        for n in self.nodes:
            if n["type"].startswith("n8n-nodes-langchain."):
                n["type"] = "@n8n/" + n["type"]
        data = {"name": self.name, "nodes": self.nodes, "connections": self.conns,
                "settings": {"executionOrder": "v1"}, "pinData": {},
                "meta": {"templateCredsSetupCompleted": True}}
        path = OUT / fname
        path.write_text(json.dumps(data, indent=1))
        print(f"wrote {path} ({len(self.nodes)} nodes)")


# ============================================================
# PRIMARY WORKFLOW
# ============================================================
wf = WF("SIGNAL — Intelligence Pipeline")

# ---- 1 INPUT ----
wf.add(sticky("## 1 · INPUT\n**🧠 SIGNAL SEED**\nWebhook entry for all three input modes:\nnatural language · structured · investigate-URL\n\nEvery run gets a durable `run_id` and an investigation record opened in PostgreSQL before intelligence begins.", [-20, -140], 620, 460, 4))
wf.add(node("🧠 SIGNAL SEED", "n8n-nodes-base.webhook", 2.1, [0, 0],
            {"httpMethod": "POST", "path": "signal/pipeline", "responseMode": "responseNode", "options": {}},
            webhook_id="signal-pipeline"))
wf.add(node("Initialize Run", "n8n-nodes-base.code", 2, [220, 0], {"jsCode": C.INIT_RUN}))
wf.add(node("Build Open SQL", "n8n-nodes-base.code", 2, [440, 0], {"jsCode": C.OPEN_RUN_SQL}))
wf.add(node("Open Investigation Run", "n8n-nodes-base.postgres", 2.6, [660, 0],
            {"operation": "executeQuery", "query": "={{ $json.sql }}", "options": {}},
            cred=PG, cred_type="postgres", always_output=True))

# ---- 2 THINK ----
wf.add(sticky("## 2 · THINK\n**🧭 AI RESEARCH STRATEGIST**\nGroq (Llama 3.3 70B) structured extraction → research domains, multi-angle queries, entities, **counter-queries**.\nFallback chain: Groq → OpenRouter → deterministic rules. The pipeline never dies.", [860, -140], 900, 560, 3))
wf.add(node("Build Strategist Prompt", "n8n-nodes-base.code", 2, [880, 0], {"jsCode": C.STRATEGIST_PROMPT}))
wf.add(node("🧭 AI RESEARCH STRATEGIST", "n8n-nodes-langchain.informationExtractor", 1.2, [1100, 0],
            {"text": "={{ $json.prompt }}",
             "attributes": {"attributes": [
                 {"name": "topic", "type": "string", "required": True, "description": "Canonical topic name"},
                 {"name": "research_domains", "type": "array", "required": True, "description": "4-8 domains: companies government research jobs github news infrastructure community finance"},
                 {"name": "queries", "type": "array", "required": True, "description": "6-10 search queries mixing DIRECT INDIRECT COMMERCIAL TECHNICAL REGULATORY ACADEMIC CONTRARIAN HISTORICAL angles"},
                 {"name": "entities", "type": "array", "required": False, "description": "Key organizations technologies people locations"},
                 {"name": "counter_queries", "type": "array", "required": True, "description": "3-5 queries that would DISPROVE an acceleration narrative"},
                 {"name": "time_horizon_days", "type": "string", "required": False, "description": "Monitoring horizon in days"}]},
             "options": {"systemMessage": "You are SIGNAL's research strategist. Design multi-angle OSINT research plans. Be specific to industry and geography. Always include contrarian angles."}},
            on_error="continueRegularOutput"))
wf.add(node("Groq Reasoner", "n8n-nodes-langchain.lmChatOpenAi", 1.3, [1100, 260],
            {"model": {"__rl": True, "value": GROQ_MODEL, "mode": "list"}, "options": {"baseURL": GROQ_BASE, "temperature": 0.2, "maxTokens": 2048}},
            cred=GROQ, cred_type="openAiApi"))
wf.add(iff("Strategist OK?", [1320, 0], "={{ $json.output && $json.output.topic ? 'yes' : 'no' }}", "equals", "yes"))
wf.add(node("OpenRouter Fallback Strategist", "n8n-nodes-base.httpRequest", 4.2, [1540, -160],
            {"method": "POST", "url": "https://openrouter.ai/api/v1/chat/completions",
             "sendHeaders": True, "headerParameters": {"parameters": [{"name": "Authorization", "value": "=Bearer {{ $env.OPENROUTER_API_KEY }}"}]},
             "sendBody": True, "specifyBody": "json",
             "jsonBody": "={{ JSON.stringify({ model: $env.OPENROUTER_MODEL || 'meta-llama/llama-3.3-70b-instruct:free', messages: [{ role: 'user', content: $('Build Strategist Prompt').first().json.prompt }], response_format: { type: 'json_object' } }) }}",
             "options": {"timeout": 20000}},
            on_error="continueRegularOutput"))
wf.add(node("Parse Fallback Plan", "n8n-nodes-base.code", 2, [1760, -160], {"jsCode": C.PARSE_FALLBACK_PLAN}))
wf.add(node("Plan Ready", "n8n-nodes-base.merge", 2.1, [1980, 0], {"mode": "append", "options": {}}))

# ---- 3 SENSE ----
wf.add(sticky("## 3 · SENSE\nSeven independent radar channels sweep the public internet in parallel:\n🌐 web(DDG) · 📰 news(GoogleNews RSS) · 💻 GitHub API · 💼 jobs(HN Algolia) · 🏛️ policy(Federal Register) · 🔬 arXiv · 💬 Reddit\nEach sensor degrades independently — one failure never stops the investigation.", [2180, -700], 1560, 1560, 5))
wf.add(iff("Demo Scenario?", [2200, 0], "={{ $('Initialize Run').first().json.scenario_key || '' }}", "notEmpty", ""))
wf.add(node("Demo Sensor Fixtures", "n8n-nodes-base.code", 2, [2420, -320], {"jsCode": C.DEMO_FIXTURES}))
wf.add(node("Normalize Plan", "n8n-nodes-base.code", 2, [2420, 100], {"jsCode": C.NORMALIZE_PLAN}))

RADARS = [
    ("🌐 WEB RADAR", "web", "https://html.duckduckgo.com/html/?q={{ encodeURIComponent($json.web_query || $json.plan_topic) }}", "text"),
    ("📰 NEWS RADAR", "news", None, None),
    ("💻 GITHUB RADAR", "github", "https://api.github.com/search/repositories?q={{ encodeURIComponent($json.plan_topic) }}&sort=updated&per_page=10", None),
    ("💼 WORKFORCE RADAR", "jobs", "https://hn.algolia.com/api/v1/search_by_date?query={{ encodeURIComponent($json.plan_topic + ' hiring') }}&tags=story&hitsPerPage=15", None),
    ("🏛️ POLICY RADAR", "policy", "https://www.federalregister.gov/api/v1/documents.json?per_page=10&order=newest&conditions%5Bterm%5D={{ encodeURIComponent($json.plan_topic) }}", None),
    ("🔬 RESEARCH RADAR", "research", "http://export.arxiv.org/api/query?search_query=all:{{ encodeURIComponent($json.plan_topic) }}&max_results=10", "text"),
    ("💬 COMMUNITY RADAR", "community", "https://www.reddit.com/search.json?q={{ encodeURIComponent($json.plan_topic) }}&sort=new&limit=15", None),
]
ys = [-520, -370, -220, -70, 80, 230, 380]
for (rname, ch, url, fmt), y in zip(RADARS, ys):
    if rname == "📰 NEWS RADAR":
        params = {"url": "=https://news.google.com/rss/search?q={{ encodeURIComponent($json.plan_topic) }}&hl=en-US&gl=US&ceid=US:en", "options": {}}
        ntype, tv = "n8n-nodes-base.rssFeedRead", 1.2
    else:
        params = {"method": "GET", "url": ("=" + url) if "{{" in url else url, "options": {}}
        if fmt:
            params["options"] = {"response": {"response": {"responseFormat": fmt}}}
        if ch in ("github", "community"):
            params["sendHeaders"] = True
            params["headerParameters"] = {"parameters": [{"name": "User-Agent", "value": "signal-osint-bot/1.0"}]}
        ntype, tv = "n8n-nodes-base.httpRequest", 4.2
    wf.add(node(rname, ntype, tv, [2640, y], params, on_error="continueRegularOutput"))
    wf.add(node(f"Tag {ch}", "n8n-nodes-base.set", 3.4, [2860, y],
                {"assignments": {"assignments": [{"id": f"a{ch}", "name": "channel", "value": ch, "type": "string"}]}, "includeOtherFields": True, "options": {}}))
    wf.link(rname, f"Tag {ch}")

MPOS = {"M1": [-325], "M2": [-25], "M3": [275]}
for m, yy in (("M1", -325), ("M2", -25), ("M3", 275)):
    wf.add(node(m, "n8n-nodes-base.merge", 2.1, [3080, yy], {"mode": "append", "options": {}}))
wf.link("Tag web", "M1", 0, 0); wf.link("Tag news", "M1", 0, 1)
wf.link("Tag github", "M2", 0, 0); wf.link("Tag jobs", "M2", 0, 1)
wf.link("Tag policy", "M3", 0, 0); wf.link("Tag research", "M3", 0, 1)
wf.add(node("M4", "n8n-nodes-base.merge", 2.1, [3300, -175], {"mode": "append", "options": {}}))
wf.link("M1", "M4", 0, 0); wf.link("Tag community", "M4", 0, 1)
wf.add(node("M5", "n8n-nodes-base.merge", 2.1, [3300, 275], {"mode": "append", "options": {}}))
wf.link("M3", "M5", 0, 0); wf.link("M2", "M5", 0, 1)
wf.add(node("M6", "n8n-nodes-base.merge", 2.1, [3520, 50], {"mode": "append", "options": {}}))
wf.link("M4", "M6", 0, 0); wf.link("M5", "M6", 0, 1)
wf.link("M6", "Unify Sensor Feeds")
wf.add(node("Unify Sensor Feeds", "n8n-nodes-base.code", 2, [3740, 50], {"jsCode": C.UNIFY_FEEDS}))

# ---- 4 INVESTIGATE ----
wf.add(sticky("## 4 · INVESTIGATE\n**🕷️ DEEP CRAWL** loops top findings through polite fetch → HTML extraction → evidence cache.\nCrypto fingerprinting + double dedup collapse copy-paste coverage before analysis.", [3940, -240], 2620, 760, 6))
wf.add(node("Dedup by URL", "n8n-nodes-base.removeDuplicates", 2, [3960, 50],
            {"operation": "removeDuplicateInputItems", "compare": "selectedFields", "fieldsToCompare": ["source_url"], "options": {}},
            on_error="continueRegularOutput"))
wf.add(node("Fingerprint Content", "n8n-nodes-base.crypto", 2, [4180, 50],
            {"action": "hash", "type": "SHA256", "value": "={{ $json.title }}|{{ $json.excerpt }}", "dataPropertyName": "content_hash", "binaryData": False},
            on_error="continueRegularOutput"))
wf.add(node("Dedup by Hash", "n8n-nodes-base.removeDuplicates", 2, [4400, 50],
            {"operation": "removeDuplicateInputItems", "compare": "selectedFields", "fieldsToCompare": ["content_hash"], "options": {}},
            on_error="continueRegularOutput"))
wf.add(node("Cap Corpus", "n8n-nodes-base.limit", 1, [4620, 50], {"maxItems": 60, "options": {}}))
wf.add(node("Prepare Crawl Queue", "n8n-nodes-base.code", 2, [4840, 50], {"jsCode": C.PREPARE_CRAWL_QUEUE}))
wf.add(node("🕷️ DEEP CRAWL", "n8n-nodes-base.splitInBatches", 3, [5060, 50], {"batchSize": 4, "options": {}}))
wf.add(node("⏳ Politeness Delay", "n8n-nodes-base.wait", 1.1, [5280, -60], {"resume": "timeInterval", "amount": 0.3, "unit": "seconds"}))
wf.add(node("🕸️ Fetch Page", "n8n-nodes-base.httpRequest", 4.2, [5500, -60],
            {"method": "GET", "url": "={{ $json.crawl_url }}", "options": {"response": {"response": {"responseFormat": "text"}}, "timeout": 8000}},
            on_error="continueRegularOutput"))
wf.add(node("Wrap HTML", "n8n-nodes-base.set", 3.4, [5720, -60],
            {"assignments": {"assignments": [{"id": "ah", "name": "html", "value": "={{ $json.data }}", "type": "string"}]}, "includeOtherFields": True, "options": {}}))
wf.add(node("📄 Extract Page Text", "n8n-nodes-base.htmlExtract", 1.2, [5940, -60],
            {"extractionValues": {"values": [
                {"key": "page_title", "cssSelector": "title", "returnValue": "text"},
                {"key": "meta_description", "cssSelector": "meta[name='description']", "returnValue": "attribute", "attribute": "content"},
                {"key": "body_text", "cssSelector": "body", "returnValue": "text"}]}, "options": {}},
            on_error="continueRegularOutput"))
wf.add(node("Build Cache SQL", "n8n-nodes-base.code", 2, [6160, -60], {"jsCode": C.CACHE_PAGE_SQL}))
wf.add(node("💾 Cache Crawled Page", "n8n-nodes-base.postgres", 2.6, [6380, -60],
            {"operation": "executeQuery", "query": "={{ $json.sql }}", "options": {}},
            cred=PG, cred_type="postgres", on_error="continueRegularOutput"))
wf.add(node("📚 Load Cached Pages", "n8n-nodes-base.postgres", 2.6, [5280, 190],
            {"operation": "executeQuery",
             "query": "=SELECT payload FROM actions WHERE action_type='crawled_page' AND detail='{{ $('Prepare Crawl Queue').first().json.run_id }}' AND created_at > now() - interval '15 minutes';",
             "options": {}},
            cred=PG, cred_type="postgres", on_error="continueRegularOutput", always_output=True))
wf.add(node("Enrich Corpus", "n8n-nodes-base.code", 2, [6380, 120], {"jsCode": C.ENRICH_CORPUS}))

# ---- 5 CONNECT ----
wf.add(sticky("## 5 · CONNECT\n🔬 atomic claims → 🧬 canonical entities → 🔗 relationship graph\nAliases collapse (NVIDIA Corp ≡ NVIDIA). Edges: hires · invests_in · partners_with · procures…", [6620, -140], 480, 560, 2))
wf.add(node("🔬 EVIDENCE LAB", "n8n-nodes-base.code", 2, [6640, 120], {"jsCode": C.EVIDENCE_LAB}))
wf.add(node("🧬 ENTITY RESOLUTION", "n8n-nodes-base.code", 2, [6860, 120], {"jsCode": C.ENTITY_RESOLUTION}))
wf.add(node("🔗 RELATIONSHIP GRAPH", "n8n-nodes-base.code", 2, [7080, 120], {"jsCode": C.RELATIONSHIP_GRAPH}))

# ---- 6 DETECT CHANGE ----
wf.add(sticky("## 6 · DETECT CHANGE\n**⏱️ TIME MACHINE** loads weeks of historical observations from memory.\n**🧬 RE-EMERGENCE ENGINE** compares against previously DISMISSED signals via pgvector similarity.\nTrivial changes are filtered out here.", [7300, -140], 700, 640, 7))
wf.add(node("⏱️ TIME MACHINE — Load History", "n8n-nodes-base.postgres", 2.6, [7320, 20],
            {"operation": "executeQuery",
             "query": "=SELECT to_char(DATE_TRUNC('week', o.observed_at),'YYYY-MM-DD') AS week, o.channel, AVG(o.value)::numeric(10,2) AS avg_val, COUNT(*) AS n FROM observations o JOIN signals s ON s.signal_id=o.signal_id WHERE s.topic ILIKE '%{{ $('Initialize Run').first().json.topic.slice(0,24).replace(/'/g,\"''\") }}%' GROUP BY 1,2 ORDER BY 1 DESC LIMIT 60;",
             "options": {}},
            cred=PG, cred_type="postgres", on_error="continueRegularOutput", always_output=True))
wf.add(node("Load Known Entities", "n8n-nodes-base.postgres", 2.6, [7320, 220],
            {"operation": "executeQuery",
             "query": "SELECT subject, predicate, object FROM relationships WHERE last_seen_at < now() - interval '36 hours' ORDER BY last_seen_at DESC LIMIT 300;",
             "options": {}},
            cred=PG, cred_type="postgres", on_error="continueRegularOutput", always_output=True))
wf.add(node("Temporal Delta Engine", "n8n-nodes-base.code", 2, [7540, 120], {"jsCode": C.TEMPORAL_DELTA}))
wf.add(node("🧬 Re-emergence Radar", "n8n-nodes-base.postgres", 2.6, [7760, 120],
            {"operation": "executeQuery",
             "query": "=SELECT signal_id, title, classification, status, 1 - (embedding <=> '{{ $json.probe_embedding }}'::vector) AS similarity FROM signals WHERE status IN ('DISMISSED','RESOLVED') ORDER BY embedding <=> '{{ $json.probe_embedding }}'::vector LIMIT 5;",
             "options": {}},
            cred=PG, cred_type="postgres", on_error="continueRegularOutput", always_output=True))
wf.add(node("Re-emergence Check", "n8n-nodes-base.code", 2, [7980, 120], {"jsCode": C.REEMERGE_CHECK}))
wf.add(iff("⚡ CHANGE DETECTOR — Meaningful?", [8200, 120],
           "={{ Math.abs($json.temporal.velocity_pct) > 20 || $json.temporal.new_entity_count > 0 || $json.claims.length >= 3 || $json.reemergence.is_reemergence }}"))

# ---- 7 FORM HYPOTHESES ----
wf.add(sticky("## 7 · FORM HYPOTHESES\n**🧠 HYPOTHESIS LAB** generates THREE competing explanations — consequential, mundane, adversarial — ranked by prior confidence. Never accepts the first idea.", [8440, -140], 700, 560, 3))
wf.add(node("Build Hypothesis Context", "n8n-nodes-base.code", 2, [8460, 120], {"jsCode": C.HYPO_CONTEXT}))
wf.add(node("🧠 HYPOTHESIS LAB", "n8n-nodes-langchain.chainLlm", 1.9, [8680, 120],
            {"promptType": "define", "text": "={{ $json.hypothesis_context }}"},
            on_error="continueRegularOutput"))
wf.add(node("Parse Hypotheses", "n8n-nodes-base.code", 2, [8900, 120], {"jsCode": C.PARSE_HYPOTHESES}))
wf.add(node("Rank Hypotheses", "n8n-nodes-base.code", 2, [9120, 120], {"jsCode": C.RANK_HYPOTHESES}))

# ---- 8 RED TEAM ----
wf.add(sticky("## 8 · RED TEAM\n**🥊 The system attacks its own conclusion.** Counter-query forge → parallel adversarial search sweep → hostile-evidence scoring → confidence adjustment.\nBefore ≠ After. Watch the confidence drop when evidence pushes back.", [9560, -140], 900, 560, 4))
wf.add(node("🥊 RED TEAM — Counter-Query Forge", "n8n-nodes-base.code", 2, [9580, 120], {"jsCode": C.COUNTER_FORGE}))
wf.add(node("Counter-Search Sweep", "n8n-nodes-base.code", 2, [9800, 120], {"jsCode": C.COUNTER_SWEEP}))
wf.add(node("Analyze Hostile Evidence", "n8n-nodes-base.code", 2, [10020, 120], {"jsCode": C.ANALYZE_HOSTILE}))
wf.add(node("Confidence Adjustment", "n8n-nodes-base.code", 2, [10240, 120], {"jsCode": C.CONFIDENCE_ADJ}))

# ---- 9 VERIFY ----
wf.add(sticky("## 9 · VERIFY\n🕵️ **SOURCE FORENSICS**: shingle-similarity clustering collapses syndicated copies into underlying events. 17 articles can equal ONE event.\nAI provenance classifier grades provenance; unsupported hypotheses are excluded.", [10460, -140], 900, 560, 5))
wf.add(node("🕵️ SOURCE FORENSICS", "n8n-nodes-base.code", 2, [10480, 120], {"jsCode": C.SOURCE_FORENSICS}))
wf.add(node("Source Quality Classifier", "n8n-nodes-langchain.textClassifier", 1.1, [10700, 120],
            {"inputText": "={{ $('Rank Hypotheses').first().json.hypotheses[0].statement + ' :: ' + ($('🔗 RELATIONSHIP GRAPH').first().json.corpus[0].title || '') }}",
             "categories": {"categories": [
                 {"category": "primary_announcement", "description": "Official press release or announcement by the organization itself"},
                 {"category": "independent_analysis", "description": "Original independent reporting or analysis by the publisher"},
                 {"category": "aggregator_syndication", "description": "Syndicated or copied coverage of other reporting"},
                 {"category": "opinion_discussion", "description": "Opinion piece or community discussion"}]},
             "options": {"fallback": "aggregator_syndication"}},
            on_error="continueRegularOutput"))
wf.add(node("Apply Credibility Weights", "n8n-nodes-base.code", 2, [10920, 120], {"jsCode": C.APPLY_CREDIBILITY}))
wf.add(node("⚖️ Evidence Validation", "n8n-nodes-base.code", 2, [11140, 120], {"jsCode": C.EVIDENCE_VALIDATION}))

# ---- 10 SCORE ----
wf.add(sticky("## 10 · SCORE\n⚖️ **SIGNAL JUDGE** — deterministic weighted scoring. The LLM NEVER invents the score.\nSignal DNA: quality · independence · acceleration · novelty · cross-domain · contradiction.", [11360, -140], 620, 400, 6))
wf.add(node("⚖️ SIGNAL JUDGE — Deterministic Score", "n8n-nodes-base.code", 2, [11380, 120], {"jsCode": C.SIGNAL_JUDGE}))
wf.add(node("Build Signal Insert SQL", "n8n-nodes-base.code", 2, [11500, 120], {"jsCode": C.PERSIST_SIGNAL_SQL}))

# ---- 11 REMEMBER ----
wf.add(sticky("## 11 · REMEMBER\n🧬 Everything persists to PostgreSQL+pgvector: sources, claims(+vectors), events, observations, relationships, hypotheses, invalidators, score history, notification ledger, run telemetry.", [11600, -140], 620, 560, 7))
wf.add(node("Persist Signal Core", "n8n-nodes-base.postgres", 2.6, [11620, 120],
            {"operation": "executeQuery", "query": "={{ $json.sql }}", "options": {}},
            cred=PG, cred_type="postgres"))
wf.add(node("Build Memory Writes", "n8n-nodes-base.code", 2, [11840, 120], {"jsCode": C.BUILD_BULK_WRITES}))
wf.add(node("🧬 MEMORY — Persist Investigation", "n8n-nodes-base.postgres", 2.6, [12060, 120],
            {"operation": "executeQuery", "query": "={{ $json.sql }}", "options": {}},
            cred=PG, cred_type="postgres", on_error="continueRegularOutput", always_output=True))
wf.add(node("Restore Context", "n8n-nodes-base.code", 2, [12280, 120], {"jsCode": C.RESTORE_CONTEXT}))

# ---- 12 HUMAN LOOP ----
wf.add(sticky("## 12 · HUMAN LOOP\nSignificant+ signals trigger an interactive Telegram alert with decision buttons.\nINVESTIGATE · WATCH · DISMISS · CONFIRM · REMIND · SHOW EVIDENCE — every choice is recorded.\nCRITICAL signals additionally fire the **Escalation Sub-flow** (Execute Workflow) and optional Calendar/Notion adapters.", [12500, -140], 900, 640, 2))
wf.add(iff("Critical or Significant?", [12520, 120], "={{ $json.verdict.signal_score >= 71 }}"))
wf.add(iff("CRITICAL? Escalate", [12740, 20], "={{ $json.verdict.signal_score >= 86 }}"))
wf.add(node("🚀 Execute Escalation Sub-flow", "n8n-nodes-base.executeWorkflow", 1.2, [12960, -160],
            {"workflowId": {"__rl": True, "value": "__ESCALATION_WF_ID__", "mode": "id"}, "options": {}}))
wf.add(iff("GitHub Issue?", [13180, -160],
           "={{ (($env.GITHUB_TOKEN || '') !== '' && ($env.GITHUB_REPO || '') !== '' && $('⚖️ SIGNAL JUDGE — Deterministic Score').first().json.verdict.signal_score >= 86) ? 'yes' : 'no' }}"))
GH_TITLE = ("🚨 SIGNAL CRITICAL ({{ $('⚖️ SIGNAL JUDGE — Deterministic Score').first().json.verdict.signal_score }}/100): "
            "{{ $('Initialize Run').first().json.topic }}")
GH_BODY = ("**Leading hypothesis:** {{ $('⚖️ SIGNAL JUDGE — Deterministic Score').first().json.verdict.leading_hypothesis }}\\n\\n"
           "| metric | value |\\n|---|---|\\n"
           "| classification | {{ $('⚖️ SIGNAL JUDGE — Deterministic Score').first().json.verdict.classification }} |\\n"
           "| confidence | {{ $('⚖️ SIGNAL JUDGE — Deterministic Score').first().json.verdict.confidence }}% |\\n"
           "| independent sources | {{ $('🕵️ SOURCE FORENSICS').first().json.forensics.independent_sources }} of {{ $('🕵️ SOURCE FORENSICS').first().json.forensics.articles_found }} articles |\\n"
           "| velocity | {{ $('Re-emergence Check').first().json.temporal.velocity_pct }}% |\\n"
           "| signal_id | `{{ $('Persist Signal Core').first().json.signal_id }}` |\\n\\n"
           "_Scored deterministically by n8n SIGNAL pipeline. Invalidators:_\\n"
           "{{ $('⚖️ SIGNAL JUDGE — Deterministic Score').first().json.verdict.invalidators.map(i => '- [ ] ' + i).join('\\n') }}")
wf.add(node("🐙 Create GitHub Issue", "n8n-nodes-base.httpRequest", 4.2, [13400, -260],
            {"method": "POST", "url": "=https://api.github.com/repos/{{ $env.GITHUB_REPO }}/issues",
             "sendHeaders": True,
             "headerParameters": {"parameters": [
                 {"name": "Authorization", "value": "=Bearer {{ $env.GITHUB_TOKEN }}"},
                 {"name": "Accept", "value": "application/vnd.github+json"},
                 {"name": "User-Agent", "value": "signal-osint-bot/1.0"}]},
             "sendBody": True, "specifyBody": "json",
             "jsonBody": "={{ JSON.stringify({ title: `" + GH_TITLE + "`, body: `" + GH_BODY + "`, labels: ['signal', 'critical'] }) }}",
             "options": {"timeout": 10000}},
            on_error="continueRegularOutput"))
wf.add(iff("Telegram Configured?", [13640, 20],
           "={{ $env.TELEGRAM_BOT_TOKEN || '' }}", "notEmpty", ""))
TG_TEXT = ("🚨 *SIGNAL DETECTED*\\n\\n*{{ $('⚖️ SIGNAL JUDGE — Deterministic Score').first().json.verdict.leading_hypothesis }}*\\n"
           "Score: {{ $json.verdict.signal_score }}/100 ({{ $json.verdict.classification }})\\n"
           "Confidence: {{ $json.verdict.confidence }}%\\n"
           "Independent sources: {{ $json.forensics.independent_sources }} ({{ $json.forensics.articles_found }} articles → {{ $json.forensics.underlying_events }} events)\\n"
           "Acceleration: {{ $('Re-emergence Check').first().json.temporal.velocity_pct }}%"
           "{{ $('Re-emergence Check').first().json.reemergence.is_reemergence ? '\\n♻️ RE-EMERGENCE of a dismissed pattern (' + $('Re-emergence Check').first().json.reemergence.best_similarity_pct + '% match)' : '' }}\\n\\n"
           "_DEMO SIMULATION_ flag: {{ $('Initialize Run').first().json.demo_mode }}")
TG_BUTTONS = '{"inline_keyboard":[[{"text":"🔎 INVESTIGATE","callback_data":"signal:{{ $(\'Persist Signal Core\').first().json.signal_id }}:INVESTIGATE"},{"text":"👀 WATCH","callback_data":"signal:{{ $(\'Persist Signal Core\').first().json.signal_id }}:WATCH"},{"text":"❌ DISMISS","callback_data":"signal:{{ $(\'Persist Signal Core\').first().json.signal_id }}:DISMISS"}],[{"text":"⏰ REMIND ME","callback_data":"signal:{{ $(\'Persist Signal Core\').first().json.signal_id }}:REMIND"},{"text":"📚 SHOW EVIDENCE","callback_data":"signal:{{ $(\'Persist Signal Core\').first().json.signal_id }}:SHOW_EVIDENCE"}]]}'
wf.add(node("🚨 SIGNAL ALERT", "n8n-nodes-base.httpRequest", 4.2, [13400, -80],
            {"method": "POST", "url": "=https://api.telegram.org/bot{{ $env.TELEGRAM_BOT_TOKEN }}/sendMessage",
             "sendBody": True, "specifyBody": "json",
             "jsonBody": "={{ JSON.stringify({ chat_id: $env.TELEGRAM_CHAT_ID, text: `" + TG_TEXT + "`, parse_mode: 'Markdown', reply_markup: " + TG_BUTTONS + " }) }}",
             "options": {"timeout": 10000}},
            on_error="continueRegularOutput"))
wf.add(node("Mark Notification Skipped", "n8n-nodes-base.code", 2, [13860, 120], {"jsCode": C.MARK_TG_SKIPPED}))
wf.add(iff("WhatsApp Configured?", [14080, 20],
           "={{ (($env.WHATSAPP_TOKEN || '') !== '' && ($env.WHATSAPP_PHONE_ID || '') !== '' && ($env.WHATSAPP_TO || '') !== '') ? 'yes' : 'no' }}"))
WA_BODY = ("🚨 *SIGNAL {{ $('⚖️ SIGNAL JUDGE — Deterministic Score').first().json.verdict.classification }}* "
           "{{ $('⚖️ SIGNAL JUDGE — Deterministic Score').first().json.verdict.signal_score }}/100\\n"
           "{{ $('⚖️ SIGNAL JUDGE — Deterministic Score').first().json.verdict.leading_hypothesis }}\\n"
           "Sources: {{ $('🕵️ SOURCE FORENSICS').first().json.forensics.independent_sources }} independent "
           "({{ $('🕵️ SOURCE FORENSICS').first().json.forensics.articles_found }} articles → "
           "{{ $('🕵️ SOURCE FORENSICS').first().json.forensics.underlying_events }} events)\\n"
           "Signal ID: {{ $('Persist Signal Core').first().json.signal_id }}")
wf.add(node("💬 WhatsApp Alert", "n8n-nodes-base.httpRequest", 4.2, [14300, -80],
            {"method": "POST", "url": "=https://graph.facebook.com/v20.0/{{ $env.WHATSAPP_PHONE_ID }}/messages",
             "sendHeaders": True,
             "headerParameters": {"parameters": [
                 {"name": "Authorization", "value": "=Bearer {{ $env.WHATSAPP_TOKEN }}"},
                 {"name": "Content-Type", "value": "application/json"}]},
             "sendBody": True, "specifyBody": "json",
             "jsonBody": "={{ JSON.stringify({ messaging_product: 'whatsapp', to: $env.WHATSAPP_TO, type: 'text', text: { preview_url: false, body: `" + WA_BODY + "` } }) }}",
             "options": {"timeout": 10000}},
            on_error="continueRegularOutput"))
wf.add(node("🚫 Mark WA Skipped", "n8n-nodes-base.code", 2, [14300, 120], {"jsCode": C.MARK_WA_SKIPPED}))
wf.add(iff("Adapters Configured?", [14520, 20],
           "={{ ($env.GOOGLE_CALENDAR_ID || '') + ($env.NOTION_DATABASE_ID || '') }}", "notEmpty", ""))
wf.add(node("📅 Google Calendar Reminder", "n8n-nodes-base.googleCalendar", 1.2, [14740, -80],
            {"resource": "event", "operation": "create",
             "calendar": {"__rl": True, "value": "={{ $env.GOOGLE_CALENDAR_ID }}", "mode": "id"},
             "start": "={{ $now.plus(24, 'hours').toISO() }}",
             "end": "={{ $now.plus(25, 'hours').toISO() }}",
             "additionalFields": {"summary": "=⏰ Re-check SIGNAL: {{ $('⚖️ SIGNAL JUDGE — Deterministic Score').first().json.verdict.classification }} — {{ $('Initialize Run').first().json.topic }}"},
             "options": {}},
            on_error="continueRegularOutput", disabled=True))
wf.add(node("📝 Notion Memory Page", "n8n-nodes-base.notion", 2.2, [14960, -80],
            {"resource": "databasePage", "operation": "create",
             "databaseId": {"__rl": True, "value": "={{ $env.NOTION_DATABASE_ID }}", "mode": "id"},
             "title": "=SIGNAL {{ $('⚖️ SIGNAL JUDGE — Deterministic Score').first().json.verdict.classification }}: {{ $('Initialize Run').first().json.topic }}",
             "propertiesUi": {"propertyValues": []}, "options": {}},
            on_error="continueRegularOutput", disabled=True))
wf.add(node("Emerging? Queue Digest", "n8n-nodes-base.if", 2.3, [12740, 300],
            {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                            "conditions": [{"id": "c6", "leftValue": "={{ $json.verdict.signal_score >= 51 && $json.verdict.signal_score <= 70 }}", "rightValue": "true", "operator": {"type": "string", "operation": "equals"}}], "combinator": "and"},
             "options": {}}))
wf.add(node("Log Quiet Observation", "n8n-nodes-base.noOp", 1, [13400, 420], {}))

# ---- 13 OUTPUT ----
wf.add(sticky("## 13 · OUTPUT\nFull intelligence package returned to the caller:\nscore · DNA · forensics · hypotheses · red-team deltas · graph · re-emergence · invalidators · timeline.", [15150, -140], 560, 400, 4))
wf.add(node("Assemble Final Report", "n8n-nodes-base.code", 2, [15170, 120], {"jsCode": C.ASSEMBLE_REPORT}))
wf.add(node("Return Intelligence Package", "n8n-nodes-base.respondToWebhook", 1.5, [15390, 120],
            {"respondWith": "firstIncomingItem", "options": {}}))

# ---- WIRING ----
wf.link("🧠 SIGNAL SEED", "Initialize Run")
wf.link("Initialize Run", "Build Open SQL")
wf.link("Build Open SQL", "Open Investigation Run")
wf.link("Open Investigation Run", "Build Strategist Prompt")
wf.link("Build Strategist Prompt", "🧭 AI RESEARCH STRATEGIST")
wf.ai_link("Groq Reasoner", "🧭 AI RESEARCH STRATEGIST")
wf.ai_link("Groq Reasoner", "🧠 HYPOTHESIS LAB")
wf.ai_link("Groq Reasoner", "Source Quality Classifier")
wf.link("🧭 AI RESEARCH STRATEGIST", "Strategist OK?")
wf.link("Strategist OK?", "Plan Ready", 0, 0)
wf.link("Strategist OK?", "OpenRouter Fallback Strategist", 1)
wf.link("OpenRouter Fallback Strategist", "Parse Fallback Plan")
wf.link("Parse Fallback Plan", "Plan Ready", 0, 1)
wf.link("Plan Ready", "Demo Scenario?")
wf.link("Demo Scenario?", "Demo Sensor Fixtures", 0)
wf.link("Demo Scenario?", "Normalize Plan", 1)
wf.link("Normalize Plan", "🌐 WEB RADAR"); wf.link("Normalize Plan", "📰 NEWS RADAR")
wf.link("Normalize Plan", "💻 GITHUB RADAR"); wf.link("Normalize Plan", "💼 WORKFORCE RADAR")
wf.link("Normalize Plan", "🏛️ POLICY RADAR"); wf.link("Normalize Plan", "🔬 RESEARCH RADAR")
wf.link("Normalize Plan", "💬 COMMUNITY RADAR")
wf.link("Demo Sensor Fixtures", "Dedup by URL")
wf.link("Unify Sensor Feeds", "Dedup by URL")
wf.link("Dedup by URL", "Fingerprint Content")
wf.link("Fingerprint Content", "Dedup by Hash")
wf.link("Dedup by Hash", "Cap Corpus")
wf.link("Cap Corpus", "Prepare Crawl Queue")
wf.link("Prepare Crawl Queue", "🕷️ DEEP CRAWL")
wf.link("🕷️ DEEP CRAWL", "📚 Load Cached Pages", 0)
wf.link("🕷️ DEEP CRAWL", "⏳ Politeness Delay", 1)
wf.link("⏳ Politeness Delay", "🕸️ Fetch Page")
wf.link("🕸️ Fetch Page", "Wrap HTML")
wf.link("Wrap HTML", "📄 Extract Page Text")
wf.link("📄 Extract Page Text", "Build Cache SQL")
wf.link("Build Cache SQL", "💾 Cache Crawled Page")
wf.link("💾 Cache Crawled Page", "🕷️ DEEP CRAWL")
wf.link("📚 Load Cached Pages", "Enrich Corpus")
wf.link("Enrich Corpus", "🔬 EVIDENCE LAB")
wf.link("🔬 EVIDENCE LAB", "🧬 ENTITY RESOLUTION")
wf.link("🧬 ENTITY RESOLUTION", "🔗 RELATIONSHIP GRAPH")
wf.link("🔗 RELATIONSHIP GRAPH", "⏱️ TIME MACHINE — Load History")
wf.link("⏱️ TIME MACHINE — Load History", "Load Known Entities")
wf.link("Load Known Entities", "Temporal Delta Engine")
wf.link("Temporal Delta Engine", "🧬 Re-emergence Radar")
wf.link("🧬 Re-emergence Radar", "Re-emergence Check")
wf.link("Re-emergence Check", "⚡ CHANGE DETECTOR — Meaningful?")
wf.link("⚡ CHANGE DETECTOR — Meaningful?", "Build Hypothesis Context", 0)
wf.link("⚡ CHANGE DETECTOR — Meaningful?", "Log Quiet Observation", 1)
wf.link("Build Hypothesis Context", "🧠 HYPOTHESIS LAB")
wf.link("🧠 HYPOTHESIS LAB", "Parse Hypotheses")
wf.link("Parse Hypotheses", "Rank Hypotheses")
wf.link("Rank Hypotheses", "🥊 RED TEAM — Counter-Query Forge")
wf.link("🥊 RED TEAM — Counter-Query Forge", "Counter-Search Sweep")
wf.link("Counter-Search Sweep", "Analyze Hostile Evidence")
wf.link("Analyze Hostile Evidence", "Confidence Adjustment")
wf.link("Confidence Adjustment", "🕵️ SOURCE FORENSICS")
wf.link("🕵️ SOURCE FORENSICS", "Source Quality Classifier")
wf.link("Source Quality Classifier", "Apply Credibility Weights")
wf.link("Apply Credibility Weights", "⚖️ Evidence Validation")
wf.link("⚖️ Evidence Validation", "⚖️ SIGNAL JUDGE — Deterministic Score")
wf.link("⚖️ SIGNAL JUDGE — Deterministic Score", "Build Signal Insert SQL")
wf.link("Build Signal Insert SQL", "Persist Signal Core")
wf.link("Persist Signal Core", "Build Memory Writes")
wf.link("Build Memory Writes", "🧬 MEMORY — Persist Investigation")
wf.link("🧬 MEMORY — Persist Investigation", "Restore Context")
wf.link("Restore Context", "Critical or Significant?")
wf.link("Critical or Significant?", "CRITICAL? Escalate", 0)
wf.link("Critical or Significant?", "Emerging? Queue Digest", 1)
wf.link("CRITICAL? Escalate", "🚀 Execute Escalation Sub-flow", 0)
wf.link("CRITICAL? Escalate", "GitHub Issue?", 1)
wf.link("🚀 Execute Escalation Sub-flow", "GitHub Issue?")
wf.link("GitHub Issue?", "🐙 Create GitHub Issue", 0)
wf.link("GitHub Issue?", "Telegram Configured?", 1)
wf.link("🐙 Create GitHub Issue", "Telegram Configured?")
wf.link("Telegram Configured?", "🚨 SIGNAL ALERT", 0)
wf.link("Telegram Configured?", "Mark Notification Skipped", 1)
wf.link("🚨 SIGNAL ALERT", "WhatsApp Configured?")
wf.link("Mark Notification Skipped", "WhatsApp Configured?")
wf.link("WhatsApp Configured?", "💬 WhatsApp Alert", 0)
wf.link("WhatsApp Configured?", "🚫 Mark WA Skipped", 1)
wf.link("💬 WhatsApp Alert", "Adapters Configured?")
wf.link("🚫 Mark WA Skipped", "Adapters Configured?")
wf.link("Adapters Configured?", "📅 Google Calendar Reminder", 0)
wf.link("Adapters Configured?", "Assemble Final Report", 1)
wf.link("📅 Google Calendar Reminder", "📝 Notion Memory Page")
wf.link("📝 Notion Memory Page", "Assemble Final Report")
wf.link("Emerging? Queue Digest", "Assemble Final Report", 0)
wf.link("Emerging? Queue Digest", "Log Quiet Observation", 1)
wf.link("Log Quiet Observation", "Assemble Final Report")
wf.link("Assemble Final Report", "Return Intelligence Package")

wf.dump("signal-intelligence-pipeline.json")

# ============================================================
# SUPPORT WF A: TELEGRAM COMMAND CENTER
# ============================================================
tcc = WF("SIGNAL — Telegram Command Center")
tcc.add(node("Telegram Updates", "n8n-nodes-base.webhook", 2.1, [0, 0],
             {"httpMethod": "POST", "path": "signal/telegram-callback", "responseMode": "responseNode", "options": {}},
             webhook_id="signal-telegram-callback"))
tcc.add(node("Parse Callback", "n8n-nodes-base.code", 2, [220, 0], {"jsCode": C.TG_PARSE_CALLBACK}))
tcc.add(node("Route Command", "n8n-nodes-base.switch", 3.4, [440, 0],
             {"rules": {"values": [
                 {"conditions": {"options": {"caseSensitive": False, "leftValue": "", "typeValidation": "loose"},
                                 "conditions": [{"id": "s1", "leftValue": "={{ $json.decision }}", "rightValue": "INVESTIGATE|WATCH|DISMISS|CONFIRM|REMIND", "operator": {"type": "string", "operation": "regex"}}], "combinator": "and"},
                  "renameOutput": True, "outputKey": "decision"},
                 {"conditions": {"options": {"caseSensitive": False, "leftValue": "", "typeValidation": "loose"},
                                 "conditions": [{"id": "s2", "leftValue": "={{ $json.decision }}", "rightValue": "SHOW_EVIDENCE", "operator": {"type": "string", "operation": "equals"}}], "combinator": "and"},
                  "renameOutput": True, "outputKey": "evidence"}]},
              "options": {"fallbackOutput": "extra", "renameFallbackOutput": "unknown"}}))
tcc.add(node("Record User Decision", "n8n-nodes-base.postgres", 2.6, [660, -100],
             {"operation": "executeQuery",
              "query": "=INSERT INTO user_feedback (signal_id, decision, channel, decided_via) VALUES ('{{ $json.signal_id }}','{{ $json.decision }}','telegram','button') ON CONFLICT DO NOTHING; UPDATE signals SET status='{{ {\"INVESTIGATE\":\"INVESTIGATING\",\"WATCH\":\"WATCHING\",\"DISMISS\":\"DISMISSED\",\"CONFIRM\":\"CONFIRMED\",\"REMIND\":\"REMINDER_SET\"}[$json.decision] || \"WATCHING\" }}' WHERE signal_id='{{ $json.signal_id }}'; INSERT INTO actions (signal_id,action_type,payload,status) VALUES ('{{ $json.signal_id }}','user_decision','{\"via\":\"telegram\"}'::jsonb,'done');",
              "options": {}},
             cred=PG, cred_type="postgres", on_error="continueRegularOutput", always_output=True))
tcc.add(node("Load Evidence Package", "n8n-nodes-base.postgres", 2.6, [660, 100],
             {"operation": "executeQuery",
              "query": "=SELECT c.statement, c.actor, c.action, s.publisher, s.source_url FROM claims c LEFT JOIN sources s ON s.run_id = c.run_id WHERE c.signal_id='{{ $json.signal_id }}' ORDER BY c.created_at DESC LIMIT 10;",
              "options": {}},
             cred=PG, cred_type="postgres", on_error="continueRegularOutput", always_output=True))
tcc.add(node("Format Acknowledgement", "n8n-nodes-base.code", 2, [880, 0], {"jsCode": C.TG_FORMAT_ACK}))
tcc.add(node("Acknowledge", "n8n-nodes-base.respondToWebhook", 1.5, [1100, 0],
             {"respondWith": "firstIncomingItem", "options": {}}))
tcc.link("Telegram Updates", "Parse Callback")
tcc.link("Parse Callback", "Route Command")
tcc.link("Route Command", "Record User Decision", 0)
tcc.link("Route Command", "Load Evidence Package", 1)
tcc.link("Route Command", "Format Acknowledgement", 2)
tcc.link("Record User Decision", "Format Acknowledgement")
tcc.link("Load Evidence Package", "Format Acknowledgement")
tcc.dump("signal-telegram-command-center.json")

# ============================================================
# SUPPORT WF B: DAILY & WEEKLY BRIEFS
# ============================================================
brf = WF("SIGNAL — Daily & Weekly Briefs")
brf.add(node("Daily Trigger", "n8n-nodes-base.scheduleTrigger", 1.2, [0, -100], {"rule": {"interval": [{"field": "cronExpression", "expression": "0 8 * * *"}]}}))
brf.add(node("Weekly Trigger", "n8n-nodes-base.scheduleTrigger", 1.2, [0, 140], {"rule": {"interval": [{"field": "cronExpression", "expression": "0 8 * * 1"}]}}))
brf.add(node("Tag Window Daily", "n8n-nodes-base.set", 3.4, [220, -100],
             {"assignments": {"assignments": [{"id": "w1", "name": "window", "value": "daily", "type": "string"}]}, "includeOtherFields": True, "options": {}}))
brf.add(node("Tag Window Weekly", "n8n-nodes-base.set", 3.4, [220, 140],
             {"assignments": {"assignments": [{"id": "w2", "name": "window", "value": "weekly", "type": "string"}]}, "includeOtherFields": True, "options": {}}))
brf.add(node("Load Recent Signals", "n8n-nodes-base.postgres", 2.6, [440, 20],
             {"operation": "executeQuery",
              "query": "=SELECT title, classification, signal_score, confidence, status, is_demo, '{{ $json.window }}' AS window FROM signals WHERE last_updated_at > now() - interval '{{ $json.window === 'weekly' ? '7 days' : '24 hours' }}' AND status NOT IN ('RESOLVED','DISMISSED') ORDER BY signal_score DESC LIMIT 30;",
              "options": {}},
             cred=PG, cred_type="postgres", on_error="continueRegularOutput", always_output=True))
brf.add(node("Summarize By Classification", "n8n-nodes-base.summarize", 1.1, [660, 20],
             {"fieldsToSummarize": {"values": [
                 {"field": "signal_score", "aggregation": "avg", "name": "avg_score"},
                 {"field": "signal_score", "aggregation": "count", "name": "signal_count"}]},
              "splitHeaders": {"values": [{"field": "classification"}]},
              "options": {}}))
brf.add(node("Format Brief", "n8n-nodes-base.code", 2, [880, 20], {"jsCode": C.BRIEF_FORMAT}))
brf.add(iff("Has Content?", [1100, 20], "={{ $json.has_content }}"))
brf.add(iff("Telegram Token?", [1320, -80], "={{ $env.TELEGRAM_BOT_TOKEN || '' }}", "notEmpty", ""))
brf.add(node("Send Brief", "n8n-nodes-base.httpRequest", 4.2, [1540, -80],
             {"method": "POST", "url": "=https://api.telegram.org/bot{{ $env.TELEGRAM_BOT_TOKEN }}/sendMessage",
              "sendBody": True, "specifyBody": "json",
              "jsonBody": "={{ JSON.stringify({ chat_id: $env.TELEGRAM_CHAT_ID, text: $json.brief }) }}",
              "options": {"timeout": 10000}},
             on_error="continueRegularOutput"))
brf.add(node("Brief Logged To Actions", "n8n-nodes-base.postgres", 2.6, [1540, 120],
             {"operation": "executeQuery",
              "query": "=INSERT INTO actions (action_type,payload,status,detail) VALUES ('brief','{\"window\":\"{{ $(\"Load Recent Signals\").first().json.window }}\"}'::jsonb,'done','digest generated');",
              "options": {}},
             cred=PG, cred_type="postgres", on_error="continueRegularOutput"))
brf.add(node("No Changes Today", "n8n-nodes-base.noOp", 1, [1320, 260], {}))
brf.link("Daily Trigger", "Tag Window Daily")
brf.link("Weekly Trigger", "Tag Window Weekly")
brf.link("Tag Window Daily", "Load Recent Signals")
brf.link("Tag Window Weekly", "Load Recent Signals")
brf.link("Load Recent Signals", "Summarize By Classification")
brf.link("Summarize By Classification", "Format Brief")
brf.link("Format Brief", "Has Content?")
brf.link("Has Content?", "Telegram Token?", 0)
brf.link("Has Content?", "No Changes Today", 1)
brf.link("Telegram Token?", "Send Brief", 0)
brf.link("Telegram Token?", "Brief Logged To Actions", 1)
brf.link("Send Brief", "Brief Logged To Actions")
brf.dump("signal-briefs-scheduler.json")

# ============================================================
# SUPPORT WF C: ERROR SENTINEL
# ============================================================
err = WF("SIGNAL — Error Sentinel")
err.add(node("Catch Pipeline Errors", "n8n-nodes-base.errorTrigger", 1, [0, 0], {}))
err.add(node("Summarize Failure", "n8n-nodes-base.code", 2, [220, 0], {"jsCode": C.ERROR_SUMMARIZE}))
err.add(node("Log Error", "n8n-nodes-base.postgres", 2.6, [440, 0],
             {"operation": "executeQuery", "query": "={{ $json.sql }}", "options": {}},
             cred=PG, cred_type="postgres", on_error="continueRegularOutput"))
err.link("Catch Pipeline Errors", "Summarize Failure")
err.link("Summarize Failure", "Log Error")
err.dump("signal-error-sentinel.json")

# ============================================================
# SUPPORT WF D: ESCALATION SUB-FLOW (Execute Workflow target)
# ============================================================
esc = WF("SIGNAL — Escalation Sub-flow")
esc.add(node("Run Once For Each Item", "n8n-nodes-base.executeWorkflowTrigger", 1.1,
             [0, 0], {"inputSource": "passthrough"}))
esc.add(node("Build Escalation SQL", "n8n-nodes-base.code", 2, [220, 0], {"jsCode": C.ESCALATION_LOG_SQL}))
esc.add(node("Record Escalation", "n8n-nodes-base.postgres", 2.6, [440, 0],
             {"operation": "executeQuery", "query": "={{ $json.sql }}", "options": {}},
             cred=PG, cred_type="postgres", on_error="continueRegularOutput"))
esc.link("Run Once For Each Item", "Build Escalation SQL")
esc.link("Build Escalation SQL", "Record Escalation")
esc.dump("signal-escalation-subflow.json")

print("ALL WORKFLOWS GENERATED")
