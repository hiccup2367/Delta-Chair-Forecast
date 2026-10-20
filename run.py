"""Start Chair Forecast and open it in the default browser.

    python run.py              # picks a free port starting at 8765
    python run.py --no-browser
    python run.py --port 9000

The app only listens on 127.0.0.1, so it is reachable from this computer and
nowhere else.
"""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import webbrowser

from chairforecast.server import create_app


def free_port(start: int) -> int:
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise SystemExit("No free port found between %d and %d." % (start, start + 49))


def main() -> None:
    parser = argparse.ArgumentParser(description="Chair Forecast")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    port = free_port(args.port)
    url = f"http://127.0.0.1:{port}/"
    app = create_app(port)

    print("\nChair Forecast is running on this computer only.")
    print(f"Open {url} if your browser didn't open by itself.")
    print("Close this window to stop it.\n")
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    try:
        from waitress import serve
        serve(app, host="127.0.0.1", port=port, threads=6, max_request_body_size=800 * 1024 * 1024,
              channel_timeout=600, _quiet=True)
    except ImportError:
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    sys.exit(main())
