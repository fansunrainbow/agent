from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Stage 9 API and built frontend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--allow-remote", action="store_true",
        help="Explicitly acknowledge that this demo API has no user authentication before binding a non-loopback host.",
    )
    args = parser.parse_args()
    if args.host not in LOOPBACK_HOSTS and not args.allow_remote:
        raise SystemExit(
            "Refusing non-loopback bind without --allow-remote: the competition demo API has no user authentication."
        )
    import uvicorn
    uvicorn.run("webapp.api:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
