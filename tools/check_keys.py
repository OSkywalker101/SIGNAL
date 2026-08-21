"""Validate SIGNAL provider keys from .env against live APIs.
Usage: python tools/check_keys.py
Exit code 0 if at least one LLM provider works; 2 otherwise.
"""
import json, pathlib, sys, urllib.request, urllib.error

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENV = {}
for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        ENV[k.strip()] = v.strip()


def probe(url, key):
    r = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, None
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:120]
    except Exception as e:
        return None, str(e)[:120]


def main():
    results = []
    gk = ENV.get("GROQ_API_KEY", "").strip()
    if gk:
        st, err = probe("https://api.groq.com/openai/v1/models", gk)
        results.append(("groq", st))
        print(f"GROQ_API_KEY   {'OK' if st == 200 else 'FAIL ' + str(st)}  {err or ''}")
        if st != 200:
            print("  -> rotate the key at https://console.groq.com/keys, update .env, then:")
            print("     python tools/bootstrap_n8n.py && python tools/import_workflows.py")
    else:
        print("GROQ_API_KEY   not set")

    ok = ENV.get("OPENROUTER_API_KEY", "").strip()
    if ok:
        st, err = probe("https://openrouter.ai/api/v1/models", ok)
        results.append(("openrouter", st))
        print(f"OPENROUTER_KEY {'OK' if st == 200 else 'FAIL ' + str(st)}  {err or ''}")
    else:
        print("OPENROUTER_API_KEY not set (deterministic rules fallback will be used)")

    tg = ENV.get("TELEGRAM_BOT_TOKEN", "").strip()
    print(f"TELEGRAM_BOT_TOKEN {'set - alerts enabled' if tg else 'not set - alerts gracefully skipped'}")
    gc = ENV.get("GOOGLE_CALENDAR_ID", "").strip()
    nt = ENV.get("NOTION_DATABASE_ID", "").strip()
    print(f"Adapters: calendar={'set' if gc else 'unset'} notion={'set' if nt else 'unset'} (enable the two disabled nodes after connecting OAuth creds)")

    llm_ok = any(status == 200 for _, status in results if _ in ("groq", "openrouter"))
    print("\nLLM strategist:", "OPERATIONAL" if llm_ok else "degraded -> deterministic fallback")
    sys.exit(0 if llm_ok else 2)


if __name__ == "__main__":
    main()
