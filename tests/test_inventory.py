import hashlib
import json
import subprocess
import sys

from mitmproxy import flow as mitm_flow
from mitmproxy import http
from mitmproxy import io as mitm_io
from mitmproxy.test import tflow

from conftest import TOOLS, load_tool

SECRET = "sk-test-SECRET-TOKEN-VALUE"
BODY_SENTINEL = "SENTINEL-SYSTEM-PROMPT-TEXT"
USER_ID = "user_SENTINEL_ACCOUNT"
USAGE_START = {"input_tokens": 3, "cache_creation_input_tokens": 10, "cache_read_input_tokens": 20, "output_tokens": 1}
USAGE_FINAL = USAGE_START | {"output_tokens": 5}


def sse(*events) -> bytes:
    return b"".join(f"event: {name}\ndata: {json.dumps(data)}\n\n".encode() for name, data in events)


def good_stream() -> bytes:
    return sse(
        ("message_start", {"type": "message_start",
                           "message": {"id": "msg_test1", "model": "claude-test", "usage": USAGE_START}}),
        ("content_block_start", {"type": "content_block_start", "index": 0,
                                 "content_block": {"type": "text", "text": ""}}),
        ("ping", {"type": "ping"}),
        ("content_block_delta", {"type": "content_block_delta", "index": 0,
                                 "delta": {"type": "text_delta", "text": "Hello"}}),
        ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        ("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn"},
                           "usage": {"output_tokens": 5}}),
        ("message_stop", {"type": "message_stop"}),
    )


def make_flow(host: str, method: str, path: str, body: bytes = b"", content_type: str = "application/json"):
    flow = tflow.tflow(resp=True)
    flow.request.host, flow.request.port, flow.request.scheme = host, 443, "https"
    flow.request.method, flow.request.path = method, path
    flow.request.headers = http.Headers(
        host=host,
        authorization=SECRET,
        content_type="application/json",
        anthropic_version="2023-06-01",
    )
    flow.request.headers["x-claude-code-request-class"] = "main"
    flow.request.headers["x-claude-code-session-id"] = "SENTINEL-SESSION"
    flow.request.content = body
    flow.response.headers = http.Headers(content_type=content_type)
    flow.response.content = b""
    return flow


def make_run(tmp_path, stream: bytes, extra_flows=()):
    run = tmp_path / "run"
    (run / "streams").mkdir(parents=True)
    (run / "steps" / "01").mkdir(parents=True)
    request = {
        "model": "claude-test", "max_tokens": 100, "stream": True,
        "metadata": {"user_id": USER_ID},
        "system": [{"type": "text", "text": "attribution"},
                   {"type": "text", "text": BODY_SENTINEL, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": [{"type": "text", "text": "Say hello."}]}],
        "tools": [],
        "thinking": {"type": "adaptive"},
    }
    flow = make_flow("api.anthropic.com", "POST", "/v1/messages?beta=true",
                     json.dumps(request).encode(), "text/event-stream")
    with open(run / "flows.mitm", "wb") as f:
        writer = mitm_io.FlowWriter(f)
        for fl in (flow, *extra_flows):
            writer.add(fl)

    (run / "streams" / f"{flow.id}.sse").write_bytes(stream)
    records = [
        {"event": "start", "flow_id": flow.id, "t_ns": 1, "content_type": "text/event-stream", "content_encoding": ""},
        {"event": "chunk", "t_ns": 2, "offset": 0, "len": len(stream)},
        {"event": "end", "reason": "eof", "t_ns": 3, "total": len(stream),
         "sha256": hashlib.sha256(stream).hexdigest()},
    ]
    (run / "streams" / f"{flow.id}.chunks.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))

    cli = [
        {"type": "system", "subtype": "init", "session_id": "SENTINEL-SESSION"},
        {"type": "assistant", "message": {"id": "msg_test1", "usage": USAGE_START}},
        {"type": "result", "subtype": "success", "is_error": False, "num_turns": 1,
         "result": "Hello", "usage": USAGE_FINAL},
    ]
    (run / "steps" / "01" / "stdout.jsonl").write_text("".join(json.dumps(e) + "\n" for e in cli))
    (run / "manifest.json").write_text(json.dumps({
        "run_id": "synthetic", "case": "A1", "auth_kind": "oauth",
        "steps": [{"n": 1, "exit_code": 0}], "claude_env_names": ["HOME", "PATH"],
    }))
    return run


def inventory(run):
    return subprocess.run([sys.executable, str(TOOLS / "inventory"), str(run)], capture_output=True, text=True)


def test_classifies_synthetic_run(tmp_path):
    done = inventory(make_run(tmp_path, good_stream()))
    out = done.stdout
    assert done.returncode == 0, out + done.stderr
    assert "inference       POST api.anthropic.com /v1/messages?beta=true 200" in out
    assert "UNKNOWN flows: 0" in out
    assert "request: model=claude-test stream=True system=2 blocks messages=1 tools=0" in out
    assert "cache_control markers: messages x0, system x1, tools x0" in out
    assert 'thinking: {"type": "adaptive"}' in out
    assert "message roles: user x1; message content block types: text x1" in out
    assert "message_start x1" in out and "stop_reason=end_turn" in out
    assert "usage final:            input_tokens=3 cache_creation_input_tokens=10 " \
           "cache_read_input_tokens=20 output_tokens=5" in out
    assert "in_sse=yes usage_equals_sse_final=no usage_equals_sse_message_start=yes" in out
    assert "result usage equals that sum: yes" in out


def test_output_is_sanitized(tmp_path):
    out = inventory(make_run(tmp_path, good_stream())).stdout
    for forbidden in (SECRET, BODY_SENTINEL, USER_ID, "SENTINEL-SESSION", "Say hello"):
        assert forbidden not in out
    assert "authorization" in out and "x-claude-code-session-id" in out
    assert "anthropic-version: 2023-06-01" in out
    assert "x-claude-code-request-class: main" in out


def test_fails_on_unknown_host(tmp_path):
    stray = make_flow("evil.example.com", "GET", "/collect/0123456789abcdef0123?token=abcdef")
    done = inventory(make_run(tmp_path, good_stream(), extra_flows=[stray]))
    assert done.returncode == 1
    assert "! flow 2: UNKNOWN endpoint GET evil.example.com/collect/<id>" in done.stdout
    assert "UNKNOWN flows: 1" in done.stdout
    assert "token=<v>" in done.stdout and "abcdef" not in done.stdout


def test_flow_without_response(tmp_path):
    def cut_off(host, path):
        flow = make_flow(host, "POST", path)
        flow.response = None
        flow.error = mitm_flow.Error("Client disconnected.")
        return flow

    telemetry = inventory(make_run(tmp_path / "a", good_stream(),
                                   extra_flows=[cut_off("api.anthropic.com", "/api/event_logging/v2/batch")]))
    assert telemetry.returncode == 0, telemetry.stdout
    assert "- flow 2: telemetry flow has no response (Client disconnected.)" in telemetry.stdout

    inference = inventory(make_run(tmp_path / "b", good_stream(),
                                   extra_flows=[cut_off("api.anthropic.com", "/v1/messages")]))
    assert inference.returncode == 1
    assert "! flow 2: inference flow has no response" in inference.stdout


def test_fails_on_unknown_sse_event_and_block(tmp_path):
    stream = good_stream() + sse(
        ("surprise", {"type": "surprise"}),
        ("content_block_start", {"type": "content_block_start", "index": 1, "content_block": {"type": "hologram"}}),
    )
    done = inventory(make_run(tmp_path, stream))
    assert done.returncode == 1
    assert "unknown SSE event type 'surprise'" in done.stdout
    assert "unknown content block type 'hologram'" in done.stdout


def test_fails_on_truncated_stream_file(tmp_path):
    run = make_run(tmp_path, good_stream())
    (sse_file,) = (run / "streams").glob("*.sse")
    sse_file.write_bytes(sse_file.read_bytes()[:-10])
    done = inventory(run)
    assert done.returncode == 1
    assert "does not match the size/sha256" in done.stdout


def test_classify_and_sanitize_units():
    inv = load_tool("inventory")
    assert inv.classify("POST", "api.anthropic.com", "/v1/messages?beta=true") == "inference"
    assert inv.classify("POST", "api.anthropic.com", "/v1/messages/count_tokens?beta=true") == "count_tokens"
    assert inv.classify("GET", "api.anthropic.com", "/v1/messages") == "UNKNOWN"
    assert inv.classify("POST", "api.anthropic.com.evil.test", "/v1/messages") == "UNKNOWN"
    assert inv.classify("POST", "http-intake.logs.us5.datadoghq.com", "/api/v2/logs") == "telemetry"
    assert inv.classify("GET", "api.githubcopilot.com", "/mcp/") == "mcp"
    assert inv.classify("DELETE", "api.githubcopilot.com", "/mcp/") == "UNKNOWN"
    assert inv.sanitize_path("/api/eval/sdk-AbCdEfGhIjKlMnOp") == "/api/eval/<id>"
    assert inv.sanitize_path("/api/claude_code_penguin_mode") == "/api/claude_code_penguin_mode"
    assert inv.sanitize_path("/a/123e4567-e89b-12d3-a456-426614174000/b?beta=true&limit=1000&q=me@x.y") \
        == "/a/<uuid>/b?beta=true&limit=1000&q=<v>"
    assert inv.parse_sse(b"event: a\r\ndata: 1\r\ndata: 2\r\n\r\n: c\n\ndata: x\n\n") == [("a", "1\n2"), ("message", "x")]
