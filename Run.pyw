import os, sys, runpy
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

target = 'app.py' if _deps_ok() else 'installer.py'
runpy.run_path(str(_dir / target), run_name='__main__')
