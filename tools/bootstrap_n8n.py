"""Bootstrap fresh n8n via internal REST (session-cookie auth): owner setup, login, credentials."""
import json, sys, time, urllib.request, urllib.error, pathlib

BASE = "http://localhost:5679"
ROOT = pathlib.Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
OUT = pathlib.Path(__file__).resolve().parent / "cred_ids.json"


def env(key):
    for line in ENV_PATH.read_text().splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip()
    return ""


def req(method, path, body=None, headers=None, cookies=None, timeout=30):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        r.add_header(k, v)
    if cookies:
        r.add_header("Cookie", cookies)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            sc = resp.headers.get("Set-Cookie", "")
            raw = resp.read().decode()
            try:
                payload = json.loads(raw)
            except Exception:
                payload = {"raw": raw[:300]}
            return resp.status, payload, (sc.split(";")[0] if sc else cookies)
    except urllib.error.HTTPError as e:
        return e.code, {"err": e.read().decode()[:400]}, cookies


def wait_n8n(minutes=6):
    deadline = time.time() + minutes * 60
    while time.time() < deadline:
        try:
            s, _, _ = req("GET", "/healthz")
            if s == 200:
                print("n8n up")
                return True
        except Exception:
            pass
        time.sleep(3)
    return False


def main():
    if not wait_n8n():
        sys.exit("n8n did not come up")
    email, password = env("N8N_ADMIN_EMAIL"), env("N8N_ADMIN_PASSWORD")

    s, b, _ = req("POST", "/rest/owner/setup",
                  {"email": email, "firstName": "SIGNAL", "lastName": "Admin", "password": password})
    print("owner setup:", s)

    s, b, cookie = req("POST", "/rest/login", {"emailOrLdapLoginId": email, "password": password})
    if s != 200:
        sys.exit(f"login failed: {s}")
    print("login ok")

    hdr = {"browser-id": "signal"}

    def cred(name, ctype, data):
        body = {"name": name, "type": ctype, "data": data}
        s, b2, _ = req("POST", "/rest/credentials", body, headers=hdr, cookies=cookie)
        if s in (200, 201):
            cid = (b2.get("data") or {}).get("id") if isinstance(b2.get("data"), dict) else None
            if not cid and isinstance(b2, dict):
                cid = b2.get("id")
            print(f"credential '{name}' -> {cid}")
            return cid
        # list existing
        s2, lst, _ = req("GET", "/rest/credentials", headers=hdr, cookies=cookie)
        items = []
        if isinstance(lst, dict):
            d = lst.get("data")
            if isinstance(d, dict):
                items = d.get("items") or d.get("credentials") or []
            elif isinstance(d, list):
                items = d
        for c in items:
            if isinstance(c, dict) and c.get("name") == name:
                print(f"credential '{name}' exists -> {c.get('id')}")
                return c.get("id")
        print(f"credential '{name}' FAILED: {s} {str(b2)[:250]}")
        return None

    ids = {
        "postgres": cred("Signal Postgres", "postgres",
                         {"host": "postgres", "port": 5432, "database": env("POSTGRES_DB"),
                          "user": env("POSTGRES_USER"), "password": env("POSTGRES_PASSWORD"),
                          "ssl": "disable"}),
        "openai_groq": cred("Groq OpenAI-compatible", "openAiApi", {"apiKey": env("GROQ_API_KEY")}),
        "telegram": None,
    }
    tok = env("TELEGRAM_BOT_TOKEN")
    if tok:
        ids["telegram"] = cred("Signal Telegram", "telegramApi", {"accessToken": tok})

    OUT.write_text(json.dumps(ids, indent=2))
    print("saved", OUT)


if __name__ == "__main__":
    main()
