"""
Tests for scripts/provision_client.py — Step 5.

All DB, subprocess (alembic), and Redis calls are mocked.
Tests verify:
  - Bad client_id format → EXIT_BAD_ARGS
  - Missing config file → EXIT_BAD_ARGS
  - Invalid config (validation error) → EXIT_BAD_ARGS
  - DB connection failure → EXIT_DB_FAILURE
  - Platform migration failure → EXIT_MIGRATION_FAILURE
  - Per-client migration failure → EXIT_MIGRATION_FAILURE
  - Missing table after migration → EXIT_DB_FAILURE
  - Happy path (all steps succeed) → EXIT_OK
  - Idempotency: tenant INSERT ON CONFLICT does not raise
  - Redis warning does not abort provisioning
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from iolabs_sdr.scripts.provision_client import (
    EXIT_BAD_ARGS,
    EXIT_DB_FAILURE,
    EXIT_MIGRATION_FAILURE,
    EXIT_OK,
    CLIENT_TABLES,
    provision_client,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_config(tmp_path):
    """A minimal fake config JSON and a corresponding ClientConfig mock."""
    config_file = tmp_path / "test_client.json"
    config_file.write_text('{"client_id": "test_client"}')

    fake_config = MagicMock()
    fake_config.client_id = "test_client"
    fake_config.sender_name = "Test Sender"
    return config_file, fake_config


@pytest.fixture
def mock_cursor():
    """A psycopg2 cursor mock that returns True for every table existence check."""
    cur = MagicMock()
    # fetchone()[0] = True → all tables exist
    cur.fetchone.return_value = (True,)
    return cur


@pytest.fixture
def mock_conn(mock_cursor):
    """A psycopg2 connection mock."""
    conn = MagicMock()
    conn.cursor.return_value = mock_cursor
    return conn


@pytest.fixture
def successful_alembic():
    """subprocess.CompletedProcess mock for a successful alembic run."""
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.returncode = 0
    proc.stderr = ""
    return proc


# ── Helper: patch everything for a full happy-path run ────────────────────────


def _run_happy_path(mock_config, mock_conn, successful_alembic, configs_dir):
    config_file, fake_config = mock_config
    with (
        patch(
            "iolabs_sdr.scripts.provision_client._CONFIGS_DIR", configs_dir
        ),
        patch(
            "iolabs_sdr.scripts.provision_client.load_client_config",
            return_value=fake_config,
        ),
        patch("psycopg2.connect", return_value=mock_conn),
        patch(
            "iolabs_sdr.scripts.provision_client._run_alembic",
            return_value=successful_alembic,
        ),
        patch(
            "iolabs_sdr.core.rate_limiter.RateLimiter.ping",
            return_value=True,
        ),
    ):
        return provision_client("test_client")


# ── Tests ──────────────────────────────────────────────────────────────────────


class TestInputValidation:
    def test_empty_client_id_returns_bad_args(self):
        assert provision_client("") == EXIT_BAD_ARGS

    def test_uppercase_client_id_returns_bad_args(self):
        assert provision_client("ACME") == EXIT_BAD_ARGS

    def test_hyphenated_client_id_returns_bad_args(self):
        assert provision_client("my-client") == EXIT_BAD_ARGS

    def test_valid_client_id_with_underscores_passes_validation(self, tmp_path, mock_conn, successful_alembic):
        # Create a config file so the check doesn't fail on missing file
        (tmp_path / "my_client.json").write_text("{}")
        fake_config = MagicMock()
        fake_config.client_id = "my_client"
        fake_config.sender_name = "Name"
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.fetchone.return_value = (True,)

        with (
            patch("iolabs_sdr.scripts.provision_client._CONFIGS_DIR", tmp_path),
            patch("iolabs_sdr.scripts.provision_client.load_client_config", return_value=fake_config),
            patch("psycopg2.connect", return_value=mock_conn),
            patch("iolabs_sdr.scripts.provision_client._run_alembic", return_value=successful_alembic),
            patch("iolabs_sdr.core.rate_limiter.RateLimiter.ping", return_value=True),
        ):
            assert provision_client("my_client") == EXIT_OK


class TestConfigChecks:
    def test_missing_config_file_returns_bad_args(self, tmp_path):
        with patch("iolabs_sdr.scripts.provision_client._CONFIGS_DIR", tmp_path):
            assert provision_client("no_such_client") == EXIT_BAD_ARGS

    def test_invalid_config_returns_bad_args(self, tmp_path):
        (tmp_path / "bad_client.json").write_text("{}")
        with (
            patch("iolabs_sdr.scripts.provision_client._CONFIGS_DIR", tmp_path),
            patch(
                "iolabs_sdr.scripts.provision_client.load_client_config",
                side_effect=Exception("validation error"),
            ),
        ):
            assert provision_client("bad_client") == EXIT_BAD_ARGS


class TestDatabaseConnectivity:
    def test_db_connection_failure_returns_db_failure(self, tmp_path):
        (tmp_path / "test_client.json").write_text("{}")
        fake_config = MagicMock()
        fake_config.sender_name = "X"

        with (
            patch("iolabs_sdr.scripts.provision_client._CONFIGS_DIR", tmp_path),
            patch("iolabs_sdr.scripts.provision_client.load_client_config", return_value=fake_config),
            patch("psycopg2.connect", side_effect=Exception("connection refused")),
        ):
            assert provision_client("test_client") == EXIT_DB_FAILURE


class TestMigrations:
    def test_platform_migration_failure_returns_migration_failure(self, tmp_path, mock_conn):
        (tmp_path / "test_client.json").write_text("{}")
        fake_config = MagicMock()
        fake_config.sender_name = "X"

        failed = MagicMock(spec=subprocess.CompletedProcess)
        failed.returncode = 1
        failed.stderr = "alembic error: could not connect"

        with (
            patch("iolabs_sdr.scripts.provision_client._CONFIGS_DIR", tmp_path),
            patch("iolabs_sdr.scripts.provision_client.load_client_config", return_value=fake_config),
            patch("psycopg2.connect", return_value=mock_conn),
            patch("iolabs_sdr.scripts.provision_client._run_alembic", return_value=failed),
        ):
            assert provision_client("test_client") == EXIT_MIGRATION_FAILURE

    def test_client_migration_failure_returns_migration_failure(self, tmp_path, mock_conn):
        (tmp_path / "test_client.json").write_text("{}")
        fake_config = MagicMock()
        fake_config.sender_name = "X"

        ok = MagicMock(spec=subprocess.CompletedProcess)
        ok.returncode = 0
        ok.stderr = ""
        fail = MagicMock(spec=subprocess.CompletedProcess)
        fail.returncode = 2
        fail.stderr = "table already exists"

        # First call (001) succeeds, second (002) fails
        with (
            patch("iolabs_sdr.scripts.provision_client._CONFIGS_DIR", tmp_path),
            patch("iolabs_sdr.scripts.provision_client.load_client_config", return_value=fake_config),
            patch("psycopg2.connect", return_value=mock_conn),
            patch(
                "iolabs_sdr.scripts.provision_client._run_alembic",
                side_effect=[ok, fail],
            ),
        ):
            assert provision_client("test_client") == EXIT_MIGRATION_FAILURE

    def test_alembic_called_with_correct_args(self, tmp_path, mock_conn, successful_alembic):
        (tmp_path / "test_client.json").write_text("{}")
        fake_config = MagicMock()
        fake_config.sender_name = "X"
        mock_conn.cursor.return_value.fetchone.return_value = (True,)

        with (
            patch("iolabs_sdr.scripts.provision_client._CONFIGS_DIR", tmp_path),
            patch("iolabs_sdr.scripts.provision_client.load_client_config", return_value=fake_config),
            patch("psycopg2.connect", return_value=mock_conn),
            patch(
                "iolabs_sdr.scripts.provision_client._run_alembic",
                return_value=successful_alembic,
            ) as mock_alembic,
            patch("iolabs_sdr.core.rate_limiter.RateLimiter.ping", return_value=True),
        ):
            provision_client("test_client")

        calls = mock_alembic.call_args_list
        assert calls[0] == call(["upgrade", "001"])
        assert calls[1] == call(["upgrade", "002", "-x", "client_schema=client_test_client"])


class TestTableVerification:
    def test_missing_table_returns_db_failure(self, tmp_path, mock_conn, successful_alembic):
        (tmp_path / "test_client.json").write_text("{}")
        fake_config = MagicMock()
        fake_config.sender_name = "X"

        # First call returns False (table missing), rest return True
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.fetchone.side_effect = [(False,)] + [(True,)] * (len(CLIENT_TABLES) - 1)

        with (
            patch("iolabs_sdr.scripts.provision_client._CONFIGS_DIR", tmp_path),
            patch("iolabs_sdr.scripts.provision_client.load_client_config", return_value=fake_config),
            patch("psycopg2.connect", return_value=mock_conn),
            patch("iolabs_sdr.scripts.provision_client._run_alembic", return_value=successful_alembic),
            patch("iolabs_sdr.core.rate_limiter.RateLimiter.ping", return_value=True),
        ):
            assert provision_client("test_client") == EXIT_DB_FAILURE

    def test_all_seven_tables_verified(self, tmp_path, mock_conn, successful_alembic):
        (tmp_path / "test_client.json").write_text("{}")
        fake_config = MagicMock()
        fake_config.sender_name = "X"
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.fetchone.return_value = (True,)

        with (
            patch("iolabs_sdr.scripts.provision_client._CONFIGS_DIR", tmp_path),
            patch("iolabs_sdr.scripts.provision_client.load_client_config", return_value=fake_config),
            patch("psycopg2.connect", return_value=mock_conn),
            patch("iolabs_sdr.scripts.provision_client._run_alembic", return_value=successful_alembic),
            patch("iolabs_sdr.core.rate_limiter.RateLimiter.ping", return_value=True),
        ):
            provision_client("test_client")

        # Exactly 7 fetchone calls — one per table
        assert mock_cursor.fetchone.call_count == len(CLIENT_TABLES)


class TestTenantRegistration:
    def test_tenant_insert_uses_on_conflict_do_nothing(self, tmp_path, mock_conn, successful_alembic):
        (tmp_path / "test_client.json").write_text("{}")
        fake_config = MagicMock()
        fake_config.sender_name = "Sender"
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.fetchone.return_value = (True,)

        with (
            patch("iolabs_sdr.scripts.provision_client._CONFIGS_DIR", tmp_path),
            patch("iolabs_sdr.scripts.provision_client.load_client_config", return_value=fake_config),
            patch("psycopg2.connect", return_value=mock_conn),
            patch("iolabs_sdr.scripts.provision_client._run_alembic", return_value=successful_alembic),
            patch("iolabs_sdr.core.rate_limiter.RateLimiter.ping", return_value=True),
        ):
            provision_client("test_client")

        # Find the INSERT call among all execute calls
        insert_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "INSERT INTO platform.tenants" in str(c)
        ]
        assert len(insert_calls) == 1
        sql = insert_calls[0].args[0]
        assert "ON CONFLICT" in sql
        assert "DO NOTHING" in sql

    def test_tenant_registered_with_correct_schema(self, tmp_path, mock_conn, successful_alembic):
        (tmp_path / "test_client.json").write_text("{}")
        fake_config = MagicMock()
        fake_config.sender_name = "My Sender"
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.fetchone.return_value = (True,)

        with (
            patch("iolabs_sdr.scripts.provision_client._CONFIGS_DIR", tmp_path),
            patch("iolabs_sdr.scripts.provision_client.load_client_config", return_value=fake_config),
            patch("psycopg2.connect", return_value=mock_conn),
            patch("iolabs_sdr.scripts.provision_client._run_alembic", return_value=successful_alembic),
            patch("iolabs_sdr.core.rate_limiter.RateLimiter.ping", return_value=True),
        ):
            provision_client("test_client")

        insert_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "INSERT INTO platform.tenants" in str(c)
        ]
        params = insert_calls[0].args[1]
        assert params[0] == "test_client"          # client_id
        assert params[3] == "client_test_client"   # db_schema


class TestRedisReachability:
    def test_redis_unreachable_does_not_abort_provisioning(self, tmp_path, mock_conn, successful_alembic):
        """Redis warning must not abort provisioning — it's only needed at send time."""
        (tmp_path / "test_client.json").write_text("{}")
        fake_config = MagicMock()
        fake_config.sender_name = "X"
        mock_conn.cursor.return_value.fetchone.return_value = (True,)

        with (
            patch("iolabs_sdr.scripts.provision_client._CONFIGS_DIR", tmp_path),
            patch("iolabs_sdr.scripts.provision_client.load_client_config", return_value=fake_config),
            patch("psycopg2.connect", return_value=mock_conn),
            patch("iolabs_sdr.scripts.provision_client._run_alembic", return_value=successful_alembic),
            patch("iolabs_sdr.core.rate_limiter.RateLimiter.ping", return_value=False),
        ):
            result = provision_client("test_client")

        assert result == EXIT_OK  # still succeeds despite Redis being down

    def test_redis_exception_does_not_abort_provisioning(self, tmp_path, mock_conn, successful_alembic):
        (tmp_path / "test_client.json").write_text("{}")
        fake_config = MagicMock()
        fake_config.sender_name = "X"
        mock_conn.cursor.return_value.fetchone.return_value = (True,)

        with (
            patch("iolabs_sdr.scripts.provision_client._CONFIGS_DIR", tmp_path),
            patch("iolabs_sdr.scripts.provision_client.load_client_config", return_value=fake_config),
            patch("psycopg2.connect", return_value=mock_conn),
            patch("iolabs_sdr.scripts.provision_client._run_alembic", return_value=successful_alembic),
            patch("iolabs_sdr.core.rate_limiter.RateLimiter.ping", side_effect=Exception("redis down")),
        ):
            result = provision_client("test_client")

        assert result == EXIT_OK


class TestHappyPath:
    def test_full_happy_path_returns_ok(self, tmp_path, mock_conn, successful_alembic):
        (tmp_path / "test_client.json").write_text("{}")
        fake_config = MagicMock()
        fake_config.client_id = "test_client"
        fake_config.sender_name = "Test Sender"
        mock_conn.cursor.return_value.fetchone.return_value = (True,)

        with (
            patch("iolabs_sdr.scripts.provision_client._CONFIGS_DIR", tmp_path),
            patch("iolabs_sdr.scripts.provision_client.load_client_config", return_value=fake_config),
            patch("psycopg2.connect", return_value=mock_conn),
            patch("iolabs_sdr.scripts.provision_client._run_alembic", return_value=successful_alembic),
            patch("iolabs_sdr.core.rate_limiter.RateLimiter.ping", return_value=True),
        ):
            result = provision_client("test_client")

        assert result == EXIT_OK

    def test_second_run_is_idempotent(self, tmp_path, mock_conn, successful_alembic):
        """Running provision twice must not raise — idempotency guarantee."""
        (tmp_path / "test_client.json").write_text("{}")
        fake_config = MagicMock()
        fake_config.sender_name = "X"
        mock_conn.cursor.return_value.fetchone.return_value = (True,)

        patches = dict(
            configs_dir=patch("iolabs_sdr.scripts.provision_client._CONFIGS_DIR", tmp_path),
            load_config=patch("iolabs_sdr.scripts.provision_client.load_client_config", return_value=fake_config),
            psycopg2=patch("psycopg2.connect", return_value=mock_conn),
            alembic=patch("iolabs_sdr.scripts.provision_client._run_alembic", return_value=successful_alembic),
            redis=patch("iolabs_sdr.core.rate_limiter.RateLimiter.ping", return_value=True),
        )
        for p in patches.values():
            p.start()
        try:
            r1 = provision_client("test_client")
            r2 = provision_client("test_client")
        finally:
            for p in patches.values():
                p.stop()

        assert r1 == EXIT_OK
        assert r2 == EXIT_OK
