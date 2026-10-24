"""Stdlib-only liveness/readiness smoke test for the local Compose backend."""

import argparse
import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--wait-seconds", type=float, default=60)
    args = parser.parse_args()
    expected = {
        "/health": {"status": "ok"},
        "/ready": {
            "status": "ready",
            "checks": {"database": "ok", "redis": "ok", "storage": "ok"},
        },
    }
    deadline = time.monotonic() + max(0, args.wait_seconds)
    while True:
        try:
            for path, body in expected.items():
                with urlopen(args.base_url.rstrip("/") + path, timeout=10) as response:
                    if response.status != 200 or json.load(response) != body:
                        raise ValueError("Unexpected health response")
            print("PASS: /health and /ready returned the expected HTTP 200 bodies")
            return 0
        except (HTTPError, URLError, OSError, ValueError):
            if time.monotonic() >= deadline:
                print(
                    "FAIL: health/readiness did not become available", file=sys.stderr
                )
                return 1
            time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())
