"""Run the local DecisionForge web UI (offline demo mode).

    python scripts/web_demo.py            # serves on http://127.0.0.1:8000
    python scripts/web_demo.py --port 9000

Uses DemoModelProvider + an offline mock search provider + local SQLite. No
Anthropic, no network calls, no credentials. Open the printed URL in a browser.

Equivalent: `uvicorn --factory app.web.bootstrap:create_demo_app --reload`
"""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args(argv)

    try:
        import uvicorn
    except ModuleNotFoundError:
        print("uvicorn is not installed. Run: pip install -e \".[web]\"")
        return 2

    print(f"DecisionForge web UI (offline demo) -> http://{args.host}:{args.port}")
    uvicorn.run(
        "app.web.bootstrap:create_demo_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
