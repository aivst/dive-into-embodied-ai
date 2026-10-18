"""Launch the viewer, including the uv Python dylib path needed on macOS."""
from pathlib import Path
import os
import sys
import sysconfig

root = Path(__file__).resolve().parent
python = root / ".venv" / "bin" / "python"
if Path(sys.prefix) != root / ".venv":
    os.execv(str(python), [str(python), str(root / "launch.py"), *sys.argv[1:]])
if sys.platform == "darwin":
    libdir = sysconfig.get_config_var("LIBDIR")
    old = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "/usr/local/lib:/usr/lib")
    if libdir:
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = f"{libdir}:{old}"
    executable = root / ".venv" / "bin" / "mjpython"
else:
    executable = python
os.execv(str(executable), [str(executable), str(root / "run_sim.py"), *sys.argv[1:]])
