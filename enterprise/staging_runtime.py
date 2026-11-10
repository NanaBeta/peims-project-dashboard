"""Fail-closed Render staging entrypoint for PEIMS enterprise (not public Streamlit).

This module does not provision resources or apply migrations on startup.
`migrate --acknowledge-staging-backup` is an explicit operator-only command.
"""
from __future__ import annotations

import argparse
import os
import re
from urllib.parse import urlsplit

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

EXPECTED_REVISION = "0005_console_sessions"
REQUIRED_OIDC = (
    "PEIMS_OIDC_ISSUER", "PEIMS_OIDC_AUDIENCE", "PEIMS_OIDC_JWKS_URL",
    "PEIMS_CONSOLE_ORIGIN", "PEIMS_CONSOLE_AUTHORIZE_URL",
    "PEIMS_CONSOLE_TOKEN_URL", "PEIMS_CONSOLE_CLIENT_ID",
    "PEIMS_CONSOLE_CLIENT_SECRET", "PEIMS_CONSOLE_COOKIE_KEY",
)
REQUIRED_HTTPS = (
    "PEIMS_OIDC_ISSUER", "PEIMS_OIDC_JWKS_URL", "PEIMS_CONSOLE_ORIGIN",
    "PEIMS_CONSOLE_AUTHORIZE_URL", "PEIMS_CONSOLE_TOKEN_URL",
)


class StagingConfigurationError(RuntimeError):
    """A generic non-secret-bearing staging configuration failure."""


def normalize_render_url(raw: str) -> str:
    """Convert Render's internal PostgreSQL URL to PEIMS psycopg + forced TLS.

    Render's internal Postgres endpoint supports sslmode=require, but cannot
    verify-full against its self-signed internal TLS certificate. Do not copy
    this exception into a different database provider's deployment.
    """
    if not raw:
        raise StagingConfigurationError("Render PostgreSQL connection is not configured")
    try:
        source = make_url(raw)
    except Exception as exc:
        raise StagingConfigurationError("Invalid Render PostgreSQL URL") from None
    if source.drivername not in {"postgresql", "postgres", "postgresql+psycopg"}:
        raise StagingConfigurationError("Expected a PostgreSQL URL from Render")
    if not source.host or not source.username or not source.password or not source.database:
        raise StagingConfigurationError("Incomplete Render PostgreSQL connection")
    if source.query and set(source.query) - {"sslmode"}:
        raise StagingConfigurationError("Unexpected PostgreSQL URL parameters")
    if source.query.get("sslmode", "require") != "require":
        raise StagingConfigurationError("Insecure PostgreSQL TLS mode")
    return source.set(drivername="postgresql+psycopg", query={"sslmode": "require"}).render_as_string(hide_password=False)


def _valid_https(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        return (parsed.scheme == "https" and bool(parsed.hostname)
                and not parsed.username and not parsed.password and not parsed.fragment)
    except ValueError:
        return False


def configure_staging(env=None) -> str:
    """Validate configured staging values and install the normalized DSN in env.

    Exposes no environment values or database password in validation errors.
    """
    env = env if env is not None else os.environ
    if env.get("PEIMS_DEPLOYMENT_ENV") != "staging":
        raise StagingConfigurationError("This entrypoint is restricted to staging")
    if env.get("PEIMS_DATABASE_URL"):
        raise StagingConfigurationError("Use Render's managed connection binding only")
    db_url = normalize_render_url(env.get("PEIMS_RENDER_DATABASE_URL", ""))
    for name in REQUIRED_OIDC:
        value = env.get(name, "").strip()
        if not value or "example" in value.casefold() or "replace" in value.casefold():
            raise StagingConfigurationError("Missing or placeholder staging identity configuration")
        if name in REQUIRED_HTTPS and not _valid_https(value):
            raise StagingConfigurationError("Invalid HTTPS identity provider configuration")
    parsed_origin = urlsplit(env["PEIMS_CONSOLE_ORIGIN"])
    if parsed_origin.path not in ("", "/") or parsed_origin.query or parsed_origin.port == 80:
        raise StagingConfigurationError("Console origin must be an HTTPS origin without a path")
    if len(env["PEIMS_CONSOLE_CLIENT_SECRET"]) < 16:
        raise StagingConfigurationError("Console client secret is too short")
    try:
        from cryptography.fernet import Fernet
        Fernet(env["PEIMS_CONSOLE_COOKIE_KEY"].encode("ascii"))
    except Exception:
        raise StagingConfigurationError("Console cookie encryption key is invalid") from None
    env["PEIMS_DATABASE_URL"] = db_url
    return db_url


def check_schema(db_url: str) -> None:
    """Require the reviewed Alembic revision, without running schema changes."""
    engine = create_engine(db_url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        if version != EXPECTED_REVISION:
            raise StagingConfigurationError("Staging schema is not at the expected migration revision")
    except StagingConfigurationError:
        raise
    except Exception:
        raise StagingConfigurationError("Staging database is unavailable or not migrated") from None
    finally:
        engine.dispose()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="PEIMS enterprise Render staging operations")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="Validate secrets and migration revision")
    commands.add_parser("serve", help="Start the HTTPS-ingress-backed API after checks")
    m = commands.add_parser("migrate", help="Apply staged migrations explicitly")
    m.add_argument("--acknowledge-staging-backup", action="store_true")
    args = parser.parse_args(argv)
    db_url = configure_staging()
    if args.command == "migrate":
        if not args.acknowledge_staging_backup:
            parser.error("Staging schema migration requires acknowledged backup and approval")
        from alembic import command
        from alembic.config import Config
        command.upgrade(Config("alembic.ini"), "head")
        check_schema(db_url)
        print("Staging migration revision verified.")
        return 0
    check_schema(db_url)
    if args.command == "serve":
        import uvicorn
        port = int(os.getenv("PORT", "10000"))
        if not 1 <= port <= 65535:
            raise StagingConfigurationError("Invalid service port")
        uvicorn.run("enterprise.main:app", host="0.0.0.0", port=port, proxy_headers=False, workers=1)
        return 0
    print("Staging settings and migration revision verified.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StagingConfigurationError as exc:
        # Exception messages are designed to contain no URL, token, or password.
        raise SystemExit(f"Staging startup blocked: {exc}") from None
