"""
Live view of the HUD in a web browser, for dev without a screen on the Pi.

    python main.py --web      ->  open http://<pi-address>:8000 on your laptop

Serves the rendered frames as an MJPEG stream (an <img> that keeps updating).
"""

import io
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pygame

PAGE = b"""<!doctype html><title>BikeHUD</title>
<body style="margin:0;background:#000;display:grid;place-items:center;height:100vh">
<img src="/stream" style="max-width:100%;max-height:100%">"""

_frame = None                    # latest JPEG bytes
_cond = threading.Condition()
_last = 0.0


def publish(surface, fps=15):
    """Call after each render; encodes the screen to JPEG at most `fps` times a second."""
    global _frame, _last
    now = time.monotonic()
    if now - _last < 1 / fps:
        return
    _last = now
    buf = io.BytesIO()
    pygame.image.save(surface, buf, "frame.jpg")
    with _cond:
        _frame = buf.getvalue()
        _cond.notify_all()


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(PAGE)
            return
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()
        try:
            while True:
                with _cond:
                    _cond.wait(timeout=1)
                    frame = _frame
                if frame is None:
                    continue
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
        except (BrokenPipeError, ConnectionResetError):
            pass  # browser tab closed

    def log_message(self, *args):
        pass  # keep the HUD logs clean


def start(port=8000):
    server = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"[WEB] HUD live view at http://<pi-address>:{port}")
