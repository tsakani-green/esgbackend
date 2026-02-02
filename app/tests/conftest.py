import sys
import pathlib

# Ensure the esgbackend package root is importable so `import app` works
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
