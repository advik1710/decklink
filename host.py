#!/usr/bin/env python3
"""DeckLink: tiny local PC dashboard host (Python standard library only)."""
import argparse
import json
import os
import platform
import secrets
import shutil
import socket
import subprocess
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
WEB_ROOT = ROOT / "web"
LOCK = threading.Lock()
PREV_IDLE = PREV_TOTAL = None
NET_PREV = None
STARTED = time.time()


def load_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def local_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def cpu_percent():
    global PREV_IDLE, PREV_TOTAL
    # Windows provides a useful load estimate with GetSystemTimes; Linux exposes /proc/stat.
    try:
        if os.name == "nt":
            import ctypes
            class FILETIME(ctypes.Structure):
                _fields_ = [("low", ctypes.c_ulong), ("high", ctypes.c_ulong)]
            idle, kernel, user = FILETIME(), FILETIME(), FILETIME()
            if ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
                val = lambda ft: (ft.high << 32) | ft.low
                i, total = val(idle), val(kernel) + val(user)
            else:
                return None
        else:
            with open("/proc/stat", "r", encoding="ascii") as f:
                fields = list(map(int, f.readline().split()[1:]))
            i, total = fields[3] + (fields[4] if len(fields) > 4 else 0), sum(fields)
        with LOCK:
            old_i, old_t = PREV_IDLE, PREV_TOTAL
            PREV_IDLE, PREV_TOTAL = i, total
        if old_i is None or total == old_t:
            time.sleep(0.12)
            return cpu_percent()
        return round(100 * (1 - (i - old_i) / (total - old_t)))
    except Exception:
        return None


def memory_stats():
    if os.name == "nt":
        try:
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            state = MEMORYSTATUSEX(); state.dwLength = ctypes.sizeof(state)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
                return {"total": state.ullTotalPhys, "used": state.ullTotalPhys-state.ullAvailPhys,
                        "percent": state.dwMemoryLoad}
        except Exception:
            pass
    try:
        with open("/proc/meminfo", "r", encoding="ascii") as f:
            vals = {line.split(":")[0]: int(line.split()[1]) * 1024 for line in f if ":" in line}
        total, avail = vals["MemTotal"], vals.get("MemAvailable", vals.get("MemFree", 0))
        return {"total": total, "used": total-avail, "percent": round(100*(total-avail)/total)}
    except Exception:
        return {"total": 0, "used": 0, "percent": None}


def network_stats():
    global NET_PREV
    rx = tx = 0
    try:
        if os.name == "nt":
            raw = subprocess.check_output(["netstat", "-e"], text=True, timeout=2)
            for line in raw.splitlines():
                parts = line.split()
                if parts and parts[0].lower() == "bytes":
                    rx, tx = int(parts[1]), int(parts[2]); break
        else:
            with open("/proc/net/dev", "r", encoding="ascii") as f:
                for line in f.readlines()[2:]:
                    fields = line.replace(":", " ").split()
                    if len(fields) >= 10 and fields[0] != "lo":
                        rx += int(fields[1]); tx += int(fields[9])
        now = time.time(); old = NET_PREV; NET_PREV = (rx, tx, now)
        if old:
            elapsed = max(now-old[2], .1)
            return {"down": max(0, round((rx-old[0])/elapsed)), "up": max(0, round((tx-old[1])/elapsed))}
    except Exception:
        pass
    return {"down": 0, "up": 0}


def stats():
    usage = shutil.disk_usage(ROOT.anchor)
    return {"cpu": cpu_percent(), "memory": memory_stats(),
            "disk": {"total": usage.total, "used": usage.used, "percent": round(100*usage.used/usage.total)},
            "network": network_stats(), "hostname": socket.gethostname(),
            "platform": platform.system(), "uptime": int(time.time()-STARTED)}


def launch(action):
    """Execute only configured action types. No client-supplied command is accepted."""
    kind = action.get("type")
    if kind == "url":
        url = action.get("url", "")
        if not url.startswith(("https://", "http://")):
            raise ValueError("URL must use HTTP or HTTPS")
        if os.name == "nt":
            os.startfile(url)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", url], close_fds=True)
        else:
            subprocess.Popen(["xdg-open", url], close_fds=True)
    elif kind == "app":
        executable = action.get("executable", "")
        args = action.get("args", [])
        if not executable or not isinstance(args, list) or not all(isinstance(x, str) for x in args):
            raise ValueError("Invalid app configuration")
        subprocess.Popen([executable] + args, close_fds=True)
    else:
        raise ValueError("Unsupported action type")


class Handler(BaseHTTPRequestHandler):
    server_version = "DeckLink/0.1"

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def send_json(self, code, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "null"); self.end_headers(); self.wfile.write(body)

    def authorized(self):
        token = self.headers.get("X-DeckLink-Token", "")
        return secrets.compare_digest(token, self.server.token)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/ping":
            return self.send_json(200, {"ok": True})
        if path.startswith("/api/") and not self.authorized():
            return self.send_json(401, {"error": "Pair with your host token"})
        if path == "/api/info":
            actions = [{"id": x["id"], "label": x["label"], "icon": x.get("icon", "⚡")} for x in self.server.config.get("actions", [])]
            return self.send_json(200, {"name": self.server.config.get("name", "DeckLink"), "actions": actions,
                "host": socket.gethostname(), "version": "0.1.0"})
        if path == "/api/stats":
            return self.send_json(200, stats())
        if path == "/":
            path = "/index.html"
        file_path = (WEB_ROOT / path.lstrip("/")).resolve()
        if not str(file_path).startswith(str(WEB_ROOT.resolve())) or not file_path.is_file():
            self.send_error(404); return
        data = file_path.read_bytes()
        ctype = "text/html; charset=utf-8" if file_path.suffix == ".html" else "text/" + ("css" if file_path.suffix == ".css" else "javascript") + "; charset=utf-8"
        self.send_response(200); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache"); self.end_headers(); self.wfile.write(data)

    def do_POST(self):
        path = urlparse(self.path).path
        if not self.authorized():
            return self.send_json(401, {"error": "Pair with your host token"})
        if path != "/api/action":
            return self.send_json(404, {"error": "Not found"})
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
            action_id = payload.get("id")
            action = next((a for a in self.server.config.get("actions", []) if a.get("id") == action_id), None)
            if action is None:
                return self.send_json(404, {"error": "Unknown button"})
            launch(action)
            return self.send_json(200, {"ok": True, "message": action["label"] + " started"})
        except Exception as err:
            return self.send_json(400, {"error": str(err)})


def main():
    parser = argparse.ArgumentParser(description="Run the DeckLink PC dashboard")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true", help="Do not open the dashboard on this PC")
    args = parser.parse_args()
    config = load_config()
    token = config.get("token", "").strip() or secrets.token_urlsafe(24)
    config["token"] = token
    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    server.token, server.config = token, config
    address = "http://%s:%d/?token=%s" % (local_ip(), args.port, token)
    print("DeckLink is ready: " + address)
    print("Open that address on your tablet while both devices are on the same Wi-Fi.")
    print("Keep this window open. Press Ctrl+C to stop.")
    if not args.no_open:
        webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping DeckLink...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
