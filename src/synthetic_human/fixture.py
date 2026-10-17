from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PRODUCTS = [("Orion", 120, 24), ("Lyra", 95, 12), ("Vega", 145, 36)]


class Catalog:
    """Local, labelled demo website. Prices are fictional; source pages are browsed through the GUI."""

    def __init__(self, port=0, products=None):
        catalog_products = tuple(PRODUCTS if products is None else products)

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path in ("/", "/index.html"):
                    title = "Demo Product Catalog"
                    content = (
                        "<h1>Demo Product Catalog</h1><p>Fictional products, USD. Tax assumption: 8%.</p>"
                    )
                    for name, price, _ in catalog_products:
                        content += f'<section><h2>{name}</h2><p>Price: USD {price:.2f}</p><a href="/{name.lower()}">Details {name}</a></section>'
                else:
                    product = next((p for p in catalog_products if self.path == "/" + p[0].lower()), None)
                    if not product:
                        self.send_error(404)
                        return
                    name, price, warranty = product
                    title = f"Product details: {name}"
                    content = f'<h1>{title}</h1><p>Price: USD {price:.2f}</p><div style="height:110vh">Product information. Fictional evaluation data.</div><p>Warranty: {warranty} months</p><a href="/">Back to catalog</a>'
                body = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{title}</title><style>body{{font:20px system-ui;max-width:850px;margin:50px auto;color:#183247;background:#f6f8fc}}section{{min-height:40vh;padding:24px;border-bottom:1px solid #aac}}a{{color:#165abd}}h1{{font-size:32px}}</style></head><body>{content}<p>Source: local Synthetic Human Agent demo fixture.</p></body></html>""".encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
