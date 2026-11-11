"""Guard the free Streamlit entrypoint from accidental enterprise provisioning.

These tests deliberately do not claim that session-only state is persisted.
"""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def test_free_app_has_no_enterprise_service_imports():
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    assert not any(name == "enterprise" or name.startswith("enterprise.") for name in imports)


def test_streamlit_install_does_not_include_enterprise_api_dependencies():
    lines = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    specs = [line.strip().lower() for line in lines
             if line.strip() and not line.lstrip().startswith("#")]
    blocked = ("-r requirements-api", "fastapi", "uvicorn", "sqlalchemy",
               "alembic", "psycopg", "asyncpg", "supabase")
    assert not any(spec.startswith(prefix) for spec in specs for prefix in blocked)


def test_paid_render_blueprint_not_automatically_in_streamlit_dependencies():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "render.yaml" not in app
    assert "render.yaml" not in req
