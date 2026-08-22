"""SIGNAL — The Internet's Early Warning System: FastAPI backend.
Proxies investigations into the n8n Intelligence Pipeline webhook and serves
the PostgreSQL memory to the Command Center UI.
"""
import json
import datetime as dt
import os
import subprocess
import threading
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, db

app = FastAPI(title="SIGNAL API", version="1.0.0",
              description="Backend for the Internet's Early Warning System. Orchestrated by n8n.")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

STATIC = Path(__file__).parent / "static"
app.mount("/app", StaticFiles(directory=str(STATIC), html=True), name="app")

REPORTS = Path(__file__).resolve().parent.parent / "reports"
REPORTS.mkdir(exist_ok=True)
app.mount("/reports", StaticFiles(directory=str(REPORTS)), name="reports")


# ------------------------------------------------------------- report artifacts
def push_reports_async():
    """Commit + push any newly generated PDF reports to GitHub in the background.
    Non-fatal by design: demo must never break because of git."""
    def job():
        try:
            repo = str(Path(__file__).resolve().parent.parent)
            subprocess.run(["git", "add", "-A", "reports"], cwd=repo,
                           capture_output=True, text=True, timeout=60)
            c = subprocess.run(["git", "commit", "-m",
                                "report artifact: auto-generated SIGNAL PDF report"],
                               cwd=repo, capture_output=True, text=True, timeout=60)
            if c.returncode != 0 and "nothing to commit" not in (c.stdout + c.stderr).lower():
                return
            subprocess.run(["git", "pull", "--rebase", "--autostash"], cwd=repo,
                           capture_output=True, text=True, timeout=60)
            subprocess.run(["git", "push"], cwd=repo,
                           capture_output=True, text=True, timeout=120)
        except Exception:
            pass
    threading.Thread(target=job, daemon=True).start()


@app.get("/")
def root():
    return RedirectResponse(url="/app/")


# ---------------------------------------------------------------- health
@app.get("/api/health")
def health():
    out = {"api": "ok", "time": dt.datetime.now(dt.timezone.utc).isoformat()}
    try:
        db.fetch_one("SELECT 1 AS ok")
        out["db"] = "ok"
    except Exception as e:
        out["db"] = f"error: {e}"
    try:
        r = httpx.get(f"{config.N8N_BASE}/healthz", timeout=5)
        out["n8n"] = "ok" if r.status_code == 200 else f"http {r.status_code}"
    except Exception as e:
        out["n8n"] = f"error: {e}"
    return out


# ---------------------------------------------------------------- investigate (proxy -> n8n)
class InvestigateBody(BaseModel):
    topic: str | None = None
    url: str | None = None
    scenario_key: str | None = Field(default=None, description="infra_accel|tech_shift|false_signal|collapse|reemergence")
    time_horizon_days: int | None = 28


@app.post("/api/investigate")
def investigate(body: InvestigateBody):
    payload = body.model_dump(exclude_none=True)
    if not payload.get("topic") and not payload.get("url"):
        raise HTTPException(422, "Provide 'topic' or 'url'")
    try:
        r = httpx.post(config.WEBHOOK_URL, json=payload, timeout=300)
    except httpx.TimeoutException:
        raise HTTPException(504, "n8n pipeline timed out after 300s")
    except Exception as e:
        raise HTTPException(502, f"n8n unreachable: {e}")
    if r.status_code != 200:
        raise HTTPException(r.status_code, f"n8n pipeline error: {r.text[:400]}")
    if not r.content:
        raise HTTPException(502, "n8n returned an empty response (check n8n executions)")
    try:
        out = r.json()
    except Exception:
        raise HTTPException(502, f"n8n returned non-JSON: {r.text[:200]}")
    push_reports_async()
    return out


# ---------------------------------------------------------------- signals
SIGNAL_LIST_SQL = """
SELECT signal_id, title, topic, status, classification, signal_score, confidence,
       velocity, acceleration, articles_found, underlying_events, independent_sources,
       is_demo, scenario_key, first_detected_at, last_updated_at, dna
FROM signals
WHERE (%(status)s::text IS NULL OR status = %(status)s::text)
  AND (%(classification)s::text IS NULL OR classification = %(classification)s::text)
ORDER BY COALESCE(last_updated_at, first_detected_at) DESC
LIMIT %(limit)s OFFSET %(offset)s
"""


@app.get("/api/signals")
def list_signals(limit: int = 50, offset: int = 0, status: str | None = None,
                 classification: str | None = None):
    rows = db.fetch_all(SIGNAL_LIST_SQL, {
        "limit": min(limit, 200), "offset": offset,
        "status": status, "classification": classification,
    })
    for r in rows:
        for k in ("dna",):
            r[k] = db.jparse(r.get(k))
        for k in ("signal_score", "confidence", "velocity", "acceleration"):
            r[k] = float(r[k]) if r.get(k) is not None else None
        for k in ("first_detected_at", "last_updated_at"):
            r[k] = r[k].isoformat() if r.get(k) else None
    return {"count": len(rows), "signals": rows}


@app.get("/api/signals/{signal_id}")
def signal_detail(signal_id: str):
    sig = db.fetch_one("SELECT * FROM signals WHERE signal_id = %s", (signal_id,))
    if not sig:
        raise HTTPException(404, "signal not found")
    sig["dna"] = db.jparse(sig.get("dna"))
    sig["metadata"] = db.jparse(sig.get("metadata"))
    for k in ("signal_score", "confidence", "velocity", "acceleration"):
        sig[k] = float(sig[k]) if sig.get(k) is not None else None
    for k in ("first_detected_at", "last_updated_at", "resolved_at"):
        sig[k] = sig[k].isoformat() if sig.get(k) else None

    sources = db.fetch_all(
        """SELECT source_url, publisher, source_type, published_at, primary_or_secondary,
                  credibility_score, independence_group, title, content_excerpt, metadata
           FROM sources WHERE run_id IN (SELECT run_id::uuid FROM investigations WHERE signal_id = %s)
           ORDER BY credibility_score DESC NULLS LAST LIMIT 100""", (signal_id,))
    # fallback: latest sources by content hash overlap is complex; also attach via claims join below

    claims = db.fetch_all(
        """SELECT claim_id, actor, action, object, quantity, quantity_unit, statement,
                  verification, created_at
           FROM claims WHERE signal_id = %s ORDER BY created_at DESC LIMIT 100""", (signal_id,))

    events = db.fetch_all(
        """SELECT event_id, actor, action, object, quantity, occurred_at, confidence
           FROM events WHERE signal_id = %s ORDER BY occurred_at DESC NULLS LAST LIMIT 60""", (signal_id,))

    hypotheses = db.fetch_all(
        """SELECT rank, statement, prior_confidence, posterior_confidence, status, reasoning
           FROM hypotheses WHERE signal_id = %s ORDER BY rank""", (signal_id,))
    for h in hypotheses:
        h["prior_confidence"] = float(h["prior_confidence"]) if h["prior_confidence"] is not None else None
        h["posterior_confidence"] = float(h["posterior_confidence"]) if h["posterior_confidence"] is not None else None

    relationships = db.fetch_all(
        """SELECT subject, predicate, object, weight, evidence_count, first_seen_at, last_seen_at
           FROM relationships WHERE signal_id = %s ORDER BY evidence_count DESC LIMIT 60""", (signal_id,))
    for r in relationships:
        r["weight"] = float(r["weight"]) if r["weight"] is not None else None
        for k in ("first_seen_at", "last_seen_at"):
            r[k] = r[k].isoformat() if r.get(k) else None

    invalidators = db.fetch_all(
        """SELECT invalidator_id, condition_text, still_valid, created_at
           FROM invalidators WHERE signal_id = %s ORDER BY created_at""", (signal_id,))
    for i_row in invalidators:
        i_row["created_at"] = i_row["created_at"].isoformat() if i_row.get("created_at") else None

    contradictions = db.fetch_all(
        """SELECT evidence_url, statement, strength, found_by, created_at
           FROM contradictions WHERE signal_id = %s ORDER BY strength DESC LIMIT 20""", (signal_id,))
    for c in contradictions:
        c["strength"] = float(c["strength"]) if c.get("strength") is not None else None
        c["created_at"] = c["created_at"].isoformat() if c.get("created_at") else None

    history = db.fetch_all(
        """SELECT score, confidence, status, recorded_at, note FROM signal_history
           WHERE signal_id = %s ORDER BY recorded_at""", (signal_id,))
    for hrow in history:
        hrow["score"] = float(hrow["score"])
        hrow["recorded_at"] = hrow["recorded_at"].isoformat()

    observations = db.fetch_all(
        """SELECT channel, metric, value, observed_at FROM observations
           WHERE signal_id = %s ORDER BY observed_at DESC LIMIT 80""", (signal_id,))

    feedback = db.fetch_all(
        """SELECT decision, channel, comment, decided_at FROM user_feedback
           WHERE signal_id = %s ORDER BY decided_at DESC LIMIT 20""", (signal_id,))
    for f in feedback:
        f["decided_at"] = f["decided_at"].isoformat()

    investigation = db.fetch_one(
        """SELECT run_id, status, started_at, finished_at, pages_retrieved, claims_extracted,
                  events_normalized, duplicates_removed, independent_sources, redteam_searches,
                  final_score, sensor_health, timeline_log
           FROM investigations WHERE signal_id = %s ORDER BY started_at DESC LIMIT 1""", (signal_id,))
    if investigation:
        investigation["sensor_health"] = db.jparse(investigation.get("sensor_health")) or {}
        investigation["timeline_log"] = db.jparse(investigation.get("timeline_log")) or []
        for k in ("started_at", "finished_at"):
            investigation[k] = investigation[k].isoformat() if investigation.get(k) else None
        investigation["final_score"] = float(investigation["final_score"]) if investigation.get("final_score") is not None else None

    for s in sources:
        s["metadata"] = db.jparse(s.get("metadata"))
        s["credibility_score"] = float(s["credibility_score"]) if s.get("credibility_score") is not None else None
        s["published_at"] = s["published_at"].isoformat() if s.get("published_at") else None

    for c in claims + events:
        for k in ("created_at", "occurred_at"):
            if k in c and c.get(k):
                c[k] = c[k].isoformat()
        if "quantity" in c:
            c["quantity"] = float(c["quantity"]) if c.get("quantity") is not None else None

    return {"signal": sig, "sources": sources, "claims": claims, "events": events,
            "hypotheses": hypotheses, "relationships": relationships,
            "invalidators": invalidators, "contradictions": contradictions,
            "history": history, "observations": observations,
            "feedback": feedback, "investigation": investigation}


class DecisionBody(BaseModel):
    decision: str = Field(description="INVESTIGATE|WATCH|DISMISS|CONFIRM|REMIND|SHOW_EVIDENCE")
    channel: str = "ui"
    comment: str | None = None


@app.post("/api/signals/{signal_id}/decision")
def record_decision(signal_id: str, body: DecisionBody):
    decision = body.decision.upper()
    valid = {"INVESTIGATE", "WATCH", "DISMISS", "CONFIRM", "REMIND", "SHOW_EVIDENCE"}
    if decision not in valid:
        raise HTTPException(422, f"decision must be one of {sorted(valid)}")
    sig = db.fetch_one("SELECT signal_id FROM signals WHERE signal_id = %s", (signal_id,))
    if not sig:
        raise HTTPException(404, "signal not found")
    db.execute(
        "INSERT INTO user_feedback (signal_id, decision, channel, comment, decided_via) "
        "VALUES (%s, %s, %s, %s, 'ui')", (signal_id, decision, body.channel, body.comment))
    new_status = config.DECISION_STATUS.get(decision)
    if new_status:
        db.execute("UPDATE signals SET status = %s, last_updated_at = now() WHERE signal_id = %s",
                   (new_status, signal_id))
    return {"ok": True, "decision": decision, "status": new_status or "unchanged"}


# ---------------------------------------------------------------- runs & stats
@app.get("/api/runs")
def list_runs(limit: int = 25):
    rows = db.fetch_all(
        """SELECT run_id, signal_id, status, started_at, finished_at, pages_retrieved,
                  claims_extracted, events_normalized, duplicates_removed, redteam_searches,
                  final_score, sensor_health
           FROM investigations ORDER BY started_at DESC LIMIT %s""", (min(limit, 100),))
    for r in rows:
        r["sensor_health"] = db.jparse(r.get("sensor_health")) or {}
        for k in ("started_at", "finished_at"):
            r[k] = r[k].isoformat() if r.get(k) else None
        r["final_score"] = float(r["final_score"]) if r.get("final_score") is not None else None
    return {"count": len(rows), "runs": rows}


@app.get("/api/stats")
def stats():
    row = db.fetch_one("""
        SELECT count(*) AS total_signals,
               count(*) FILTER (WHERE classification = 'CRITICAL') AS critical,
               count(*) FILTER (WHERE classification = 'SIGNIFICANT') AS significant,
               count(*) FILTER (WHERE classification = 'EMERGING') AS emerging,
               count(*) FILTER (WHERE classification IN ('WEAK','NOISE')) AS weak_noise,
               count(*) FILTER (WHERE status = 'DISMISSED') AS dismissed,
               count(*) FILTER (WHERE is_demo) AS demo_signals,
               AVG(signal_score)::numeric(5,1) AS avg_score,
               MAX(last_updated_at) AS last_signal_at
        FROM signals""")
    runs = db.fetch_one("""
        SELECT count(*) AS total_runs,
               count(*) FILTER (WHERE status = 'COMPLETED') AS completed_runs,
               count(*) FILTER (WHERE started_at > now() - interval '24 hours') AS runs_24h
        FROM investigations""")
    channels = db.fetch_all(
        """SELECT o.channel, count(*) AS readings, AVG(o.value)::numeric(10,1) AS avg_volume
           FROM observations o GROUP BY o.channel ORDER BY readings DESC""")
    top_claims = db.fetch_all(
        """SELECT actor, action, count(*) AS mentions FROM claims
           WHERE action <> 'none' GROUP BY actor, action ORDER BY mentions DESC LIMIT 8""")
    out = dict(row) if row else {}
    out.update(dict(runs) if runs else {})
    for k in ("avg_score",):
        out[k] = float(out[k]) if out.get(k) is not None else None
    out["last_signal_at"] = out["last_signal_at"].isoformat() if out.get("last_signal_at") else None
    for c in channels:
        c["avg_volume"] = float(c["avg_volume"]) if c.get("avg_volume") is not None else None
    out["channels"] = channels
    out["top_actors"] = top_claims
    return out


def main():
    uvicorn.run(app, host="127.0.0.1", port=config.API_PORT)


if __name__ == "__main__":
    main()
