"""Seed the SIGNAL database with rich demo data so the Command Center looks alive instantly.
Idempotent by default (skips when signals exist); use --force to wipe demo rows first.

Usage:
    python tools/seed_demo.py            # seed if empty
    python tools/seed_demo.py --force    # delete seeded demo signals, re-seed
"""
import json
import pathlib
import random
import sys
import uuid
import datetime as dt

import psycopg2
import psycopg2.extras

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENV = {}
for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        ENV[k.strip()] = v.strip()

PG = dict(host=ENV.get("SIGNAL_PG_HOST", "localhost"),
          port=int(ENV.get("SIGNAL_PG_PORT", "5432")),
          user=ENV.get("POSTGRES_USER", "signal"),
          password=ENV.get("POSTGRES_PASSWORD", "change_me_in_prod"),
          dbname=ENV.get("POSTGRES_DB", "signal"))

NOW = dt.datetime.now(dt.timezone.utc)


def ago(days=0, hours=0):
    return NOW - dt.timedelta(days=days, hours=hours)


def dna(q, i, a, n, x, c):
    return {"source_quality": q, "independence": i, "acceleration": a,
            "novelty": n, "cross_domain": x, "contradiction": c}


SEED_SIGNALS = [
    dict(
        title="YottaGrid commits 40,000-GPU AI compute cluster in Pune", topic="india ai compute build-out",
        status="ESCALATED", classification="CRITICAL", score=91, confidence=84,
        velocity=140.0, accel=25.0, articles=17, events=4, independent=4, is_demo=True,
        scenario="infra_accel",
        dna=dna(88, 72, 96, 78, 90, 12),
        sources=[
            ("Reuters", "news", "primary_announcement", 0.92, 1),
            ("Bloomberg", "news", "independent_analysis", 0.85, 1),
            ("PIB Government", "policy", "primary_announcement", 0.9, 2),
            ("JobsWire India", "jobs", "independent_analysis", 0.7, 3),
            ("GitHub Trending", "github", "independent_analysis", 0.68, 3),
            ("Syndication Daily", "news", "aggregator_syndication", 0.35, 1),
        ],
        claims=[
            ("YottaGrid", "expands", "40k-GPU cluster Pune", 40000, "gpu", "Reuters"),
            ("YottaGrid", "hires", "CUDA inference engineers", 27, "engineers", "JobsWire India"),
            ("India AI Ministry", "procures", "Rs 10,000 crore compute subsidy", 10000, "crore", "PIB Government"),
            ("Syndication Daily", "launches", "copy of YottaGrid press release", None, None, "Syndication Daily"),
        ],
        hyps=[
            (1, "India's private AI-compute build-out has entered a genuine multi-quarter acceleration phase", 74, 81, "leading",
             "Government procurement, private cluster announcements and hiring surge reinforce across four channels."),
            (2, "One-off election-cycle subsidy driving temporary procurement spike", 45, 38, "candidate",
             "Timing aligns with budget announcements; sustainability depends on next fiscal cycle."),
            (3, "Coordinated PR inflating perceived momentum ahead of investor roadshow", 28, 19, "disproved",
             "Independent tender records and third-party hiring data corroborate real capacity commitments."),
        ],
        rels=[("yottagrid", "partners_with", "nvidia"), ("yottagrid", "hires", "cuda engineers"),
              ("india ai ministry", "procures", "gpu capacity"), ("sarvam-2 stack", "appears_in", "github trending")],
        invalidators=[
            "Next national budget allocates <50% of announced compute funds",
            "YottaGrid delays cluster commissioning beyond two quarters",
            "Hiring postings for CUDA roles flatten for 4 consecutive weeks",
        ],
        history=[62, 68, 75, 79, 86, 91],
        obs=[("news", 8), ("policy", 5), ("jobs", 6), ("github", 4), ("community", 3), ("web", 9)],
        decision=("CONFIRM", "telegram", "Confirmed via TG button during dry-run."),
        contradiction=None,
        sensor_health={"web": "AVAILABLE", "news": "AVAILABLE", "github": "AVAILABLE", "jobs": "AVAILABLE", "policy": "AVAILABLE", "research": "AVAILABLE", "community": "AVAILABLE"},
    ),
    dict(
        title="Solid-state battery pilot lines scale faster than incumbent roadmap", topic="solid-state battery commercialization",
        status="EMERGING", classification="SIGNIFICANT", score=76, confidence=71,
        velocity=65.0, accel=12.0, articles=11, events=5, independent=5, is_demo=True,
        scenario="tech_shift",
        dna=dna(76, 66, 74, 70, 72, 30),
        sources=[
            ("Nikkei Asia", "news", "independent_analysis", 0.82, 1),
            ("Toyota Press Release", "news", "primary_announcement", 0.9, 2),
            ("arXiv Materials", "research", "independent_analysis", 0.75, 3),
            ("Battery Insider", "news", "aggregator_syndication", 0.4, 2),
        ],
        claims=[
            ("Toyota", "launches", "pilot solid-state line 2027 models", None, None, "Nikkei Asia"),
            ("QuantumScape", "invests", "gigawatt pilot facility", 200, "million", "Battery Insider"),
            ("Tokyo Institute", "publishes_research", "sulfide electrolyte benchmark", None, None, "arXiv Materials"),
        ],
        hyps=[
            (1, "Manufacturing cost curve crossed the threshold for mass-market EVs before 2028", 61, 64, "leading",
             "Multiple independent pilot-line announcements with capital commitments."),
            (2, "Announcements timed to offset incumbent lithium slowdown narratives", 42, 41, "candidate",
             "Several releases share language patterns suggesting shared PR source."),
            (3, "Research breakthrough overhyped; production yields remain undisclosed", 33, 29, "candidate",
             "No independent yield verification found in hostile sweep."),
        ],
        rels=[("toyota", "partners_with", "sumitomo"), ("quantumscape", "invests_in", "pilot facility"),
              ("tokyo institute", "appears_in", "arxiv")],
        invalidators=["2027 model-year homologation filings fail to appear", "Pilot yield data stays unpublished through Q2"],
        history=[48, 55, 60, 66, 71, 76],
        obs=[("news", 7), ("research", 4), ("web", 6), ("community", 2)],
        decision=("WATCH", "ui", "Watching until yield data lands."),
        contradiction={"statement": "Industry chemist argues sulfide route remains 5 years from automotive scale", "strength": 0.55},
        sensor_health={"web": "AVAILABLE", "news": "AVAILABLE", "github": "EMPTY", "jobs": "DEGRADED", "policy": "AVAILABLE", "research": "AVAILABLE", "community": "AVAILABLE"},
    ),
    dict(
        title="'Quantum advantage in logistics' claim collapses under replication attempt", topic="quantum logistics optimization",
        status="COLLAPSING", classification="WEAK", score=34, confidence=28,
        velocity=-45.0, accel=-20.0, articles=14, events=2, independent=2, is_demo=True,
        scenario="false_signal",
        dna=dna(38, 22, 15, 44, 30, 82),
        sources=[
            ("Startup PR Wire", "news", "primary_announcement", 0.5, 1),
            ("Tech Daily", "news", "aggregator_syndication", 0.32, 1),
            ("Replication Blog", "research", "independent_analysis", 0.66, 2),
        ],
        claims=[
            ("D-Wave-style startup", "launches", "logistics quantum solver", None, None, "Startup PR Wire"),
            ("Independent replicators", "warns_or_declines", "benchmark fails to reproduce", None, None, "Replication Blog"),
        ],
        hyps=[
            (1, "Genuine early capability, noisy benchmarks", 35, 18, "disproved",
             "Replication team found classical heuristic matches claimed speedup."),
            (2, "Investor-driven hype cycle without technical basis", 58, 79, "leading",
             "All volume traces to single press release syndicated across outlets."),
        ],
        rels=[("pr wire startup", "announces", "quantum solver"), ("replication blog", "contradicts_growth_of", "quantum claims")],
        invalidators=["Peer-reviewed benchmark appears confirming >2x speedup", "Second lab reproduces the result"],
        history=[58, 52, 46, 41, 37, 34],
        obs=[("news", 11), ("web", 3), ("research", 2), ("community", 1)],
        decision=("DISMISS", "ui", "Syndicated echo chamber; forensic collapse confirmed."),
        contradiction={"statement": "Classical solver matches claimed performance at 1/1000 cost", "strength": 0.88},
        sensor_health={"web": "AVAILABLE", "news": "AVAILABLE", "github": "EMPTY", "jobs": "EMPTY", "policy": "EMPTY", "research": "AVAILABLE", "community": "AVAILABLE"},
    ),
    dict(
        title="Dismissed 'GPU smuggling corridor' chatter re-emerges with customs data", topic="gpu export control evasion",
        status="REOPENED", classification="SIGNIFICANT", score=73, confidence=66,
        velocity=80.0, accel=18.0, articles=9, events=3, independent=3, is_demo=True,
        scenario="reemergence",
        dna=dna(70, 63, 77, 58, 68, 35),
        sources=[
            ("Customs Records Digest", "policy", "independent_analysis", 0.8, 1),
            ("Regional Herald", "news", "independent_analysis", 0.72, 1),
            ("Forum Thread", "community", "opinion_discussion", 0.45, 3),
        ],
        claims=[
            ("Unnamed brokers", "expands", "transshipment routes via third countries", None, None, "Customs Records Digest"),
            ("Regional Herald", "publishes_research", "shipment anomaly analysis", None, None, "Regional Herald"),
        ],
        hyps=[
            (1, "Systematic export-control evasion network operational at scale", 52, 67, "leading",
             "Customs anomalies corroborate earlier community chatter that was previously dismissed."),
            (2, "Statistical artifact from tariff reclassification changes", 40, 26, "candidate",
             "Reclassification schedule does not align with observed timing."),
        ],
        rels=[("brokers", "expands", "transshipment routes"), ("regional herald", "appears_in", "customs digest")],
        invalidators=["Customs office publishes methodology correction voiding anomaly", "Third-country import data shows benign re-export destinations"],
        history=[41, 39, 36, 58, 66, 73],
        obs=[("policy", 4), ("news", 6), ("community", 5), ("web", 4)],
        decision=None,
        contradiction={"statement": "Freight analyst attributes spike to seasonal electronics restock", "strength": 0.42},
        sensor_health={"web": "AVAILABLE", "news": "AVAILABLE", "github": "EMPTY", "jobs": "EMPTY", "policy": "AVAILABLE", "research": "EMPTY", "community": "AVAILABLE"},
    ),
]


def main(force=False):
    conn = psycopg2.connect(**PG)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if force:
        print("force: removing previously seeded demo signals…")
        cur.execute("""
            DELETE FROM user_feedback WHERE signal_id IN (SELECT signal_id FROM signals WHERE is_demo);
            DELETE FROM invalidators WHERE signal_id IN (SELECT signal_id FROM signals WHERE is_demo);
            DELETE FROM hypotheses WHERE signal_id IN (SELECT signal_id FROM signals WHERE is_demo);
            DELETE FROM contradictions WHERE signal_id IN (SELECT signal_id FROM signals WHERE is_demo);
            DELETE FROM observations WHERE signal_id IN (SELECT signal_id FROM signals WHERE is_demo);
            DELETE FROM signal_history WHERE signal_id IN (SELECT signal_id FROM signals WHERE is_demo);
            DELETE FROM relationships WHERE signal_id IN (SELECT signal_id FROM signals WHERE is_demo);
            UPDATE investigations SET signal_id = NULL WHERE signal_id IN (SELECT signal_id FROM signals WHERE is_demo);
            DELETE FROM events WHERE signal_id IN (SELECT signal_id FROM signals WHERE is_demo);
            DELETE FROM claims WHERE signal_id IN (SELECT signal_id FROM signals WHERE is_demo);
            DELETE FROM notifications WHERE signal_id IN (SELECT signal_id FROM signals WHERE is_demo);
            DELETE FROM actions WHERE signal_id IN (SELECT signal_id FROM signals WHERE is_demo);
            DELETE FROM signals WHERE is_demo;
        """)
        conn.commit()

    cur.execute("SELECT count(*) AS n FROM signals")
    if cur.fetchone()["n"] > 0 and not force:
        print("signals table not empty — skipping (use --force to reseed)")
        return

    rng = random.Random(42)
    for S in SEED_SIGNALS:
        run_id = str(uuid.uuid4())
        signal_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO signals (signal_id, title, topic, input_mode, status, classification,
                signal_score, confidence, dna, velocity, acceleration, articles_found,
                underlying_events, independent_sources, first_detected_at, last_updated_at,
                is_demo, scenario_key, embedding)
            VALUES (%s,%s,%s,'natural',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now(),%s,%s,%s)""",
            (signal_id, S["title"], S["topic"], S["status"], S["classification"],
             S["score"], S["confidence"], json.dumps(S["dna"]), S["velocity"], S["accel"],
             len(S["sources"]), S["events"], S["independent"],
             NOW - dt.timedelta(days=len(S["history"])), S["is_demo"], S["scenario"],
             "[" + ",".join(f"{rng.uniform(-0.05,0.05):.4f}" for _ in range(384)) + "]"))

        src_ids = {}
        for i, (pub, stype, cls, cred, group) in enumerate(S["sources"]):
            url = f"https://demo-signal.local/{uuid.UUID(int=rng.getrandbits(128)).hex[:12]}"
            cur.execute("""
                INSERT INTO sources (source_url,url_hash,source_type,publisher,published_at,
                    primary_or_secondary,credibility_score,independence_group,title,content_excerpt,run_id,metadata)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING source_id""",
                (url, uuid.UUID(int=rng.getrandbits(128)).hex[:16], stype, pub,
                 NOW - dt.timedelta(days=rng.randint(0, 6)),
                 "primary" if cls == "primary_announcement" else "secondary",
                 cred, f"ev_{group}", f"{S['title']} — {pub}",
                 f"Deterministic demo fixture for {pub}.", run_id,
                 json.dumps({"is_demo": True})))
            src_ids[i] = cur.fetchone()["source_id"]

        claim_rows = []
        for (actor, action, obj, qty, unit, pub) in S["claims"]:
            stmt = f"{actor} {action.replace('_', ' ')} {obj}"
            cur.execute("""
                INSERT INTO claims (signal_id, run_id, source_id, actor, action, object,
                    quantity, quantity_unit, statement, verification, embedding, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'unverified',%s,%s)""",
                (signal_id, run_id, src_ids[0], actor, action, obj, qty, unit, stmt,
                 "[" + ",".join(f"{rng.uniform(-0.05,0.05):.4f}" for _ in range(384)) + "]",
                 NOW - dt.timedelta(days=rng.randint(0, 3))))
            cur.execute("""
                INSERT INTO events (signal_id, source_id, actor, action, object, quantity,
                    occurred_at, confidence, embedding)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (signal_id, src_ids[0], actor, action, obj, qty,
                 NOW - dt.timedelta(days=rng.randint(0, 5)), round(rng.uniform(0.55, 0.9), 2),
                 "[" + ",".join(f"{rng.uniform(-0.05,0.05):.4f}" for _ in range(384)) + "]"))
            claim_rows.append(stmt)

        for (rank, stmt, prior, post, status, reasoning) in S["hyps"]:
            cur.execute("""
                INSERT INTO hypotheses (signal_id, rank, statement, prior_confidence,
                    posterior_confidence, status, reasoning)
                VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (signal_id, rank, stmt, prior, post, status, reasoning))

        for (subj, pred, obj_) in S["rels"]:
            cur.execute("""
                INSERT INTO relationships (signal_id, subject, predicate, object, weight,
                    evidence_count, first_seen_at, last_seen_at, is_new)
                VALUES (%s,%s,%s,%s,%s,%s,%s,now(),true)""",
                (signal_id, subj, pred, obj_, round(rng.uniform(0.3, 1.0), 2), rng.randint(1, 4),
                 NOW - dt.timedelta(days=rng.randint(1, 6))))

        for txt in S["invalidators"]:
            cur.execute("INSERT INTO invalidators (signal_id, condition_text) VALUES (%s,%s)",
                        (signal_id, txt))

        if S.get("contradiction"):
            c = S["contradiction"]
            cur.execute("""INSERT INTO contradictions (signal_id, evidence_url, statement, strength, found_by)
                           VALUES (%s,%s,%s,%s,'red_team')""",
                        (signal_id, "https://demo-signal.local/contradiction", c["statement"], c["strength"]))

        base = NOW - dt.timedelta(days=len(S["history"]))
        for j, sc in enumerate(S["history"]):
            cur.execute("""INSERT INTO signal_history (signal_id, score, confidence, status, recorded_at, note)
                           VALUES (%s,%s,%s,%s,%s,%s)""",
                        (signal_id, sc, max(10, S["confidence"] - (len(S['history']) - j) * 3),
                         "history", base + dt.timedelta(days=j), "seeded evolution point"))

        for days_ago in range(len(S["history"]) - 1, -1, -1):
            for (ch, vol) in S["obs"]:
                jitter = max(0, int(vol * rng.uniform(0.5, 1.4)))
                cur.execute("""INSERT INTO observations (signal_id, run_id, channel, metric, value,
                               observed_at, window_start, window_end, details)
                               VALUES (%s,%s,%s,'volume',%s,%s,%s,%s,%s)""",
                            (signal_id, run_id, ch, jitter,
                             base + dt.timedelta(days=(len(S["history"]) - 1 - days_ago)),
                             base + dt.timedelta(days=(len(S["history"]) - 1 - days_ago), hours=-24),
                             base + dt.timedelta(days=(len(S["history"]) - 1 - days_ago)),
                             json.dumps({"seeded": True})))

        started = NOW - dt.timedelta(days=len(S["history"]))
        cur.execute("""
            INSERT INTO investigations (run_id, n8n_execution_id, signal_id, trigger_mode,
                input_payload, research_plan, status, sources_searched, pages_retrieved,
                claims_extracted, events_normalized, duplicates_removed, independent_sources,
                hypotheses_formed, hypotheses_disproved, redteam_searches, final_score,
                started_at, finished_at, sensor_health, timeline_log)
            VALUES (%s,%s,%s,'monitor',%s,%s,'COMPLETED',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now(),%s,%s)""",
            (run_id, f"seed-{str(uuid.uuid4())[:8]}", signal_id,
             json.dumps({"topic": S["topic"], "scenario": S["scenario"], "seeded": True}),
             json.dumps({"queries": [S["topic"]], "counter_queries": [], "seeded": True}),
             len(S["sources"]) + 4, len(S["sources"]), len(S["claims"]), S["events"], 2,
             S["independent"], len(S["hyps"]),
             sum(1 for h in S["hyps"] if h[4] == "disproved"), 5, S["score"],
             started, json.dumps(S["sensor_health"]),
             json.dumps([{"stage": st, "detail": "seeded"} for st in
                         ["INPUT", "THINK", "SENSE", "INVESTIGATE", "CONNECT", "DETECT CHANGE",
                          "FORM HYPOTHESES", "RED TEAM", "VERIFY", "SCORE", "REMEMBER", "HUMAN LOOP"]])))

        cur.execute("""INSERT INTO notifications (signal_id, channel, severity, message, sent_at, status, detail)
                       VALUES (%s,'telegram',%s,%s,%s,'sent','seeded demo alert')""",
                    (signal_id, S["classification"].lower(),
                     f"Signal {S['classification']} ({S['score']}/100): {S['title']}",
                     started + dt.timedelta(minutes=2)))

        if S.get("decision"):
            dec, chan, comment = S["decision"]
            cur.execute("""INSERT INTO user_feedback (signal_id, decision, channel, comment, decided_via, decided_at)
                           VALUES (%s,%s,%s,%s,'seed',%s)""",
                        (signal_id, dec, chan, comment, started + dt.timedelta(hours=1)))

        print(f"seeded [{S['classification']:>11}] {S['score']:>2}/100  {S['title'][:60]}")

    conn.commit()
    cur.close()
    conn.close()
    print("\nSEED COMPLETE")


if __name__ == "__main__":
    main(force="--force" in sys.argv)
