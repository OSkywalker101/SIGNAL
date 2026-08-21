-- ============================================================
-- SIGNAL — Database Schema (PostgreSQL 16 + pgvector)
-- The persistent memory of the Internet's Early Warning System
-- ============================================================
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ---------- ENTITIES (canonical, alias-resolved) ----------
CREATE TABLE IF NOT EXISTS entities (
    entity_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name  TEXT NOT NULL,
    entity_type     TEXT NOT NULL CHECK (entity_type IN ('company','person','technology','product','organization','government','location','research_topic')),
    aliases         TEXT[] DEFAULT '{}',
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata        JSONB DEFAULT '{}'
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_entities_canonical ON entities (LOWER(canonical_name), entity_type);

-- ---------- SOURCES ----------
CREATE TABLE IF NOT EXISTS sources (
    source_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_url          TEXT NOT NULL,
    url_hash            TEXT UNIQUE,
    source_type         TEXT NOT NULL,             -- web|news|rss|github|jobs|government|research|community|hackernews
    publisher           TEXT,
    author              TEXT,
    published_at        TIMESTAMPTZ,
    retrieved_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    primary_or_secondary TEXT NOT NULL DEFAULT 'secondary' CHECK (primary_or_secondary IN ('primary','secondary')),
    credibility_score   NUMERIC(4,3) DEFAULT 0.5,  -- 0..1
    independence_group  TEXT,                       -- forensic cluster id: same underlying event
    title               TEXT,
    content_excerpt     TEXT,
    content_hash        TEXT,                       -- crypto hash for exact-dup detection
    run_id              UUID,
    metadata            JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_sources_run ON sources(run_id);
CREATE INDEX IF NOT EXISTS idx_sources_group ON sources(independence_group);

-- ---------- CLAIMS (atomic, sourced) ----------
CREATE TABLE IF NOT EXISTS claims (
    claim_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id       UUID,
    run_id          UUID,
    source_id       UUID REFERENCES sources(source_id),
    actor           TEXT,
    action          TEXT,
    object          TEXT,
    quantity        NUMERIC,
    quantity_unit   TEXT,
    location        TEXT,
    claimed_at      TIMESTAMPTZ,
    statement       TEXT NOT NULL,
    verification    TEXT NOT NULL DEFAULT 'unverified' CHECK (verification IN ('verified','contradicted','unsupported','unverified')),
    embedding       vector(384),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_claims_signal ON claims(signal_id);

-- ---------- EVENTS (normalized underlying events) ----------
CREATE TABLE IF NOT EXISTS events (
    event_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id       UUID,
    actor           TEXT,
    action          TEXT,
    object          TEXT,
    quantity        NUMERIC,
    location        TEXT,
    occurred_at     TIMESTAMPTZ,
    source_id       UUID REFERENCES sources(source_id),
    confidence      NUMERIC(4,3) DEFAULT 0.5,
    embedding       vector(384),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_events_signal ON events(signal_id);

-- ---------- SIGNALS ----------
CREATE TABLE IF NOT EXISTS signals (
    signal_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title               TEXT NOT NULL,
    topic               TEXT NOT NULL,
    input_mode          TEXT NOT NULL DEFAULT 'natural' CHECK (input_mode IN ('natural','structured','url')),
    status              TEXT NOT NULL DEFAULT 'DETECTED' CHECK (status IN ('DETECTED','EMERGING','INVESTIGATING','CONFIRMED','DISMISSED','WATCH','ESCALATED','RESOLVED','COLLAPSING','REVERSED','REOPENED')),
    classification      TEXT CHECK (classification IN ('NOISE','WEAK','EMERGING','SIGNIFICANT','CRITICAL')),
    signal_score        NUMERIC(5,2),
    confidence          NUMERIC(5,2),
    dna                 JSONB DEFAULT '{}',      -- Signal DNA breakdown
    velocity            NUMERIC,                  -- % change vs history
    acceleration        NUMERIC,
    articles_found      INTEGER DEFAULT 0,
    underlying_events   INTEGER DEFAULT 0,
    independent_sources INTEGER DEFAULT 0,
    first_detected_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at         TIMESTAMPTZ,
    is_demo             BOOLEAN NOT NULL DEFAULT false,
    scenario_key        TEXT,
    embedding           vector(384),
    metadata            JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status);

-- ---------- OBSERVATIONS (raw sensor readings over time) ----------
CREATE TABLE IF NOT EXISTS observations (
    observation_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id       UUID REFERENCES signals(signal_id),
    run_id          UUID,
    channel         TEXT NOT NULL,                 -- web|news|github|jobs|policy|research|community|hackernews
    metric          TEXT NOT NULL,                 -- volume|new_entities|new_terms|...
    value           NUMERIC NOT NULL,
    observed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    window_start    TIMESTAMPTZ,
    window_end      TIMESTAMPTZ,
    details         JSONB DEFAULT '{}',
    embedding       vector(384)
);
CREATE INDEX IF NOT EXISTS idx_obs_signal_time ON observations(signal_id, observed_at DESC);

-- ---------- RELATIONSHIPS (graph edges) ----------
CREATE TABLE IF NOT EXISTS relationships (
    relationship_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id       UUID,
    subject         TEXT NOT NULL,
    predicate       TEXT NOT NULL,                 -- hires|develops|partners|appears_in|affects|announces|supports
    object          TEXT NOT NULL,
    weight          NUMERIC(4,3) DEFAULT 0.5,
    evidence_count  INTEGER DEFAULT 1,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_new          BOOLEAN DEFAULT true
);
CREATE INDEX IF NOT EXISTS idx_rel_signal ON relationships(signal_id);

-- ---------- HYPOTHESES ----------
CREATE TABLE IF NOT EXISTS hypotheses (
    hypothesis_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id       UUID REFERENCES signals(signal_id),
    rank            INTEGER DEFAULT 99,
    statement       TEXT NOT NULL,
    prior_confidence NUMERIC(5,2) DEFAULT 50,
    posterior_confidence NUMERIC(5,2),             -- after red team
    status          TEXT NOT NULL DEFAULT 'candidate' CHECK (status IN ('candidate','leading','disproved','confirmed')),
    reasoning       TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_hyp_signal ON hypotheses(signal_id);

-- ---------- CONTRADICTIONS ----------
CREATE TABLE IF NOT EXISTS contradictions (
    contradiction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id        UUID REFERENCES signals(signal_id),
    hypothesis_id    UUID REFERENCES hypotheses(hypothesis_id),
    evidence_url     TEXT,
    statement        TEXT NOT NULL,
    strength         NUMERIC(4,3) DEFAULT 0.5,     -- how damaging
    found_by         TEXT DEFAULT 'red_team',       -- red_team|user|monitor
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- INVESTIGATIONS (run observability) ----------
CREATE TABLE IF NOT EXISTS investigations (
    run_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    n8n_execution_id    TEXT,
    signal_id           UUID,
    trigger_mode        TEXT NOT NULL,             -- monitor|investigate_url|red_team|scheduled
    input_payload       JSONB DEFAULT '{}',
    research_plan       JSONB DEFAULT '{}',
    status              TEXT NOT NULL DEFAULT 'RUNNING' CHECK (status IN ('RUNNING','COMPLETED','FAILED','PARTIAL')),
    sources_searched    INTEGER DEFAULT 0,
    pages_retrieved     INTEGER DEFAULT 0,
    claims_extracted    INTEGER DEFAULT 0,
    events_normalized   INTEGER DEFAULT 0,
    duplicates_removed  INTEGER DEFAULT 0,
    independent_sources INTEGER DEFAULT 0,
    hypotheses_formed   INTEGER DEFAULT 0,
    hypotheses_disproved INTEGER DEFAULT 0,
    redteam_searches    INTEGER DEFAULT 0,
    final_score         NUMERIC(5,2),
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at         TIMESTAMPTZ,
    error_summary       TEXT,
    sensor_health       JSONB DEFAULT '{}',        -- per-channel AVAILABLE/DEGRADED/UNAVAILABLE
    timeline_log        JSONB DEFAULT '[]'         -- ordered stage log for demo replay
);

-- ---------- SIGNAL HISTORY (score evolution) ----------
CREATE TABLE IF NOT EXISTS signal_history (
    history_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id    UUID REFERENCES signals(signal_id),
    score        NUMERIC(5,2) NOT NULL,
    confidence   NUMERIC(5,2),
    status       TEXT,
    recorded_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    note         TEXT
);
CREATE INDEX IF NOT EXISTS idx_hist_signal_time ON signal_history(signal_id, recorded_at);

-- ---------- USER FEEDBACK (human-in-the-loop decisions) ----------
CREATE TABLE IF NOT EXISTS user_feedback (
    feedback_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id    UUID REFERENCES signals(signal_id),
    decision     TEXT NOT NULL CHECK (decision IN ('INVESTIGATE','WATCH','DISMISS','CONFIRM','REMIND','SHOW_EVIDENCE')),
    channel      TEXT DEFAULT 'ui',                -- ui|telegram|calendar
    comment      TEXT,
    decided_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_via  TEXT                              -- button label / endpoint
);

-- ---------- ACTIONS ----------
CREATE TABLE IF NOT EXISTS actions (
    action_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id    UUID,
    action_type  TEXT NOT NULL,                    -- notify|calendar_event|notion_page|digest|escalate
    payload      JSONB DEFAULT '{}',
    status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','sent','failed','skipped')),
    detail       TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- NOTIFICATIONS ----------
CREATE TABLE IF NOT EXISTS notifications (
    notification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id       UUID,
    channel         TEXT NOT NULL,                 -- telegram|discord|email|inapp
    severity        TEXT NOT NULL,                 -- critical|significant|emerging|info
    message         TEXT NOT NULL,
    sent_at         TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','sent','failed','skipped')),
    detail          TEXT
);

-- ---------- INVALIDATION CONDITIONS ("what would change our mind") ----------
CREATE TABLE IF NOT EXISTS invalidators (
    invalidator_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id      UUID REFERENCES signals(signal_id),
    hypothesis_id  UUID,
    condition_text TEXT NOT NULL,
    check_query_hint TEXT,
    still_valid    BOOLEAN DEFAULT true,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- SENSOR HEALTH LOG ----------
CREATE TABLE IF NOT EXISTS sensor_health (
    health_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id      UUID,
    channel     TEXT NOT NULL,
    state       TEXT NOT NULL CHECK (state IN ('AVAILABLE','DEGRADED','UNAVAILABLE','DEMO_FALLBACK')),
    latency_ms  INTEGER,
    detail      TEXT,
    checked_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- HELPER: semantic memory search ----------
CREATE INDEX IF NOT EXISTS idx_claims_embedding ON claims USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_events_embedding ON events USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_signals_embedding ON signals USING hnsw (embedding vector_cosine_ops);
