"""Loopback video preview with range support, scoped to explicitly registered files."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import mimetypes
from pathlib import Path
import re
import secrets
import threading


class MediaPreview:
    def __init__(self):
        self.files = {}
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_HEAD(self):
                self.send_media(False)

            def do_GET(self):
                self.send_media(True)

            def send_media(self, body):
                path = owner.files.get(self.path.split("?", 1)[0])
                if path is None or not path.is_file():
                    self.send_error(404)
                    return
                size = path.stat().st_size
                start, end = 0, size - 1
                partial = False
                requested = self.headers.get("Range")
                if requested:
                    match = re.fullmatch(r"bytes=(\d*)-(\d*)", requested)
                    if not match or not any(match.groups()):
                        self.send_error(416)
                        return
                    left, right = match.groups()
                    if left:
                        start = int(left)
                        end = min(int(right), size - 1) if right else size - 1
                    else:
                        start = max(0, size - int(right))
                    if start > end or start >= size:
                        self.send_response(416)
                        self.send_header("Content-Range", f"bytes */{size}")
                        self.end_headers()
                        return
                    partial = True
                self.send_response(206 if partial else 200)
                self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(max(0, end - start + 1)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Access-Control-Allow-Origin", "*")
                if partial:
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.end_headers()
                if body:
                    try:
                        with path.open("rb") as stream:
                            stream.seek(start)
                            remaining = end - start + 1
                            while remaining > 0:
                                chunk = stream.read(min(remaining, 65536))
                                if not chunk:
                                    break
                                self.wfile.write(chunk)
                                remaining -= len(chunk)
                    except (ConnectionError, OSError):
                        pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def register(self, path):
        path = Path(path).resolve(strict=True)
        key = "/" + secrets.token_urlsafe(24) + "/" + path.name
        # ASCII token only; filename is not used in lookup or routing.
        key = key.rsplit("/", 1)[0] + "/media"
        self.files[key] = path
        return f"http://127.0.0.1:{self.server.server_port}{key}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()
