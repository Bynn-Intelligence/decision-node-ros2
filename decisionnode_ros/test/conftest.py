"""A mock of the DecisionNode API for the tests: never the real API."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

ANSWER = {
    "model": "decisionnode-flash-0.9.0-rc1",
    "answers": {
        "person": {"type": "truth", "truth": 0.91},
        "hazard": {"type": "choice", "choice": "smoke", "confidence": 0.8, "probabilities": {"none": 0.1, "smoke": 0.9}},
        "crowd": {"type": "number", "number": 3, "expected": 3.2, "confidence": 0.6, "probabilities": {"3": 0.6, "4": 0.4}},
        "door": {"type": "box", "x1": 10, "y1": 20, "x2": 110, "y2": 220, "present": 0.95, "confidence": 0.7,
                 "image": "camera", "width": 640, "height": 480},
    },
    "usage": {"input_tokens": 120, "output_tokens": 0, "cost": {"usd": 0.00012, "model_usd": 0.00012, "boosters_usd": 0.0, "free_tier": False}},
}


class MockApi:
    def __init__(self):
        self.requests = []
        self.status = 200
        self.body = ANSWER
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.url = "http://127.0.0.1:%d" % self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def _handler(self):
        api = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length)
                api.requests.append({"path": self.path, "headers": dict(self.headers), "body": json.loads(body or b"null")})
                data = json.dumps(api.body).encode()
                self.send_response(api.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("x-request-id", "req_mock_0001")
                self.send_header("x-decisionnode-latency-ms", "42")
                self.end_headers()
                self.wfile.write(data)

        return Handler

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def api():
    mock = MockApi()
    yield mock
    mock.close()
