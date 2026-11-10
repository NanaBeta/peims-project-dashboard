"""Offline staging release tests — no cloud credentials or network calls."""
from __future__ import annotations

from pathlib import Path
import re

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.engine import make_url

from enterprise import staging_runtime as staging
from scripts.staging_smoke import check_origin


def _fixture_env():
    return {
        'PEIMS_DEPLOYMENT_ENV': 'staging',
        'PEIMS_RENDER_DATABASE_URL': 'postgresql://alice:safepassword@dpg-abc.internal:5432/peims',
        'PEIMS_OIDC_ISSUER': 'https://login.sso.test/tenant/',
        'PEIMS_OIDC_AUDIENCE': 'api://peims-stage',
        'PEIMS_OIDC_JWKS_URL': 'https://login.sso.test/tenant/keys',
        'PEIMS_CONSOLE_ORIGIN': 'https://peims-stage.onrender.com',
        'PEIMS_CONSOLE_AUTHORIZE_URL': 'https://login.sso.test/authorize',
        'PEIMS_CONSOLE_TOKEN_URL': 'https://login.sso.test/token',
        'PEIMS_CONSOLE_CLIENT_ID': 'peims-oidc-staging-app',
        'PEIMS_CONSOLE_CLIENT_SECRET': 'staging-test-not-a-real-secret',
        'PEIMS_CONSOLE_COOKIE_KEY': Fernet.generate_key().decode('ascii'),
    }


def test_render_connection_rewrites_scheme_and_requires_tls():
    url = staging.normalize_render_url('postgresql://user:p%40ss@db.internal:5432/pilot')
    parsed = make_url(url)
    assert parsed.drivername == 'postgresql+psycopg'
    assert parsed.password == 'p@ss'
    assert parsed.query['sslmode'] == 'require'
    assert 'p%40ss' in url


@pytest.mark.parametrize('bad', [
    '', 'sqlite:///tmp/db.sqlite', 'postgresql://user@db.internal/mydb',
    'postgresql://user:pass@db.internal/db?sslmode=disable',
    'postgresql://user:pass@db.internal/db?sslmode=verify-full',
    'postgresql://user:pass@db.internal/db?options=-c',
])
def test_bad_urls_fail_closed_without_leaking_value(bad):
    with pytest.raises(staging.StagingConfigurationError) as exc:
        staging.normalize_render_url(bad)
    assert bad not in str(exc.value) or not bad


def test_staging_configuration_installs_canonical_url():
    env = _fixture_env()
    url = staging.configure_staging(env)
    assert env['PEIMS_DATABASE_URL'] == url
    assert make_url(url).query['sslmode'] == 'require'


def test_no_production_or_unconfigured_oidc_environment():
    env = _fixture_env()
    env['PEIMS_DEPLOYMENT_ENV'] = 'production'
    with pytest.raises(staging.StagingConfigurationError, match='staging'):
        staging.configure_staging(env)
    env = _fixture_env()
    env['PEIMS_OIDC_ISSUER'] = 'http://bad.example.com'
    with pytest.raises(staging.StagingConfigurationError):
        staging.configure_staging(env)
    env = _fixture_env()
    env['PEIMS_CONSOLE_COOKIE_KEY'] = 'not-a-fernet-key'
    with pytest.raises(staging.StagingConfigurationError):
        staging.configure_staging(env)


def test_db_override_disallowed_and_migration_guard(monkeypatch):
    env = _fixture_env()
    env['PEIMS_DATABASE_URL'] = 'postgresql+psycopg://unwanted:pwd@elsewhere/db?sslmode=require'
    with pytest.raises(staging.StagingConfigurationError):
        staging.configure_staging(env)
    monkeypatch.setattr(staging, 'configure_staging', lambda: 'mock_database_url')
    with pytest.raises(SystemExit):
        staging.main(['migrate'])


def test_schema_verification_and_mismatch(monkeypatch):
    class MockConnection:
        def __init__(self, revision): self.revision = revision
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def execute(self, sql):
            assert 'alembic_version' in str(sql)
            revision = self.revision
            return type('Result', (), {'scalar_one': lambda s: revision})()
    class MockEngine:
        def __init__(self, revision): self.revision = revision; self.disposed=False
        def connect(self): return MockConnection(self.revision)
        def dispose(self): self.disposed=True
    engine = MockEngine(staging.EXPECTED_REVISION)
    monkeypatch.setattr(staging, 'create_engine', lambda *a, **kw: engine)
    staging.check_schema('redacted')
    assert engine.disposed
    engine = MockEngine('0004_work_management')
    with pytest.raises(staging.StagingConfigurationError, match='migration revision'):
        staging.check_schema('redacted')
    assert engine.disposed


def test_blueprint_is_off_by_default_and_database_external_access_denied():
    yaml = pytest.importorskip('yaml')
    root = Path(__file__).resolve().parents[1]
    blueprint = yaml.safe_load((root / 'render.yaml').read_text())
    web = blueprint['services'][0]
    database = blueprint['databases'][0]
    assert web['autoDeployTrigger'] == 'off'
    assert web['healthCheckPath'] == '/readyz'
    assert web['startCommand'] == 'python -m enterprise.staging_runtime serve'
    assert database['ipAllowList'] == []
    assert database['region'] == web['region']
    assert web['envVars'][1]['fromDatabase']['name'] == database['name']
    confidential = {'PEIMS_CONSOLE_COOKIE_KEY','PEIMS_CONSOLE_CLIENT_SECRET'}
    assert all(next(x for x in web['envVars'] if x['key']==k)['sync'] is False for k in confidential)


@pytest.mark.parametrize('origin', ['http://staging.test','https://user:pass@host.test','https://host.test/console/','https://host.test/?q=1'])
def test_smoke_check_refuses_non_origin_inputs(origin):
    with pytest.raises(ValueError):
        check_origin(origin)


def test_smoke_check_accepts_https_origin():
    assert check_origin('https://stage.peims.test/') == 'https://stage.peims.test'
