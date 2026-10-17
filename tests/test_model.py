import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from synthetic_human.model import ModelGateway


async def test_shared_model_contract_and_rejected_role(rig):
    requests = []
    response_role = ["office"]

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
            body = json.dumps(
                {
                    "message": {"content": json.dumps({"next_role": response_role[0], "reason": "test"})},
                    "prompt_eval_count": 30,
                    "eval_count": 8,
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        rig.settings.model_url = f"http://127.0.0.1:{server.server_port}"
        gateway = ModelGateway(rig.settings, rig.store)
        result = await gateway.decide("browser", {"count": 3}, ["office"], "office")
        assert result.next_role == "office"
        assert requests[0][0] == "/api/chat"
        assert requests[0][1]["format"]["properties"]["next_role"]
        response_role[0] = "arbitrary-code-executor"
        with pytest.raises(ValueError, match="outside"):
            await gateway.decide("browser", {"count": 3}, ["office"], "office")
        usage = [
            json.loads(r[0]) for r in rig.store.db.execute("SELECT body FROM events WHERE kind='model.call'")
        ]
        assert len(usage) == 2
        assert usage[0]["input_tokens"] == 30
        assert usage[1]["error"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
