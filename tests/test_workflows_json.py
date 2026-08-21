"""Structural validation of the generated n8n workflow JSONs."""
import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
WFD = ROOT / "n8n" / "workflows"

FILES = [
    "signal-intelligence-pipeline.json",
    "signal-telegram-command-center.json",
    "signal-briefs-scheduler.json",
    "signal-error-sentinel.json",
    "signal-escalation-subflow.json",
]

SECRET_PATTERNS = [
    re.compile(r"gsk_[A-Za-z0-9]{10,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{25,}"),
    re.compile(r"\d{8,10}:AA[A-Za-z0-9_\-]{30,}"),  # telegram bot token shape
]


@pytest.mark.parametrize("fname", FILES)
def test_file_exists_and_parses(fname):
    wf = json.loads((WFD / fname).read_text(encoding="utf-8"))
    assert wf["name"], fname
    assert isinstance(wf["nodes"], list) and wf["nodes"]
    assert isinstance(wf["connections"], dict)


@pytest.mark.parametrize("fname", FILES)
def test_no_unscoped_langchain_types(fname):
    wf = json.loads((WFD / fname).read_text(encoding="utf-8"))
    for n in wf["nodes"]:
        assert not n["type"].startswith("n8n-nodes-langchain."), (
            f"{fname}:{n['name']} uses unscoped prefix {n['type']} — this build requires @n8n/ scope")


def test_primary_pipeline_size():
    wf = json.loads((WFD / "signal-intelligence-pipeline.json").read_text(encoding="utf-8"))
    assert len(wf["nodes"]) >= 100, "primary pipeline lost nodes"


@pytest.mark.parametrize("fname", FILES)
def test_connections_reference_existing_nodes(fname):
    wf = json.loads((WFD / fname).read_text(encoding="utf-8"))
    names = {n["name"] for n in wf["nodes"]}
    problems = []
    for src, conn in wf["connections"].items():
        if src not in names:
            problems.append(f"connection source '{src}' is not a node")
        for branch in (conn.get("main") or []):
            for tgt in branch or []:
                if tgt["node"] not in names:
                    problems.append(f"'{src}' -> missing target '{tgt['node']}'")
    # ai sub-node connections (model links)
    for src, conn in wf["connections"].items():
        for ctype, branches in (conn.items() if isinstance(conn, dict) else []):
            if ctype == "main":
                continue
            for branch in branches or []:
                for tgt in branch or []:
                    if tgt.get("type", "ai_languageModel").startswith("ai_") and tgt["node"] not in names:
                        problems.append(f"{src}:{ctype} -> missing '{tgt['node']}'")
    assert not problems, f"{fname}: {problems[:5]}"


@pytest.mark.parametrize("fname", FILES)
def test_expressions_have_equals_prefix(fname):
    """Any parameter string containing {{ }} must start with '=' to be evaluated."""
    wf = json.loads((WFD / fname).read_text(encoding="utf-8"))
    problems = []

    def walk(node_name, key_path, v):
        if isinstance(v, str):
            if "{{" in v and not v.startswith("=") and not v.startswith("{"):
                problems.append(f"{node_name}.{key_path}: {v[:70]}")
        elif isinstance(v, dict):
            for k, vv in v.items():
                walk(node_name, f"{key_path}.{k}", vv)
        elif isinstance(v, list):
            for i, vv in enumerate(v):
                walk(node_name, f"{key_path}[{i}]", vv)

    for n in wf["nodes"]:
        if n["type"] == "n8n-nodes-base.stickyNote":
            continue
        walk(n["name"], "parameters", n.get("parameters", {}))
    assert not problems, f"{fname}: expressions without '=' prefix: {problems[:5]}"


@pytest.mark.parametrize("fname", FILES)
def test_no_embedded_secrets(fname):
    raw = (WFD / fname).read_text(encoding="utf-8")
    hits = [p.pattern for p in SECRET_PATTERNS if p.search(raw)]
    assert not hits, f"{fname}: possible secrets embedded: {hits}"


def test_adapter_nodes_ship_disabled():
    wf = json.loads((WFD / "signal-intelligence-pipeline.json").read_text(encoding="utf-8"))
    by_name = {n["name"]: n for n in wf["nodes"]}
    cal = by_name.get("📅 Google Calendar Reminder")
    notion = by_name.get("📝 Notion Memory Page")
    assert cal and cal.get("disabled") is True, "calendar adapter must ship disabled until OAuth connected"
    assert notion and notion.get("disabled") is True, "notion adapter must ship disabled until creds connected"


def test_webhook_paths_unique():
    paths = []
    for fname in FILES:
        wf = json.loads((WFD / fname).read_text(encoding="utf-8"))
        for n in wf["nodes"]:
            if n["type"].endswith(".webhook"):
                paths.append(n["parameters"].get("path"))
    assert len(paths) == len(set(paths)), f"duplicate webhook paths: {paths}"
