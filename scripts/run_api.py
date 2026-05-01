"""Cross-platform dev server launcher.

Usage:
    python scripts/run_api.py
    python scripts/run_api.py --port 9000 --no-reload
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Zecpath ATS API locally")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-reload", action="store_true", help="Disable auto-reload")
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args()

    # Make sure we run from project root regardless of CWD
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

    try:
        import uvicorn
    except ImportError:
        print("uvicorn not installed. Run: pip install -r requirements.txt", file=sys.stderr)
        return 1

    uvicorn.run(
        "api.main:app",
        host=args.host,
        port=args.port,
        reload=not args.no_reload,
        log_level=args.log_level,
        app_dir=str(project_root),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
