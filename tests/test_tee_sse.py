import hashlib
import http.client
import json
import time

from mitmproxy import io as mitm_io

from conftest import PAUSE, PLAIN_BODY, SSE_EVENTS


def fetch(proxy_port: int, url: str):
    """GET through the proxy; return (body, monotonic time of each read)."""
    conn = http.client.HTTPConnection("127.0.0.1", proxy_port, timeout=30)
    conn.request("GET", url)
    resp = conn.getresponse()
    assert resp.status == 200
    body, times = b"", []
    while True:
        data = resp.read1(65536)
        if not data:
            break
        times.append(time.monotonic())
        body += data
    conn.close()
    return body, times


def sidecar_records(proxy):
    (path,) = proxy.streams.glob("*.chunks.jsonl")
    return path, [json.loads(line) for line in path.read_text().splitlines()]


def test_tee_bytes_equal_client_bytes(proxy, sse_server):
    body, _ = fetch(proxy.port, f"http://127.0.0.1:{sse_server.server_port}/sse")
    sent = hashlib.sha256(b"".join(SSE_EVENTS)).hexdigest()
    assert hashlib.sha256(body).hexdigest() == sent

    proxy.stop()
    (sse_file,) = proxy.streams.glob("*.sse")
    assert hashlib.sha256(sse_file.read_bytes()).hexdigest() == sent

    _, records = sidecar_records(proxy)
    assert [r["event"] for r in records[:1] + records[-1:]] == ["start", "end"]
    chunks = records[1:-1]
    assert all(r["event"] == "chunk" for r in chunks)
    offset = 0
    for r in chunks:
        assert r["offset"] == offset
        offset += r["len"]
    assert records[-1] == records[-1] | {"reason": "eof", "total": len(body), "sha256": sent}


def test_stream_is_not_buffered(proxy, sse_server):
    _, recv_times = fetch(proxy.port, f"http://127.0.0.1:{sse_server.server_port}/sse")
    send_times = sse_server.send_times
    assert len(send_times) == len(SSE_EVENTS)
    # the client had the first event before the server sent the last one
    assert recv_times[0] < send_times[-1]
    assert recv_times[0] - send_times[0] < PAUSE

    proxy.stop()
    _, records = sidecar_records(proxy)
    chunk_times = [r["t_ns"] for r in records if r["event"] == "chunk"]
    assert len(chunk_times) >= len(SSE_EVENTS)
    assert (chunk_times[-1] - chunk_times[0]) / 1e9 > PAUSE * (len(SSE_EVENTS) - 1) * 0.8


def test_non_sse_is_left_alone_and_streams_are_traceable(proxy, sse_server):
    base = f"http://127.0.0.1:{sse_server.server_port}"
    plain, _ = fetch(proxy.port, base + "/plain")
    assert plain == PLAIN_BODY
    fetch(proxy.port, base + "/sse")
    proxy.stop()

    with open(proxy.flows, "rb") as f:
        flows = {flow.request.path: flow for flow in mitm_io.FlowReader(f).stream()}
    assert flows["/plain"].response.raw_content == PLAIN_BODY
    # streamed: the tee file is the only copy of the body
    assert not flows["/sse"].response.raw_content
    assert sorted(p.name for p in proxy.streams.iterdir()) == [
        f"{flows['/sse'].id}.chunks.jsonl",
        f"{flows['/sse'].id}.sse",
    ]
