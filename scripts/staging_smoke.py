"""Unauthenticated external health checks; no customer data or test credentials.

Run only after the staging service is deployed and the database migrated.
"""
from __future__ import annotations

import argparse
from urllib.parse import urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check_origin(origin: str) -> str:
    parts = urlsplit(origin)
    if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
            or parts.path not in ("", "/") or parts.query or parts.fragment):
        raise ValueError("Provide only the HTTPS origin of the staging service")
    return origin.rstrip("/")


def run_smoke(origin: str) -> dict[str, int]:
    origin = check_origin(origin)
    opener = build_opener(NoRedirect())
    paths = {
        "/healthz": 200,
        "/readyz": 200,
        "/console/": 200,
        "/console/api/session": 401,
        "/v1/projects": 401,
    }
    results = {}
    for path, expected in paths.items():
        request = Request(origin + path, headers={"Accept": "application/json"})
        try:
            with opener.open(request, timeout=8) as response:
                code = response.status
                response.read(4096)
        except HTTPError as exc:
            code = exc.code
        except (URLError, TimeoutError) as exc:
            raise RuntimeError(f"Cannot reach staging path {path}") from None
        results[path] = code
        if code != expected:
            raise RuntimeError(f"Staging smoke check failed at {path}: expected {expected}, got {code}")
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify anonymous PEIMS staging API boundaries")
    parser.add_argument("--origin", required=True, help="HTTPS origin of your deployed staging service")
    args = parser.parse_args(argv)
    results = run_smoke(args.origin)
    for path, status in results.items():
        print(f"{path} : {status} (expected)")
    print("Anonymous staging smoke checks passed. Multi-account acceptance is still required.")


if __name__ == "__main__":
    main()
