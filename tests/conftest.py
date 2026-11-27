import http.server
import importlib.machinery
import importlib.util
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
TOOLS = REPO / "tools"
MITMDUMP = Path(sys.executable).parent / "mitmdump"

PAUSE = 0.4
# Deliberately awkward: CRLF line ends, multi-byte UTF-8, bytes that are not
# valid UTF-8, and one event larger than a socket buffer.
SSE_EVENTS = [
    b'event: message_start\ndata: {"n": 1}\n\n',
    b'event: ping\r\ndata: {"n": 2, "s": "\xd0\xbf\xd1\x80\xd0\xb8\xd0\xb2\xd0\xb5\xd1\x82"}\r\n\r\n',
    b": comment with raw bytes \x00\xff\xfe\n\n",
    b"event: message_stop\ndata: " + b"x" * 70000 + b"\n\n",
]
PLAIN_BODY = b'{"plain": true}'


def load_tool(name: str):
    """Import an extension-less script from tools/ as a module."""
    loader = importlib.machinery.SourceFileLoader(f"tool_{name}", str(TOOLS / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_port(port: int, proc: subprocess.Popen | None = None, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc is not None and proc.poll() is not None:
            raise RuntimeError(f"process exited with {proc.returncode}")
        with socket.socket() as s:
            s.settimeout(0.2)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.05)
    raise RuntimeError(f"port {port} did not open")


class _Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        for i, event in enumerate(SSE_EVENTS):
            if i:
                time.sleep(PAUSE)
            self.server.send_times.append(time.monotonic())
            self.wfile.write(b"%x\r\n%s\r\n" % (len(event), event))
            self.wfile.flush()
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()

    def do_GET(self):
        if self.path == "/sse":
            self._sse()
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(PLAIN_BODY)))
            self.end_headers()
            self.wfile.write(PLAIN_BODY)

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self._sse()


@pytest.fixture
def sse_server():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.send_times = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="session")
def confdir(tmp_path_factory):
    return tmp_path_factory.mktemp("mitm-confdir")


class Proxy:
    def __init__(self, proc, port, flows, streams):
        self.proc, self.port, self.flows, self.streams = proc, port, flows, streams

    def stop(self):
        if self.proc.poll() is None:
            self.proc.send_signal(signal.SIGINT)
            self.proc.wait(timeout=20)


@pytest.fixture
def proxy(tmp_path, confdir):
    port = free_port()
    flows, streams = tmp_path / "flows.mitm", tmp_path / "streams"
    proc = subprocess.Popen(
        [str(MITMDUMP), "--listen-host", "127.0.0.1", "--listen-port", str(port),
         "--set", f"confdir={confdir}", "-w", str(flows),
         "-s", str(TOOLS / "tee_sse.py"), "--set", f"tee_dir={streams}"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    wait_for_port(port, proc)
    p = Proxy(proc, port, flows, streams)
    yield p
    p.stop()
