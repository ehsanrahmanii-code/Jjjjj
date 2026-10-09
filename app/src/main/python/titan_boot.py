"""Bootstrap full TITAN V62 inside Chaquopy — import works on device."""
from __future__ import annotations

import os
import sys
import threading
import traceback

_started = False
_lock = threading.Lock()
_status = {"ok": False, "message": "idle", "error": None, "phase": "idle"}


def status() -> dict:
    return dict(_status)


def _prepare_android_home() -> str:
    files = None
    try:
        from com.chaquo.python import Python  # type: ignore
        ctx = Python.getInstance().getPlatform().getApplication()
        files = str(ctx.getFilesDir().getAbsolutePath())
    except Exception:
        files = os.path.join(os.path.expanduser("~"), ".titan_files")

    home = None
    for cand in ("/storage/emulated/0/JJJ", "/sdcard/JJJ", "/storage/self/primary/JJJ"):
        try:
            os.makedirs(cand, exist_ok=True)
            probe = os.path.join(cand, ".titan_probe")
            with open(probe, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(probe)
            home = cand
            break
        except Exception:
            continue
    if home is None:
        home = os.path.join(files, "JJJ")
        for sub in ("", "secrets", "data", "cache", "memory"):
            os.makedirs(os.path.join(home, sub) if sub else home, exist_ok=True)

    os.environ["TITAN_HOME"] = home
    os.environ["TITAN_APP_HOME"] = home
    os.environ["HOME"] = home
    os.environ["TITAN_OPEN_BROWSER"] = "0"
    os.environ["TITAN_HOST"] = "0.0.0.0"
    os.environ["TITAN_PORT"] = "8080"
    os.environ["TITAN_PORT_DEFAULT"] = "8080"
    sys.dont_write_bytecode = True
    return home


def _import_engine():
    """Import titan_engine the Chaquopy way; hide unwritable shared storage so APP_HOME falls back to TITAN_HOME."""
    import pathlib

    hide = {
        "/storage/emulated/0",
        "/sdcard",
        "/storage/self/primary",
    }
    real_exists = pathlib.Path.exists
    real_is_dir = pathlib.Path.is_dir

    def _exists(self):
        s = str(self).rstrip("/")
        if s in hide:
            return False
        return real_exists(self)

    def _is_dir(self):
        s = str(self).rstrip("/")
        if s in hide:
            return False
        return real_is_dir(self)

    pathlib.Path.exists = _exists  # type: ignore
    pathlib.Path.is_dir = _is_dir  # type: ignore
    try:
        import titan_engine as te
        return te
    finally:
        pathlib.Path.exists = real_exists  # type: ignore
        pathlib.Path.is_dir = real_is_dir  # type: ignore


def start_server() -> str:
    global _started
    with _lock:
        if _started:
            return str(_status.get("phase") or "already")
        _started = True
        _status.update({"ok": False, "message": "starting", "error": None, "phase": "boot"})

    def _run():
        try:
            _status["phase"] = "home"
            home = _prepare_android_home()
            _status["message"] = f"home:{home}"

            _status["phase"] = "import"
            _status["message"] = "import titan_engine (numpy/pandas)…"
            te = _import_engine()

            _status["phase"] = "serve"
            _status["message"] = "dashboard on 0.0.0.0:8080"
            if hasattr(te, "run_titan"):
                te.run_titan(open_browser=False)
            elif hasattr(te, "app"):
                try:
                    from waitress import serve
                    serve(te.app, host="0.0.0.0", port=8080, threads=6, channel_timeout=120)
                except Exception:
                    te.app.run(host="0.0.0.0", port=8080, threaded=True, use_reloader=False)
            else:
                raise RuntimeError("titan_engine has no run_titan/app")
            _status["ok"] = True
            _status["phase"] = "stopped"
        except Exception as exc:
            _status["ok"] = False
            _status["error"] = f"{exc}\n{traceback.format_exc()}"
            _status["message"] = "error"
            _status["phase"] = "error"

    threading.Thread(target=_run, name="titan-full", daemon=True).start()
    return "booting-full-v62"


def get_status_text() -> str:
    s = status()
    if s.get("error"):
        return "error: " + str(s["error"])[:500]
    return f"{s.get('phase')}: {s.get('message')}"
