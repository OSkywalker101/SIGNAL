"""Syntax-check every JS snippet in wf_codes.py with node --check (skips if node missing)."""
import pathlib
import subprocess
import sys
import tempfile

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "tools"))
import wf_codes as C  # noqa: E402

SNIPPETS = {k: v for k, v in vars(C).items()
            if isinstance(v, str) and k.isupper() and len(v) > 40}


def node_available():
    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


@pytest.mark.skipif(not node_available(), reason="node not available")
@pytest.mark.parametrize("name", sorted(SNIPPETS))
def test_snippet_parses(name):
    wrapped = "(async function(){\n" + SNIPPETS[name] + "\n})"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(wrapped)
        path = f.name
    r = subprocess.run(["node", "--check", path], capture_output=True, text=True)
    assert r.returncode == 0, f"{name} syntax error:\n{r.stderr[-400:]}"


def test_no_input_first_without_fallback_in_context_nodes():
    """Nodes downstream of postgres must not rely on $input for pipeline context."""
    for name in ("REEMERGE_CHECK", "BUILD_BULK_WRITES"):
        code = SNIPPETS[name]
        assert "$(\"" in code or "$('" in code or "$( '" in code, f"{name} should read context from a named node"
