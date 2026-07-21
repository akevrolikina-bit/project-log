"""Application entry point for the packaged desktop build.

This module is used both as the PyInstaller entry point and as a convenient
way to run the whole application (API + statically-built frontend) from a
single process. It:

1. picks a local port (preferring 8001, falling back to a free one),
2. opens the default web browser at the app URL once the server is ready,
3. starts the uvicorn server (blocking) so the process stays alive.
"""

from __future__ import annotations

import socket
import threading
import time
import webbrowser

import uvicorn

HOST = "127.0.0.1"
PREFERRED_PORT = 8001


def _pick_port(preferred: int) -> int:
    """Return the preferred port if free, otherwise an OS-assigned free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((HOST, preferred))
            return preferred
        except OSError:
            probe.bind((HOST, 0))
            return probe.getsockname()[1]


def _open_browser_when_ready(port: int) -> None:
    """Wait until the server accepts connections, then open the browser."""
    url = f"http://{HOST}:{port}/"
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((HOST, port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.2)
    webbrowser.open(url)


def main() -> None:
    port = _pick_port(PREFERRED_PORT)
    url = f"http://{HOST}:{port}/"

    print("=" * 60)
    print("  TimeAudit is starting...")
    print(f"  Open in your browser: {url}")
    print("  Keep this window open while you use the app.")
    print("  Close this window to stop TimeAudit.")
    print("=" * 60)

    threading.Thread(
        target=_open_browser_when_ready, args=(port,), daemon=True
    ).start()

    # Import the app here so that any startup cost happens after the banner is
    # shown. Passing the app object (not an import string) keeps it working
    # inside the PyInstaller bundle, where reload/subprocess import is unavailable.
    from app.main import app

    uvicorn.run(app, host=HOST, port=port, log_level="info")


if __name__ == "__main__":
    main()
