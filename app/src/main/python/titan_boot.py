"""Bootstrap full TITAN V62 engine inside Chaquopy APK — Android-safe."""
from __future__ import annotations

import os
import sys
import threading
import traceback
import types

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


def _load_engine_module():
    """Load titan_engine with Android storage lock patched out."""
    import importlib.util
    from pathlib import Path

    # Locate source next to this file
    here = Path(__file__).resolve().parent
    src_path = here / "titan_engine.py"
    if not src_path.exists():
        raise FileNotFoundError("titan_engine.py not found")

    text = src_path.read_text(encoding="utf-8", errors="replace")

    # Disable hard-fail when shared storage exists but is not writable
    text = text.replace(
        "if android_storage_present:\n        raise RuntimeError(",
        "if False and android_storage_present:\n        raise RuntimeError(",
        1,
    )
    # Prefer TITAN_HOME when set (APK boot always sets it)
    if "def _select_app_home()" in text and "TITAN_HOME" in text:
        inject = '''
def _select_app_home() -> Path:
    env_home = str(os.environ.get("TITAN_HOME") or os.environ.get("TITAN_APP_HOME") or "").strip()
    if env_home:
        try:
            kroot = Path(env_home)
            if kroot.name != TITAN_FOLDER_NAME:
                kroot = kroot / TITAN_FOLDER_NAME
            probe = kroot / ".titan_jjj_probe"
            kroot.mkdir(parents=True, exist_ok=True)
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return kroot
        except OSError:
            pass
'''
        # Only inject if original doesn't already prefer env first at top of function
        # Safer minimal patch already applied above with `if False and android_storage_present`

    spec = importlib.util.spec_from_loader("titan_engine", loader=None)
    mod = importlib.util.module_from_spec(spec)  # type: ignore
    sys.modules["titan_engine"] = mod
    exec(compile(text, str(src_path), "exec"), mod.__dict__)
    return mod


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
            _status["message"] = "loading full TITAN V62 (numpy/pandas)..."
            te = _load_engine_module()

            _status["phase"] = "serve"
            _status["message"] = "binding 0.0.0.0:8080 full dashboard"
            if hasattr(te, "run_titan"):
                te.run_titan(open_browser=False)
            elif hasattr(te, "app"):
                from waitress import serve
                serve(te.app, host="0.0.0.0", port=8080, threads=6, channel_timeout=120)
            else:
                raise RuntimeError("no run_titan in engine")
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
        return "error: " + str(s["error"])[:400]
    return f"{s.get('phase')}: {s.get('message')}"
