"""SIGNAL API — configuration from repo .env."""
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load_dotenv():
    for line in (ROOT / ".env").read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()


def env(key, default=None):
    return os.environ.get(key, default)


N8N_BASE = f"http://localhost:{env('SIGNAL_N8N_PORT', '5679')}"
WEBHOOK_URL = f"{N8N_BASE}/webhook/signal/pipeline"

PG = {
    "host": env("SIGNAL_PG_HOST", "localhost"),
    "port": int(env("SIGNAL_PG_PORT", "5432")),
    "user": env("POSTGRES_USER", "signal"),
    "password": env("POSTGRES_PASSWORD", "change_me_in_prod"),
    "dbname": env("POSTGRES_DB", "signal"),
}

API_PORT = int(env("SIGNAL_API_PORT", "8000"))

DECISION_STATUS = {
    "INVESTIGATE": "INVESTIGATING",
    "WATCH": "WATCH",
    "DISMISS": "DISMISSED",
    "CONFIRM": "CONFIRMED",
    "REMIND": "WATCH",
}
