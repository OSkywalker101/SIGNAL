# 🛰️ SIGNAL — The Internet's Early Warning System

> An n8n-orchestrated OSINT intelligence agency that answers one question: **"Is something real starting on the internet right now — or am I looking at noise?"**

## Overview
- **What it is:** A 107‑node n8n workflow that automatically plans, senses seven independent channels, deep‑crawls, clusters evidence, extracts atomic claims, builds a relationship graph, forms three hypotheses, red‑teams with adversarial searches and issues a deterministic 0‑100 score.
- **Novelty:** n8n as the product (every step inspectable), deterministic judge (LLM never invents the score), forensic source collapse, re‑emergence engine (pgvector), env‑gated integrations.
- **Tools:** n8n, FastAPI, PostgreSQL + pgvector, Groq → OpenRouter LLM, deterministic DNA scoring, pgvector, plain‑HTML/CSS/JS UI with SVG radar/graph, 72 pytest tests.
- **Use cases:** Competitive intelligence, risk monitoring, market‑entry scouting, research/journalism, automated alerts (Telegram/WhatsApp/GitHub).
- **Target audience:** Product & innovation managers, risk & compliance officers, analysts/journalists, startup founders, n8n enthusiasts.

![SIGNAL Overview](https://via.placeholder.com/800x300?text=SIGNAL+Overview+Diagram)

SIGNAL plans an investigation, sweeps seven independent public channels, deep‑crawls and fingerprints evidence, extracts atomic claims, resolves entities into a relationship graph, compares everything against **its own PostgreSQL/pgvector memory**, forms three competing hypotheses, **red-teams itself with adversarial searches**, then issues a deterministic 0–100 score — NOISE → WEAK → EMERGING → SIGNIFICANT → CRITICAL. Humans close the loop (Investigate / Watch / Dismiss), and dismissed patterns that re-emerge are automatically reopened.

The entire intelligence discipline is **a 107-node n8n workflow** (+ 4 support workflows). n8n is not glue here — it is the product.

---

## Why it's different

| # | Principle | Implementation |
|---|-----------|----------------|
| 1 | **n8n as the product, not glue** | 100% of capability lives as inspectable/editable nodes: `n8n/workflows/*.json` |
| 2 | **The LLM never invents the score** | Groq/OpenRouter only *plan* & *hypothesize*; scoring is deterministic weighted math in `⚖️ SIGNAL JUDGE` |
| 3 | **Source forensics** | Shingle-similarity clustering collapses syndicated copies → "17 articles" can honestly equal **1 event** |
| 4 | **Institutional memory (Time Machine)** | Every run writes observations/history; velocity = change vs *its own baselines*, not a snapshot |
| 5 | **Re-emergence engine (pgvector)** | Dismissed signals aren't deleted. ≥72% embedding similarity on return ⇒ auto-REOPENED |
| 6 | **Adversarial by default** | Red-team counter-search sweep + confidence deltas + an **invalidators checklist** ("what would change our mind") |
| 7 | **Graceful degradation everywhere** | Groq→OpenRouter→deterministic fallback; sensors fail independently; every integration env-gated |
| 8 | **Human-in-the-loop** | Telegram buttons / UI decisions persisted to `user_feedback`; DISMISS trains the re-emergence radar |

## Architecture

```
                        ┌──────────────────────────────────────────────────────┐
                        │                 n8n  (localhost:5679)                │
 POST /webhook/signal/pipeline ──► 1.INPUT ─► 2.THINK ─► 3.SENSE ─► 4.INVESTIGATE
                                    │            │          │             │
                              run_id+SQL   Groq/OpenRouter  7 radars    dedup×2 + crypto hash
                                    │         fallback        (DDG, GNews,   deep-crawl loop
                                    │         Information       GitHub,HN,   + page cache
                                    ▼         Extractor        FedReg,arXiv,
                        PostgreSQL+pgvector (signal db)      Reddit)
                                    │
 5.CONNECT ─► 6.DETECT CHANGE ─► 7.FORM HYPOTHESES ─► 8.RED TEAM ─► 9.VERIFY ─► 10.SCORE
 entity      Time Machine vs     ChainLLM ×3          DDG counter-  shingle      deterministic
 resolution  own baselines       hypotheses           search sweep  forensics    ⚖️ JUDGE
 graph       Re-emergence        prior conf           hostile-evid  text-class   DNA weights
 (canonical) Radar (pgvector)                          strength                   0-100
                                    │
                     11.REMEMBER (bulk SQL: sources·claims(+vectors)·events·observations·
                      relationships·hypotheses·invalidators·history·notifications)
                                    │
                     12.HUMAN LOOP ── Escalation Sub-flow (Execute Workflow)
                        ├─ 🐙 GitHub issue on CRITICAL      (env-gated)
                        ├─ 🚨 Telegram alert + decision btns (env-gated)
                        ├─ 💬 WhatsApp Cloud API alert       (env-gated)
                        └─ 📅 Google Calendar · 📝 Notion    (OAuth-gated, ship disabled)
                                    │
                     13.OUTPUT ── full intelligence package JSON

  FastAPI (:8000) ── proxies /api/investigate ──► webhook · serves memory to UI
  Command Center UI (:8000/app) ── stats · signals · DNA radar · graph · timeline · runs
```

**Support workflows:** Telegram Command Center (callback webhook → decisions), Daily & Weekly Briefs (schedule), Error Sentinel (error trigger → actions ledger), Escalation Sub-flow (Execute Workflow).

## Quick start

```bash
cd signal
docker compose up -d                       # pgvector :5432 · n8n :5679
pip install -r api/requirements.txt

python tools/bootstrap_n8n.py              # owner + credentials in n8n (idempotent)
python tools/import_workflows.py           # create/update + activate all 5 workflows
python tools/seed_demo.py                  # rich demo data (skips if data exists)
python tools/check_keys.py                 # validates Groq/OpenRouter/Telegram/GitHub config

python -m uvicorn api.main:app --port 8000 # backend + UI
start http://localhost:8000/app/
```

Windows one-click: `start-signal.bat` / `stop-signal.bat`.

## Demo script (judges)

| Beat | Action | What proves |
|------|--------|-------------|
| 1 | Open `http://localhost:8000/app/` | Live board: classifications, score bars, mini-DNA |
| 2 | **⚡ INVESTIGATE** → topic `humanoid robot warehouse deployments` → RUN (~15 s live / ~3 s demo scenario) | Full pipeline: plan→sense×7→crawl→red-team→score |
| 3 | Open the new signal → **EVIDENCE** tab | Atomic claims traced to sources; independence groups collapse syndication |
| 4 | **HYPOTHESES** + **RED TEAM** tabs | Prior→posterior bars move after adversarial searches; contradictions listed |
| 5 | Run the SAME topic again | Velocity now computed vs its own baseline (Time Machine memory) |
| 6 | **DISMISS** a signal, rerun similar pattern | Re-emergence engine flags similarity % and REOPENs |
| 7 | n8n editor tab: show `⚖️ SIGNAL JUDGE` node | The LLM never scores — deterministic weights, fully auditable |

### Sample input / expected output

**Request**
```bash
curl -X POST http://localhost:8000/api/investigate \
  -H "Content-Type: application/json" \
  -d '{"topic":"solid-state battery commercialization","scenario_key":"tech_shift"}'
```

**Response (abridged — real payload ≈ 4 KB)**
```json
{
  "product": "SIGNAL — The Internet's Early Warning System",
  "orchestrated_by": "n8n",
  "run_id": "9f2c…", "signal_id": "b21bce09-…",
  "analysis_path": "full",
  "score": 75, "classification": "SIGNIFICANT", "confidence": 66,
  "dna": {"source_quality": 76, "independence": 66, "acceleration": 74,
           "novelty": 70, "cross_domain": 72, "contradiction": 30},
  "velocity_pct": 100,
  "forensics": {"articles_found": 6, "underlying_events": 6,
                 "independent_sources": 6, "unique_domains": 6},
  "plan": {"provider": "openrouter", "queries": ["…"], "counter_queries": ["…"]},
  "hypotheses": [{"statement": "…", "prior": 58, "posterior": 64, "status": "leading"}],
  "red_team": {"searches_executed": 5, "contradictions": ["…"]},
  "graph": {"nodes": [...], "edges": [...]},
  "reemergence": {"checked_against_dismissed": 0, "is_reemergence": false},
  "invalidators": ["Independent outlets stop adding NEW reporting …", "…"],
  "timeline": [{"stage": "INPUT", "detail": "..."}, ...]
}
```

**Demo scenarios** (deterministic fixtures — never presented as live data):
`infra_accel` (compute build-out, CRITICAL trajectory) · `tech_shift` (technology transition) · `false_signal` (syndicated echo chamber → forensic collapse) · `collapse` (narrative dies) · `reemergence` (dismissed pattern returns).

## Integrations (all optional, env-gated)

| Channel | Env vars | Behaviour when unset |
|---|---|---|
| 🤖 Groq (primary strategist) | `GROQ_API_KEY` | falls back ↓ |
| 🌐 OpenRouter (fallback LLM) | `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | falls back ↓ deterministic rules |
| 🚨 Telegram alerts + buttons | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | alert logged as skipped |
| 💬 WhatsApp Cloud API | `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`, `WHATSAPP_TO` | alert logged as skipped |
| 🐙 GitHub issue on CRITICAL | `GITHUB_TOKEN`, `GITHUB_REPO` (`owner/name`) | step skipped |
| 📅 Google Calendar reminder | OAuth credential in n8n + enable node | node ships disabled |
| 📝 Notion memory page | Notion credential + `NOTION_DATABASE_ID` + enable node | node ships disabled |

Set vars in `.env`, restart n8n (`docker compose up -d`), run `python tools/import_workflows.py`.

## Project layout

```
signal/
├── api/                    FastAPI backend + static SPA (Command Center)
│   ├── main.py             endpoints: investigate proxy, signals, decisions, runs, stats
│   ├── db.py  config.py    thin psycopg layer, .env loader
│   └── static/             dependency-free dashboard (SVG radar/graph/sparklines)
├── n8n/workflows/          generated workflow JSONs (the product)
├── tools/
│   ├── wf_codes.py         all JS executed inside Code nodes (single source of truth)
│   ├── generate_workflows.py   emits the 5 workflows from wf_codes
│   ├── import_workflows.py update-in-place importer + activator (internal REST API)
│   ├── bootstrap_n8n.py    owner setup + Postgres/Groq credentials
│   ├── seed_demo.py        rich demo dataset (4 signals w/ full history)
│   ├── check_keys.py       provider key validator
├── db/init/01-schema.sql   signals·sources·claims(+pgvector)·events·observations·…
├── tests/                  pytest: workflow structure, snippet syntax, API smoke
├── docker-compose.yml      pgvector + n8n (port 5679)
├── start-signal.bat / stop-signal.bat
└── .env                    secrets (never commit)
```

## Testing

```bash
python -m pytest tests -q      # 73 tests: workflow JSON structure, expression prefixes,
                               # scoped langchain types, JS snippet syntax (node --check),
                               # no embedded secrets, API smoke (DB-optional)
```

## Security notes

- All provider keys live ONLY in `.env` (gitignored); workflows reference `$env.*` at runtime.
- Workflow JSONs are scanned by CI-grade tests for embedded secret patterns.
- Integrations degrade to logged skips — the demo cannot leak or fail on missing creds.
- Change `POSTGRES_PASSWORD`, `N8N_ADMIN_PASSWORD` before any non-local deployment.

## Configuration reference (`.env`)

```ini
# core
POSTGRES_USER=signal  POSTGRES_PASSWORD=…  POSTGRES_DB=signal
SIGNAL_PG_PORT=5432  SIGNAL_N8N_PORT=5679  SIGNAL_API_PORT=8000
N8N_ADMIN_EMAIL=admin@signal.local  N8N_ADMIN_PASSWORD=…
N8N_ENCRYPTION_KEY=…

# LLM strategists (fallback chain top→down)
GROQ_API_KEY=gsk_…
OPENROUTER_API_KEY=sk-or-…
# OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct:free

# notifications (all optional)
TELEGRAM_BOT_TOKEN=  TELEGRAM_CHAT_ID=
WHATSAPP_TOKEN=  WHATSAPP_PHONE_ID=  WHATSAPP_TO=
GITHUB_TOKEN=  GITHUB_REPO=owner/repo
GOOGLE_CALENDAR_ID=  NOTION_DATABASE_ID=

# tuning
DEMO_MODE=false
SIGNAL_SCORING_WEIGHTS=novelty:0.15,acceleration:0.20,…   # optional override
```

---

Built for the n8n competition. Orchestrated end-to-end by n8n.
