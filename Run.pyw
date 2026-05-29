import os, sys, runpy, platform
from pathlib import Path

_dir = Path(__file__).parent
os.chdir(_dir)
sys.path.insert(0, str(_dir))


def _deps_ok():
    for pkg in ("fitz", "flask", "deep_translator", "webview"):
        try:
            __import__(pkg)
        except ImportError:
            return False
    return True


def _linux_backend_ok() -> bool:
    try:
        import gi
        try:
            gi.require_version('WebKit2', '4.0')
        except ValueError:
            gi.require_version('WebKit2', '4.1')
        from gi.repository import WebKit2
        return True
    except Exception:
        pass
    for qt in ('PyQt5.QtWebEngineWidgets', 'PyQt6.QtWebEngineWidgets'):
        try:
            __import__(qt)
            return True
        except ImportError:
            pass
    return False


def _show_error(title, msg):
    try:
        import tkinter as tk
        from tkinter import messagebox
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror(title, msg)
        r.destroy()
    except Exception:
        print(f"\n[ERROR] {msg}\n")


if platform.system() == 'Linux' and _deps_ok() and not _linux_backend_ok():
    _show_error(
        "PDF Translator — Missing dependency",
        "A web engine is required to display the interface.\n\n"
        "Install with:\n"
        "  sudo apt install python3-gi gir1.2-webkit2-4.1\n"
        "  (older systems: gir1.2-webkit2-4.0)\n\n"
        "Or with Qt:\n"
        "  pip install PyQt5 PyQtWebEngine"
    )
    sys.exit(1)

target = 'app.py' if _deps_ok() else 'installer.py'
runpy.run_path(str(_dir / target), run_name='__main__')
