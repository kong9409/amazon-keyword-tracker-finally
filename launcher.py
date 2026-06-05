from __future__ import annotations

import socket
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
APP_PORT = 8766
APP_URL = f"http://127.0.0.1:{APP_PORT}"
PYTHONW = Path(r"C:\Users\EDY\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe")


def is_port_open(host: str = "127.0.0.1", port: int = APP_PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((host, port)) == 0


def main() -> int:
    if not PYTHONW.exists():
        print(f"Python runtime was not found: {PYTHONW}")
        return 1
    if not (APP_DIR / "app.py").exists():
        print("app.py was not found in this folder.")
        return 1

    if not is_port_open():
        subprocess.Popen(
            [str(PYTHONW), str(APP_DIR / "app.py")],
            cwd=str(APP_DIR),
            env={**os.environ, "KEYWORD_TRACKER_PORT": str(APP_PORT)},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )

    for _ in range(20):
        if is_port_open():
            webbrowser.open(APP_URL)
            print(f"Keyword Tracker opened: {APP_URL}")
            return 0
        time.sleep(0.25)

    print("Service did not start. Please run app.py manually to see the error.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
