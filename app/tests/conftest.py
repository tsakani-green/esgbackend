import sys
import pathlib

# Ensure the esgbackend package root is importable so `import app` works
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Prevent pydantic-settings from attempting to read any .env files during tests.
# Some developer machines have .env files with non-UTF8 contents which cause
# collection-time failures. Override the DotEnvSettingsSource to return nothing.
try:
    import pydantic_settings.sources as _psources
    _psources.DotEnvSettingsSource._read_env_files = lambda self, case_sensitive: {}
except Exception:
    # If pydantic-settings internals change, don't fail tests at import time.
    pass
