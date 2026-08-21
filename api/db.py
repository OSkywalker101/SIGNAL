"""Thin PostgreSQL access layer (psycopg2, RealDictCursor)."""
import json
import contextlib

import psycopg2
import psycopg2.extras

from . import config


def fetch_all(sql, params=None):
    with contextlib.closing(psycopg2.connect(**config.PG)) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            return [dict(r) for r in cur.fetchall()]


def fetch_one(sql, params=None):
    rows = fetch_all(sql, params)
    return rows[0] if rows else None


def execute(sql, params=None):
    with contextlib.closing(psycopg2.connect(**config.PG)) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            conn.commit()
            return cur.rowcount


def execute_returning(sql, params=None):
    with contextlib.closing(psycopg2.connect(**config.PG)) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            row = cur.fetchone()
            conn.commit()
            return dict(row) if row else None


def jparse(v):
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return v
    try:
        return json.loads(v)
    except Exception:
        return v
