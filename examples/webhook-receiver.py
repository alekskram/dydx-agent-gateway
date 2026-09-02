"""Webhook receiver example: stdlib-only HTTP server that accepts alerts
from the gateway's alerts.py and prints/stores them.

Run:            python examples/webhook-receiver.py [port]
Gateway side:   DYDX_WEBHOOKS="http://127.0.0.1:8911/hook" python alerts.py
"""
import datetime
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/hook":
            self.send_response(404)
            self.end_headers()
            return
        n = int(self.headers.get("Content-Length", 0))
        event = json.loads(self.rfile.read(n) or b"{}")
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] ⚠️ {event.get('kind')} {event.get('subject')}: "
              f"{json.dumps(event.get('payload', {}), ensure_ascii=False)[:200]}",
              flush=True)
        self.send_response(200)
        self.end_headers()

    def log_message(self, *a):  # keep the console quiet
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8911
    print(f"webhook receiver on :{port}/hook — waiting for gateway alerts…")
    HTTPServer(("127.0.0.1", port), H).serve_forever()
