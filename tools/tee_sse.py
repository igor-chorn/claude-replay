"""mitmproxy addon: stream text/event-stream responses through and tee the raw bytes.

Usage: mitmdump -w flows.mitm -s tools/tee_sse.py --set tee_dir=<dir>

Per SSE response, named after the id of its flow in the -w dump:
  <tee_dir>/<flow.id>.sse           body bytes exactly as forwarded to the client
  <tee_dir>/<flow.id>.chunks.jsonl  one "start" record, one "chunk" record per
                                    chunk (t_ns, offset, len), one "end" record

The bytes are the HTTP message body as mitmproxy hands it over: transfer
framing (chunked, h2 frames) is removed, content-encoding is not.
"""

import hashlib
import json
import logging
import time
from pathlib import Path

from mitmproxy import ctx, http


class _Tee:
    def __init__(self, flow: http.HTTPFlow, directory: Path):
        self.offset = 0
        self.sha256 = hashlib.sha256()
        self.closed = False
        self.body = open(directory / f"{flow.id}.sse", "wb")
        self.sidecar = open(directory / f"{flow.id}.chunks.jsonl", "w")
        self._record(
            {
                "event": "start",
                "flow_id": flow.id,
                "t_ns": time.monotonic_ns(),
                "wall_time": time.time(),
                "status": flow.response.status_code,
                "content_type": flow.response.headers.get("content-type", ""),
                "content_encoding": flow.response.headers.get("content-encoding", ""),
            }
        )

    def _record(self, obj: dict) -> None:
        self.sidecar.write(json.dumps(obj) + "\n")
        self.sidecar.flush()

    def __call__(self, data: bytes) -> bytes:
        if not data:
            self.close("eof")
            return data
        if self.closed:
            return data
        self.body.write(data)
        self.body.flush()
        self.sha256.update(data)
        self._record(
            {
                "event": "chunk",
                "t_ns": time.monotonic_ns(),
                "offset": self.offset,
                "len": len(data),
            }
        )
        self.offset += len(data)
        return data

    def close(self, reason: str) -> None:
        if self.closed:
            return
        self.closed = True
        self.body.close()
        self._record(
            {
                "event": "end",
                "reason": reason,
                "t_ns": time.monotonic_ns(),
                "total": self.offset,
                "sha256": self.sha256.hexdigest(),
            }
        )
        self.sidecar.close()


class TeeSSE:
    def __init__(self):
        self.tees: dict[str, _Tee] = {}

    def load(self, loader):
        loader.add_option(
            name="tee_dir",
            typespec=str,
            default="",
            help="Directory for teed SSE response bodies (required).",
        )

    def running(self):
        if not ctx.options.tee_dir:
            logging.error("tee_sse: --set tee_dir=<dir> is required, shutting down")
            ctx.master.shutdown()
            return
        Path(ctx.options.tee_dir).mkdir(parents=True, exist_ok=True)

    def responseheaders(self, flow: http.HTTPFlow):
        content_type = flow.response.headers.get("content-type", "")
        if content_type.split(";")[0].strip().lower() != "text/event-stream":
            return
        tee = _Tee(flow, Path(ctx.options.tee_dir))
        self.tees[flow.id] = tee
        flow.response.stream = tee

    # The stream callable is not invoked at all for a body-less response, and
    # not with b"" when the connection breaks, so close from the flow hooks too.
    def response(self, flow: http.HTTPFlow):
        tee = self.tees.pop(flow.id, None)
        if tee:
            tee.close("eof")

    def error(self, flow: http.HTTPFlow):
        tee = self.tees.pop(flow.id, None)
        if tee:
            tee.close("error")

    def done(self):
        for tee in self.tees.values():
            tee.close("shutdown")
        self.tees.clear()


addons = [TeeSSE()]
