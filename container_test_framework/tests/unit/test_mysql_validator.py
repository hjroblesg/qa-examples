"""Unit tests for ``ctf.validators.mysql.MySQLValidator``.

The DB client is injected as a mock ``connection_factory``, so these tests run
with **no MySQL server and without the mysql-connector driver installed**. They
assert three things per check: the SQL/params issued, how results are
interpreted, and that failures degrade into a failed ``ValidationResult`` rather
than an exception.

Techniques: dependency injection, Mock cursor with ``fetchone.side_effect``
sequencing, ``call_args_list`` SQL assertions, parametrized pass/fail cases.
"""
from unittest.mock import MagicMock

import pytest

from ctf.validators.mysql import MySQLConfig, MySQLValidator
from ctf.validators.base import ValidationResult

pytestmark = [pytest.mark.unit, pytest.mark.mysql]


@pytest.fixture
def mock_conn():
    conn = MagicMock(name="connection")
    cur = MagicMock(name="cursor")
    conn.cursor.return_value = cur
    return conn, cur


@pytest.fixture
def validator(mock_conn):
    conn, cur = mock_conn
    v = MySQLValidator(
        image="mysql",
        tag="8.0",
        config=MySQLConfig(database="testdb"),
        connection_factory=lambda: conn,
    )
    return v, conn, cur


def _executed_sql(cur):
    """All SQL statements passed to cursor.execute, in order."""
    return [call.args[0] for call in cur.execute.call_args_list]


# --------------------------------------------------------------------------- #
# connection management                                                       #
# --------------------------------------------------------------------------- #
class TestConnection:
    def test_uses_injected_factory_and_memoizes(self):
        conn = MagicMock()
        factory = MagicMock(return_value=conn)
        v = MySQLValidator(connection_factory=factory)

        assert v.connect() is conn
        assert v.connect() is conn          # second call reuses
        factory.assert_called_once()        # ...factory only invoked once

    def test_default_factory_is_not_touched_when_injected(self, validator):
        # No mysql.connector import should be required in these tests.
        v, conn, _ = validator
        assert v.connect() is conn

    def test_close_closes_and_clears_connection(self, validator):
        v, conn, _ = validator
        v.connect()
        v.close()
        conn.close.assert_called_once()
        assert v._conn is None
        v.close()  # idempotent — safe to call again

    def test_default_factory_lazily_imports_driver(self, monkeypatch):
        """The real factory imports mysql.connector only when called. We inject a
        fake module so this runs without the driver installed."""
        import sys
        fake_conn = MagicMock(name="real_connection")
        fake_connector = MagicMock()
        fake_connector.connect.return_value = fake_conn
        fake_module = MagicMock()
        fake_module.connector = fake_connector
        monkeypatch.setitem(sys.modules, "mysql", fake_module)
        monkeypatch.setitem(sys.modules, "mysql.connector", fake_connector)

        v = MySQLValidator(config=MySQLConfig(host="db", port=3307, user="u"))
        assert v.connect() is fake_conn
        kwargs = fake_connector.connect.call_args.kwargs
        assert kwargs["host"] == "db" and kwargs["port"] == 3307 and kwargs["user"] == "u"


# --------------------------------------------------------------------------- #
# connectivity / health                                                       #
# --------------------------------------------------------------------------- #
class TestConnectivity:
    def test_passes_on_select_1(self, validator):
        v, conn, cur = validator
        cur.fetchone.return_value = (1,)

        result = v.check_connectivity()

        assert isinstance(result, ValidationResult)
        assert result.name == "connectivity" and result.passed is True
        assert _executed_sql(cur) == ["SELECT 1"]

    def test_fails_on_unexpected_value(self, validator):
        v, conn, cur = validator
        cur.fetchone.return_value = (0,)
        result = v.check_connectivity()
        assert result.passed is False
        assert "unexpected" in result.detail

    def test_fails_gracefully_when_connection_raises(self):
        boom = MagicMock(side_effect=OSError("no route to host"))
        v = MySQLValidator(connection_factory=boom)
        result = v.check_connectivity()
        assert result.passed is False
        assert "connection failed" in result.detail


# --------------------------------------------------------------------------- #
# schema                                                                       #
# --------------------------------------------------------------------------- #
class TestSchema:
    def test_passes_when_all_columns_present(self, validator):
        v, conn, cur = validator
        v.expected_schema = {"users": ["id", "email"]}
        cur.fetchall.return_value = [("id",), ("email",), ("created_at",)]

        results = v.check_schema()

        assert len(results) == 1
        assert results[0].name == "schema:users" and results[0].passed is True
        # queries information_schema, scoped to the configured database + table
        sql = _executed_sql(cur)[0]
        assert "information_schema.columns" in sql
        assert cur.execute.call_args.args[1] == ("testdb", "users")

    def test_fails_and_lists_missing_columns(self, validator):
        v, conn, cur = validator
        v.expected_schema = {"users": ["id", "email", "phone"]}
        cur.fetchall.return_value = [("id",), ("email",)]

        results = v.check_schema()

        assert results[0].passed is False
        assert "phone" in results[0].detail

    def test_empty_schema_yields_no_results(self, validator):
        v, conn, cur = validator
        assert v.check_schema() == []

    def test_fails_gracefully_on_query_error(self, validator):
        v, conn, cur = validator
        v.expected_schema = {"users": ["id"]}
        cur.execute.side_effect = RuntimeError("information_schema unavailable")
        results = v.check_schema()
        assert results[0].passed is False
        assert "information_schema unavailable" in results[0].detail


# --------------------------------------------------------------------------- #
# CRUD                                                                         #
# --------------------------------------------------------------------------- #
class TestCrud:
    def test_full_round_trip_passes(self, validator):
        v, conn, cur = validator
        # fetchone is called after: insert-select, update-select, count
        cur.fetchone.side_effect = [("alpha",), ("beta",), (0,)]

        result = v.check_crud()

        assert result.name == "crud" and result.passed is True
        sql = " ".join(_executed_sql(cur))
        for verb in ("CREATE TABLE", "INSERT INTO", "UPDATE", "DELETE", "SELECT COUNT"):
            assert verb in sql
        conn.commit.assert_called()          # changes were committed
        # scratch table cleaned up at the end
        assert any("DROP TABLE IF EXISTS" in s for s in _executed_sql(cur))

    def test_detects_bad_update(self, validator):
        v, conn, cur = validator
        # update didn't take -> still "alpha"
        cur.fetchone.side_effect = [("alpha",), ("alpha",), (0,)]
        result = v.check_crud()
        assert result.passed is False
        assert "CRUD mismatch" in result.detail

    def test_fails_gracefully_on_db_error(self, validator):
        v, conn, cur = validator
        cur.execute.side_effect = RuntimeError("table is read only")
        result = v.check_crud()
        assert result.passed is False
        assert "read only" in result.detail


# --------------------------------------------------------------------------- #
# data integrity                                                              #
# --------------------------------------------------------------------------- #
class TestDataIntegrity:
    def test_passes_when_duplicate_pk_rejected(self, validator):
        v, conn, cur = validator
        # 1st three executes ok (drop/create/insert); the *duplicate* insert raises
        cur.execute.side_effect = [None, None, None, RuntimeError("Duplicate entry '1'"), None, None]

        result = v.check_data_integrity()

        assert result.name == "data_integrity" and result.passed is True
        assert "uniqueness enforced" in result.detail
        conn.rollback.assert_called_once()

    def test_fails_when_duplicate_pk_accepted(self, validator):
        v, conn, cur = validator
        cur.execute.side_effect = None  # nothing raises -> duplicate wrongly accepted
        result = v.check_data_integrity()
        assert result.passed is False
        assert "NOT rejected" in result.detail

    def test_fails_gracefully_when_setup_errors(self, validator):
        v, conn, cur = validator
        # the CREATE TABLE (2nd execute) blows up before we can test the constraint
        cur.execute.side_effect = [None, RuntimeError("disk full")]
        result = v.check_data_integrity()
        assert result.passed is False
        assert "disk full" in result.detail


# --------------------------------------------------------------------------- #
# checks() aggregation                                                        #
# --------------------------------------------------------------------------- #
def test_checks_aggregates_all_dimensions(validator):
    v, conn, cur = validator
    v.expected_schema = {"users": ["id"]}
    cur.fetchone.side_effect = [
        (1,),                       # connectivity SELECT 1
        ("alpha",), ("beta",), (0,) # crud round-trip
    ]
    cur.fetchall.return_value = [("id",)]

    results = v.checks()

    names = [r.name for r in results]
    assert names == ["connectivity", "schema:users", "crud", "data_integrity"]
    assert all(isinstance(r, ValidationResult) for r in results)
