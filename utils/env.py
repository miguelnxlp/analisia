import os
from pathlib import Path


def load_env(dotenv_path: Path | None = None) -> None:
    """
    Load environment variables from a .env file.
    Uses python-dotenv if available; otherwise a simple parser.
    Does not override existing environment variables.
    """
    path = dotenv_path or Path.cwd() / ".env"
    if not path.exists():
        return

    # Try python-dotenv if installed
    try:
        from dotenv import load_dotenv as _load

        _load(dotenv_path=str(path), override=False)
        return
    except Exception:
        pass

    # Fallback: minimal parser KEY=VALUE with quotes support
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception:
        # Silently ignore malformed .env
        return


