"""
Local HTTP OAuth callback server.

Both AniList and MAL redirect back to http://localhost:6789/<service>?code=...
Run get_oauth_code() in a background thread (OAuthWorker in workers.py).
"""
import threading
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 6789

_SUCCESS_HTML = b"""
<html><head><style>body{font-family:sans-serif;background:#0f0f13;color:#e0e0e0;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}
h2{color:#c084fc;}</style></head>
<body><h2>&#10003; Authorised! You can close this tab.</h2></body></html>
"""
_ERROR_HTML = b"""
<html><head><style>body{font-family:sans-serif;background:#0f0f13;color:#e0e0e0;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}
h2{color:#f87171;}</style></head>
<body><h2>&#10007; Auth failed — no code received.</h2></body></html>
"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        if code:
            self.server._result = code
            self._respond(200, _SUCCESS_HTML)
        else:
            self._respond(400, _ERROR_HTML)
        self.server._done.set()

    def _respond(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


def get_oauth_code(path_prefix: str, timeout: int = 120) -> str | None:
    """
    Start a local server on PORT, wait for a GET /{path_prefix}?code=...
    Returns the code string or None on timeout.
    """
    server = HTTPServer(("127.0.0.1", PORT), _Handler)
    server._result = None
    server._done = threading.Event()

    # Only handle one request then stop
    def _serve():
        server.handle_request()

    t = threading.Thread(target=_serve, daemon=True)
    t.start()
    server._done.wait(timeout=timeout)
    return server._result


def redirect_uri(service: str) -> str:
    return f"http://localhost:{PORT}/{service}"
