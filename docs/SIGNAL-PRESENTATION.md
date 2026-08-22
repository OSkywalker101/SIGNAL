# 🛰️ SIGNAL — The Internet's Early Warning System

### Complete Presentation Guide · 14 Stages · 97 working nodes · 1 n8n workflow

---

## 🎤 The Opening Pitch (30 seconds)

> Companies pay intelligence teams six figures to read the internet all day
> and tell them what's coming. **SIGNAL does it automatically**: seven OSINT
> channels in parallel, an AI strategist that plans the research, a red-team
> that attacks its own conclusions, a **deterministic score** the LLM is never
> allowed to invent, and an audit-ready PDF + Markdown report pushed to GitHub
> on every run. All of it orchestrated by a single n8n workflow.

---

## 🎯 THE USE CASE

**Problem.**
Market-moving signals — a competitor's pivot, a policy shift, a research
breakthrough, a hiring surge — surface in obscure corners of the internet
*weeks* before mainstream coverage. Humans can't monitor seven channels
continuously, and when they try, they fall for hype: forty copies of one press
release look like independent confirmation.

**What SIGNAL does.**
You give it one sentence (a topic). It:

1. plans the investigation with an LLM,
2. sweeps web / news / GitHub / jobs / policy / arXiv / Reddit simultaneously,
3. deep-crawls and caches pages politely,
4. extracts claims → entities → relationships,
5. compares everything against its own memory history,
6. generates competing hypotheses,
7. attacks them adversarially (red team),
8. verifies source independence via forensics,
9. computes a transparent 0–100 score,
10. saves everything to vector memory,
11. alerts you on Telegram / WhatsApp with decision buttons,
12. writes to your calendar and Notion,
13. ships a PDF + Markdown report to GitHub.

Fully automated. Every run.

**One line for the slide:**

> *From "one topic" to "evidence-backed, red-teamed, scored, archived
> intelligence report" — zero human effort.*

---

## 👥 TARGET AUDIENCE

| Audience | What they get |
|---|---|
| VCs & analysts | Early signal on tech shifts before deal flow gets crowded |
| Corp strategy / competitive intel teams | Automated watchtower on competitors & markets |
| Journalists & researchers | Story leads + source forensics that expose PR echo chambers |
| Policy & risk teams | Federal Register monitoring with velocity detection |
| Product / founder teams | "Is this trend real or hype?" answered with receipts |
| n8n community | A reference architecture: agentic planning, self-red-teaming loops, deterministic scoring, vector memory — all in native nodes |

---

## 💡 WHY PEOPLE SHOULD USE IT · WHY IT MATTERS

1. **It kills the #1 failure of AI research: hallucinated confidence.**
   The LLM plans and hypothesizes, but a *pure-code deterministic judge*
   computes the score. Same evidence → same score, always auditable.
2. **It attacks itself.**
   Most AI tools only find confirming evidence. SIGNAL's Red Team stage
   auto-generates contrarian queries and *subtracts* confidence when hostile
   evidence holds up.
3. **It detects change, not just presence.**
   Postgres + pgvector memory means it knows what it saw last week — novelty,
   acceleration, and even *re-emergence of dismissed patterns* are measured.
4. **It resists PR manipulation.**
   Shingle-similarity forensics collapse 40 syndicated copies into **one
   underlying event** — syndication can no longer fake independence.
5. **Every run produces artifacts.**
   PDF + Markdown committed to Git — intelligence you can cite, diff, audit.
6. **Resilient by design.**
   Groq→OpenRouter fallback, per-sensor degradation states
   (`AVAILABLE / EMPTY / DEGRADED`), graceful skip paths. One dead API never
   kills the pipeline.

---

# 🔧 NODE-BY-NODE WALKTHROUGH

## Stage 1 · INPUT — *"One sentence in"* (4 nodes)

| Node | n8n Type | What it does | Key detail |
|---|---|---|---|
| 🧠 SIGNAL SEED | Webhook | Entry point for all input modes | `POST /signal/pipeline`, responds at end so the caller gets the final report |
| Initialize Run | Code | Generates IDs, normalizes payload, sets demo mode | Creates `run_id`, `signal_id`; `DEMO_MODE` env-controlled only |
| Build Open SQL | Code | Writes parameterized SQL to open an investigation row | Escapes strings safely |
| Open Investigation Run | Postgres | Persists the run record | Status `running` — crash-safe audit trail starts here |

> **Say:** *"The very first thing we do is persist the run — even if everything
> downstream dies, there's a record."*

## Stage 2 · THINK — *"AI plans the investigation"* (7 nodes)

| Node | n8n Type | What it does | Key detail |
|---|---|---|---|
| Build Strategist Prompt | Code | Composes strategist prompt: domains, queries **and counter-queries** | Counter-queries = skepticism from step one |
| 🧭 AI RESEARCH STRATEGIST | Information Extractor | Forces LLM output into strict JSON schema | Schema-guaranteed structure |
| Groq Reasoner | OpenAI Chat Model | The brain behind the strategist | **Llama 3.3 70B on Groq** — near-instant inference |
| Strategist OK? | IF | Validates plan quality | Routes failures to fallback |
| OpenRouter Fallback Strategist | HTTP Request | Backup brain if Groq fails | `openrouter.ai`, free `llama-3.3-70b-instruct` |
| Parse Fallback Plan | Code | Parses fallback JSON to same schema | Identical shape either way |
| Plan Ready | Merge | Reunites primary/fallback paths | Single downstream flow |

> **Say:** *"This is agentic planning: the LLM doesn't answer — it decides
> **where to look** and **what would disprove it**."*

## Stage 3 · SENSE — *"7 radars sweep in parallel"* (22 nodes)

| Node | n8n Type | Source |
|---|---|---|
| Normalize Plan | Code | Expands plan into per-sensor query params |
| 🌐 WEB RADAR | HTTP Request | DuckDuckGo HTML results |
| 📰 NEWS RADAR | RSS Read | Google News RSS |
| 💻 GITHUB RADAR | HTTP Request | GitHub repo search (code activity) |
| 💼 WORKFORCE RADAR | HTTP Request | Hacker News hiring/jobs (Algolia API) |
| 🏛️ POLICY RADAR | HTTP Request | US Federal Register documents |
| 🔬 RESEARCH RADAR | HTTP Request | arXiv papers |
| 💬 COMMUNITY RADAR | HTTP Request | Reddit discussions |
| Tag ×7 (`Tag web/news/github/jobs/policy/research/community`) | Set | Normalize every source into ONE schema |
| M1–M6 | Merge ×6 | Binary merge tree reunites 7 branches |
| Unify Sensor Feeds | Code | Adds sensor health states `AVAILABLE / EMPTY / DEGRADED` |

> **Say:** *"Seven different formats become one schema. If one API dies, the
> others still deliver — the report just says DEGRADED instead of failing."*

## Stage 4 · INVESTIGATE — *"Read the actual pages"* (14 nodes)

| Node | n8n Type | What it does | Key detail |
|---|---|---|---|
| Dedup by URL | Remove Duplicates | Kills duplicate links | Layer 1 |
| Fingerprint Content | Crypto | SHA-256 of normalized text | Catches same story at different URLs |
| Dedup by Hash | Remove Duplicates | Kills content duplicates | Layer 2 |
| Cap Corpus | Limit | Keeps top **60 items** | Cost/time control |
| Prepare Crawl Queue | Code | Ranks URLs by priority | Best sources first |
| 🕷️ DEEP CRAWL | Loop Over Items | Batches through queue | batchSize **4** |
| ⏳ Politeness Delay | Wait | 0.3 s between fetches | Polite crawler |
| 📚 Load Cached Pages | Postgres | Cache hit? Skip fetching | Faster repeat runs |
| 🕸️ Fetch Page | HTTP Request | Downloads page HTML | Dynamic URL per item |
| Wrap HTML | Set | Wraps response for extraction | Handles odd encodings |
| 📄 Extract Page Text | HTML Extract | Strips HTML → readable text | |
| Build Cache SQL + 💾 Cache Crawled Page | Code + Postgres | Store fetched text | Next run is faster |
| Enrich Corpus | Code | Merges cache + fresh text | Fails gracefully; empty corpus = clean stop |

> **Say:** *"We don't trust headlines — we read full pages, cache them, and
> never fetch the same page twice."*

## Stage 5 · CONNECT — *"Claims → Entities → Graph"* (3 code nodes)

| Node | What it does | Example |
|---|---|---|
| 🔬 EVIDENCE LAB | Extracts atomic claims: actor, action, statement, source | "NVIDIA — announced — Blackwell volume production" |
| 🧬 ENTITY RESOLUTION | Collapses aliases into canonical entities | "NVDA", "Nvidia Corp" → **NVIDIA** |
| 🔗 RELATIONSHIP GRAPH | Builds weighted entity edges | `NVIDIA --partners_with--> TSMC (w=0.9)` |

> **Say:** *"Raw articles become structured knowledge — this lets later stages
> reason instead of vibe."*

## Stage 6 · DETECT CHANGE — *"New? Accelerating? Returning?"* (6 nodes)

| Node | n8n Type | What it does |
|---|---|---|
| ⏱️ TIME MACHINE — Load History | Postgres | Weeks of past observation volumes |
| Load Known Entities | Postgres | Entities already seen before |
| Temporal Delta Engine | Code | Velocity vs baseline, novelty %, distinct channels |
| 🧬 Re-emergence Radar | Postgres (pgvector) | Vector search over **dismissed** signals |
| Re-emergence Check | Code | Cosine similarity — zombie-pattern detector |
| ⚡ CHANGE DETECTOR — Meaningful? | IF | Below-threshold noise exits early — saves tokens |

> **Say:** *"Memory is the superpower. It measures acceleration and catches
> patterns that were dismissed but came back — humans almost never notice."*

## Stage 7 · FORM HYPOTHESES (4 nodes)

| Node | n8n Type | What it does |
|---|---|---|
| Build Hypothesis Context | Code | Packs graph + temporal data for the LLM |
| 🧠 HYPOTHESIS LAB | LLM Chain | Generates **three competing explanations**: consequential, coincidental, mundane |
| Parse Hypotheses | Code | Safe JSON parse with defaults |
| Rank Hypotheses | Code | Scores hypotheses against actual claim counts |

> **Say:** *"Not 'what happened' but 'what are the three possible stories, and
> which fits the evidence best'."*

## Stage 8 · RED TEAM — *"The system attacks itself"* (4 nodes)

| Node | What it does |
|---|---|
| 🥊 RED TEAM — Counter-Query Forge | Turns each hypothesis into adversarial search queries ("X is failing", "X criticism") |
| Counter-Search Sweep | Executes hostile searches across sensors |
| Analyze Hostile Evidence | Scores whether found evidence genuinely contradicts |
| Confidence Adjustment | Strong unresolved contradictions **lower confidence** — mathematically |

> **Say:** *"Our favorite slide: the workflow tries to destroy its own
> conclusion BEFORE you act on it."*

## Stage 9 · VERIFY — *"Forensics on every source"* (4 nodes)

| Node | n8n Type | What it does | Detail |
|---|---|---|---|
| 🕵️ SOURCE FORENSICS | Code | Shingle-similarity clustering collapses syndicated copies into underlying events; counts unique domains & independence groups | 40 copies ≠ 40 sources |
| Source Quality Classifier | Text Classifier | LLM classifies lead source | `primary_announcement / independent_analysis / aggregator_syndication…` |
| Apply Credibility Weights | Code | Classification → credibility 0–1 | Primary > analysis > aggregator |
| ⚖️ Evidence Validation | Code | Checks hypothesis support rate across corpus | Supported vs unsupported claims |

> **Say:** *"PR departments game news aggregators. Our forensics make that
> trick visible."*

## Stage 10 · SCORE — ⚖️ *"The Judge"* (1 node — the killer slide)

**⚖️ SIGNAL JUDGE — Deterministic Score** (`Code`) computes the final number in
plain JavaScript — **the LLM never sees the score.**

```text
score = Σ weights × dimension scores        (0–100)

novelty .15 · acceleration .20 · diversity .15 · quality .15
cross_domain .20 · independence .10 · contradiction −.05

NOISE ≤30 · WEAK ≤50 · EMERGING ≤70 · SIGNIFICANT ≤85 · CRITICAL >85

confidence =
  .35·independence + .25·quality + .25·support_rate + .15·(100−contradiction)
```

Weights are env-tunable (`SIGNAL_SCORING_WEIGHTS=k:v,k:v`) without touching code.

> **Say:** *"Ask any AI product if their score is reproducible. Ours is — same
> evidence, same score, forever. And the DNA breakdown shows WHY."*

## Stage 11 · REMEMBER (5 nodes)

| Node | n8n Type | What it does |
|---|---|---|
| Build Signal Insert SQL | Code | Prepares verdict insert |
| Persist Signal Core | Postgres | Saves signal verdict + embedding |
| Build Memory Writes | Code | Builds multi-table write payload |
| 🧬 MEMORY — Persist Investigation | Postgres (multi-statement) | Sources, claims (+vectors), entities, observations, hypotheses, invalidators |
| Restore Context | Code | Reassembles package after DB nodes |

> **Say:** *"Every run makes the next run smarter. Compounding intelligence
> inside n8n."*

## Stage 12 · HUMAN LOOP — *"Alert me, I decide"* (16 nodes)

| Node | n8n Type | Role |
|---|---|---|
| Critical or Significant? | IF | Triage gate |
| CRITICAL? Escalate | IF | Highest severity path |
| Emerging? Queue Digest | IF | Low severity → daily digest bucket |
| Log Quiet Observation | NoOp | Noise recorded silently |
| 🚀 Execute Escalation Sub-flow | Execute Workflow | Secondary workflow for CRITICAL |
| GitHub Issue? / 🐙 Create GitHub Issue | IF + HTTP Request | Critical signals open a tracked issue |
| Telegram Configured? / Mark Notification Skipped | IF + Code | Graceful config checks |
| 🚨 SIGNAL ALERT | HTTP Request | Telegram message: leading hypothesis, score, confidence + **inline decision buttons** |
| WhatsApp Configured? / 💬 WhatsApp Alert / 🚫 Mark WA Skipped | IF + HTTP Request + Code | Meta Cloud API v20 channel |
| Adapters Configured? | IF | Gate for calendar/Notion |
| 📅 Google Calendar Reminder | Google Calendar | Time-boxed review reminder |
| 📝 Notion Memory Page | Notion | Knowledge base page per signal |

> **Say:** *"Automation decides what matters; humans decide what to do.
> Buttons in chat close the loop."*

## Stage 13 · OUTPUT (1 node)

| Node | What it does |
|---|---|
| Assemble Final Report | Stitches score, DNA, forensics, hypotheses, red-team, graph, timeline, sensors, and all examined resources into one JSON package |

## Stage 14 · REPORT ARTIFACTS — *"Receipts, every run"* (7 nodes)

| Node | n8n Type | What it does |
|---|---|---|
| 📄 BUILD REPORT PDF | Code | Pure-JS PDF writer — multi-page branded report, zero external deps |
| 📝 BUILD REPORT MD | Code | Markdown twin: tables, checkbox invalidators, numbered source links |
| GitHub Report Push? | IF | PAT present? |
| 🐙 PUSH ARTIFACTS TO GITHUB | HTTP Request | Commits BOTH files via Contents API → timestamped Git history |
| 🚫 Mark Report Push Skipped | Code | Graceful skip note |
| 📎 MERGE REPORT METADATA | Code | Attaches artifact URLs + push status |
| Return Intelligence Package | Respond to Webhook | Full JSON returns to the caller |

> **Say:** *"PDF proves it works. Markdown proves it's honest. Git proves when.
> Auditability as a feature."*

---

## 📊 Stats Slide

- **97 functional nodes · 14 stages · 1 workflow**
- **7 parallel OSINT channels**, unified schema
- **2-layer dedup** (URL + SHA-256 fingerprint), corpus capped at 60
- **2 AI providers** with automatic failover (Groq → OpenRouter)
- **Deterministic scoring**: 7 weighted dimensions, LLM excluded from arithmetic
- **Full memory**: PostgreSQL + pgvector → velocity, novelty, re-emergence
- **3 notification surfaces** + Calendar + Notion + GitHub Issues
- **2 artifacts per run** committed to Git

---

## ❓ Anticipated Questions — Ready Answers

1. **Why code for scoring instead of an LLM?**
   Reproducibility, auditability, tunability via env var. LLMs are great at
   language, terrible at consistent arithmetic.
2. **Why not LangChain agents?**
   Native n8n nodes everywhere (Information Extractor, Text Classifier, Loop,
   Merge, Wait). Visible, debuggable, editable by any n8n user — that's the
   point of building ON n8n.
3. **Cost?**
   Free-tier LLMs (Groq / OpenRouter free models), public APIs, cached crawls.
   Marginal cost per run ≈ pennies.
4. **Failure handling?**
   Every external dependency has a configured-check or try/catch path; sensors
   degrade instead of crashing; runs persist from second one.
5. **Why webhook + respond at end?**
   Synchronous request/response AND schedulable — the same workflow serves an
   API client and a cron trigger.
6. **Extensibility?**
   Add a radar = 2 nodes + 1 merge link. Add a channel adapter = IF + HTTP
   node. The architecture absorbs growth.

---

## 🎬 90-Second Demo Flow

1. Send `{"topic": "solid state battery manufacturing scale-up"}` to `/api/investigate`
2. Show the live execution canvas sweeping through the stages
3. Point at the Telegram alert with decision buttons arriving
4. Open the generated PDF (score page → DNA table → cited resources)
5. Show the two commits on GitHub with timestamps
6. Close with:

> *"Topic in → red-teamed, scored, cited, archived intelligence out.
> In one n8n workflow."*

---

## 🏆 Closing Line for the Slide Deck

> SIGNAL isn't a chatbot that guesses. It's a pipeline that **investigates,
> cross-examines itself, scores transparently, remembers, and files its own
> paperwork** — the way real intelligence work has always been done, now fully
> automated on n8n.
