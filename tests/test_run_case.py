import json
import os
import subprocess
import sys

from conftest import MITMDUMP, SSE_EVENTS, TOOLS, free_port

ENV_NAMES = ["HOME", "HTTPS_PROXY", "NODE_EXTRA_CA_CERTS", "PATH", "PWD", "SHLVL"]

# Stand-in for the claude binary: the prompt is the URL to call. It reports its
# environment and arguments on stderr and talks to the local test server
# through the proxy it was given, like the real CLI would.
FAKE_CLAUDE = r'''#!{python}
import http.client, json, os, sys
from urllib.parse import urlsplit
if "--version" in sys.argv:
    print("0.0.0 (Fake Claude)")
    sys.exit(0)
print(json.dumps({{"env": sorted(os.environ), "argv": sys.argv[1:], "cwd": os.getcwd()}}), file=sys.stderr)
proxy = urlsplit(os.environ["HTTPS_PROXY"])
conn = http.client.HTTPConnection(proxy.hostname, proxy.port, timeout=30)
conn.request("POST", sys.argv[sys.argv.index("-p") + 1], body=b"{{}}", headers={{"x-api-key": "fake"}})
body = conn.getresponse().read()
print(json.dumps({{"type": "system", "subtype": "init", "session_id": "sess-fake-1"}}))
print(json.dumps({{"type": "result", "subtype": "success", "result": str(len(body))}}))
'''


def make_fake_claude(tmp_path):
    fake = tmp_path / "bin" / "claude"
    fake.parent.mkdir()
    fake.write_text(FAKE_CLAUDE.format(python=sys.executable))
    fake.chmod(0o755)
    return fake


def test_refuses_scratch_under_instruction_files(tmp_path, confdir):
    (tmp_path / "project").mkdir()
    (tmp_path / "project" / "CLAUDE.md").write_text("leak")
    done = subprocess.run(
        [sys.executable, str(TOOLS / "run_case"), "--port", str(free_port()), "--logs-dir", str(tmp_path / "logs"),
         "--scratch-root", str(tmp_path / "project" / "deep" / "scratch"), "--confdir", str(confdir),
         "--claude-bin", str(make_fake_claude(tmp_path)), "--mitmdump-bin", str(MITMDUMP), "prompt"],
        capture_output=True, text=True, timeout=60,
    )
    assert done.returncode == 2
    assert "would inherit instruction files" in done.stderr and "project/CLAUDE.md" in done.stderr
    assert not (tmp_path / "logs").exists()


def test_run_case_with_fake_claude(tmp_path, confdir, sse_server):
    fake = make_fake_claude(tmp_path)
    (confdir / "mitmproxy-ca-cert.pem").touch()
    url = f"http://127.0.0.1:{sse_server.server_port}/v1/messages"
    logs = tmp_path / "logs"

    env = os.environ | {"LEAK_CANARY": "1", "CLAUDECODE": "1"}
    done = subprocess.run(
        [sys.executable, str(TOOLS / "run_case"), "--case", "T", "--model", "test-model",
         "--port", str(free_port()), "--logs-dir", str(logs), "--confdir", str(confdir),
         "--scratch-root", str(tmp_path / "scratch"), "--claude-bin", str(fake), "--mitmdump-bin", str(MITMDUMP), url, url],
        capture_output=True, text=True, env=env, timeout=120,
    )
    assert done.returncode == 0, done.stdout + done.stderr

    (run,) = logs.iterdir()
    assert run.name.endswith("-T")
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["claude_code_version"] == "0.0.0 (Fake Claude)"
    assert manifest["mitmproxy_version"].startswith("Mitmproxy")
    assert manifest["auth_kind"] == "api_key"
    assert manifest["mitmdump_exit_code"] == 0
    assert manifest["error"] is None
    assert [s["exit_code"] for s in manifest["steps"]] == [0, 0]
    assert manifest["claude_env_names"] == ENV_NAMES
    assert all(s["started_at"] <= s["ended_at"] for s in manifest["steps"])

    seen = [json.loads((run / "steps" / n / "stderr.txt").read_text()) for n in ("01", "02")]
    for step in seen:
        # LC_CTYPE is set by the Python interpreter of the fake itself
        assert [name for name in step["env"] if name != "LC_CTYPE"] == ENV_NAMES
        assert step["cwd"] == str(tmp_path / "scratch" / run.name) == manifest["scratch_dir"]
        assert step["argv"][:5] == ["-p", url, "--output-format", "stream-json", "--verbose"]
        assert step["argv"][5:7] == ["--model", "test-model"]
    assert "--resume" not in seen[0]["argv"]
    assert seen[1]["argv"][-2:] == ["--resume", "sess-fake-1"]

    stdout = (run / "steps" / "01" / "stdout.jsonl").read_text().splitlines()
    assert json.loads(stdout[-1])["result"] == str(len(b"".join(SSE_EVENTS)))
    assert manifest["scratch_entries_left"] == 0 and not (tmp_path / "scratch" / run.name).exists()
    assert len(list((run / "streams").glob("*.sse"))) == 2
    assert (run / "flows.mitm").stat().st_size > 0
