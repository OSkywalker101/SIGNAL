"""Import or update SIGNAL workflows in n8n via internal REST API (urllib + cookie auth).
If tools/workflow_ids.json exists and those workflows are alive, updates in place;
otherwise creates fresh. Order matters: Escalation Sub-flow first (its ID is injected).
"""
import json, pathlib, sys, urllib.request, urllib.error

BASE = "http://localhost:5679"
ROOT = pathlib.Path(__file__).resolve().parent.parent
WFD = ROOT / "n8n" / "workflows"
ENV = {}
for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        ENV[k.strip()] = v.strip()


def req(method, path, body=None, headers=None, cookies=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        r.add_header(k, v)
    if cookies:
        r.add_header("Cookie", cookies)
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            sc = resp.headers.get("Set-Cookie", "")
            raw = resp.read().decode()
            try:
                payload = json.loads(raw) if raw else {}
            except Exception:
                payload = {"raw": raw[:300]}
            return resp.status, payload, (sc.split(";")[0] if sc else cookies)
    except urllib.error.HTTPError as e:
        return e.code, {"err": e.read().decode()[:400]}, cookies


st, _, cookie = req("POST", "/rest/owner/setup",
                    {"email": ENV["N8N_ADMIN_EMAIL"], "password": ENV["N8N_ADMIN_PASSWORD"],
                     "firstName": "SIGNAL", "lastName": "Admin"})
st, _, cookie = req("POST", "/rest/login",
                    {"emailOrLdapLoginId": ENV["N8N_ADMIN_EMAIL"], "password": ENV["N8N_ADMIN_PASSWORD"]})
assert st == 200, f"login failed {st}"
HDR = {"browser-id": "signal"}

ORDER = [
    "signal-escalation-subflow.json",
    "signal-error-sentinel.json",
    "signal-briefs-scheduler.json",
    "signal-telegram-command-center.json",
    "signal-intelligence-pipeline.json",
]

ids_file = ROOT / "tools" / "workflow_ids.json"
existing = {}
if ids_file.exists():
    for fname, wid in json.loads(ids_file.read_text()).items():
        st, resp, _ = req("GET", f"/rest/workflows/{wid}", headers=HDR, cookies=cookie)
        if st == 200:
            d = resp.get("data") or resp
            existing[fname] = wid
            print(f"found [{wid}] active={d.get('active')} {fname}")
        else:
            print(f"stale id {wid} for {fname}")
created = dict(existing)

for fname in ORDER:
    wf = json.loads((WFD / fname).read_text())
    for n in wf.get("nodes", []):
        params = n.get("parameters")
        if not isinstance(params, dict):
            continue
        rl = params.get("workflowId")
        if isinstance(rl, dict) and rl.get("value") == "__ESCALATION_WF_ID__":
            rl["value"] = created["signal-escalation-subflow.json"]
    body = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": wf.get("settings", {}),
        "pinData": {},
    }
    wid = created.get(fname)
    if wid:
        st, resp, _ = req("PUT", f"/rest/workflows/{wid}", body, headers=HDR, cookies=cookie)
        if st not in (200, 201):
            st2, resp2, _ = req("PATCH", f"/rest/workflows/{wid}", body, headers=HDR, cookies=cookie)
            st, resp = st2, resp2
        action = "updated"
    else:
        st, resp, _ = req("POST", "/rest/workflows", body, headers=HDR, cookies=cookie)
        action = "created"
    if st not in (200, 201):
        print(f"FAIL {fname}: {st} {str(resp)[:300]}")
        sys.exit(1)
    wid = (resp.get("data") or resp).get("id") or wid
    created[fname] = wid
    print(f"{action} [{wid}] {wf['name']}")

ids_file.write_text(json.dumps(created, indent=1))

# Activate: deactivate first if active (fresh version), then activate with versionId
for fname in ORDER:
    wid = created[fname]
    st, resp, _ = req("GET", f"/rest/workflows/{wid}", headers=HDR, cookies=cookie)
    d = resp.get("data") or resp
    vid = d.get("versionId")
    if d.get("active"):
        st, _, _ = req("POST", f"/rest/workflows/{wid}/deactivate", {"versionId": vid},
                       headers=HDR, cookies=cookie)
        print(f"deactivate {fname}: {st}")
        st, resp, _ = req("GET", f"/rest/workflows/{wid}", headers=HDR, cookies=cookie)
        vid = (resp.get("data") or resp).get("versionId")
    st, resp, _ = req("POST", f"/rest/workflows/{wid}/activate", {"versionId": vid},
                      headers=HDR, cookies=cookie)
    ok = st == 200 and ((resp.get("data") or resp).get("active") is True)
    print(f"activate {fname}: {st} active={ok}")
    if not ok:
        print(f"  {str(resp)[:300]}")

print("IMPORT COMPLETE")
