import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# Credit to the D2 team for reading settings from the environment and a .env file, which is how their d2-team/backend/config.py works.
# This is a much smaller version that doesn't need pydantic-settings.
def load_env_file(path):
    """Copy KEY=value lines from a .env file into the environment.
    Real environment variables win, so a deployment can override the file."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def setting(name, default=""):
    return os.environ.get(name) or default


load_env_file(ROOT / ".env")
