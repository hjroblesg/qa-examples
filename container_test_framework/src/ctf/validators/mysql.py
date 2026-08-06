"""MySQL container validator.

Validates a running MySQL container along four axes:

* **connectivity / health** — can we connect and run a trivial query?
* **schema** — do the expected tables and columns exist?
* **CRUD** — does a full insert/select/update/delete round-trip behave?
* **data integrity** — are constraints (e.g. primary-key uniqueness) enforced?

Design for testability: the DB client is *injected*. ``connection_factory`` is a
zero-arg callable that returns a DB-API connection; it defaults to
``mysql.connector.connect(...)`` (imported lazily, so unit tests that supply a
mock factory don't need the driver installed at all). Every check returns a
``ValidationResult`` and never raises, so one failing check can't hide the rest.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ctf.validators.base import ContainerValidator, ValidationResult

log = logging.getLogger("ctf.validators.mysql")


@dataclass
class MySQLConfig:
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: Optional[str] = None
    connect_timeout: int = 10


@dataclass
class MySQLValidator(ContainerValidator):
    # MySQL-friendly defaults (override the base's generic ones).
    image: str = "mysql"
    tag: str = "8.0"

    config: MySQLConfig = field(default_factory=MySQLConfig)
    # table -> list of expected column names. Empty => schema check is skipped.
    expected_schema: dict[str, list[str]] = field(default_factory=dict)
    # Injectable DB-API connection factory (defaults to mysql.connector).
    connection_factory: Optional[Callable[[], Any]] = None

    _conn: Any = field(default=None, init=False, repr=False)

    #: scratch table used by CRUD / integrity checks
    SCRATCH_TABLE = "_ctf_healthcheck"

    # -- connection management --------------------------------------------- #
    def connect(self) -> Any:
        """Return a memoized DB connection, opening one on first use."""
        if self._conn is None:
            factory = self.connection_factory or self._default_factory
            self._conn = factory()
        return self._conn

    def _default_factory(self) -> Any:
        import mysql.connector  # lazy: only needed for real (integration) runs
        c = self.config
        return mysql.connector.connect(
            host=c.host, port=c.port, user=c.user, password=c.password,
            database=c.database, connect_timeout=c.connect_timeout,
        )

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None

    # -- individual checks ------------------------------------------------- #
    def check_connectivity(self) -> ValidationResult:
        try:
            cur = self.connect().cursor()
            cur.execute("SELECT 1")
            row = cur.fetchone()
            cur.close()
            ok = row is not None and row[0] == 1
            detail = "SELECT 1 returned expected value" if ok else f"unexpected result: {row!r}"
            return ValidationResult("connectivity", ok, detail)
        except Exception as e:  # noqa: BLE001 - checks report, never raise
            return ValidationResult("connectivity", False, f"connection failed: {e}")

    def check_schema(self) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        for table, columns in self.expected_schema.items():
            try:
                cur = self.connect().cursor()
                cur.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = %s AND table_name = %s",
                    (self.config.database, table),
                )
                found = {row[0] for row in cur.fetchall()}
                cur.close()
                missing = [c for c in columns if c not in found]
                ok = not missing
                detail = "all expected columns present" if ok else f"missing columns: {missing}"
                results.append(ValidationResult(f"schema:{table}", ok, detail))
            except Exception as e:  # noqa: BLE001
                results.append(ValidationResult(f"schema:{table}", False, str(e)))
        return results

    def check_crud(self) -> ValidationResult:
        conn = self.connect()
        cur = conn.cursor()
        try:
            cur.execute(f"DROP TABLE IF EXISTS {self.SCRATCH_TABLE}")
            cur.execute(
                f"CREATE TABLE {self.SCRATCH_TABLE} (id INT PRIMARY KEY, name VARCHAR(50))"
            )
            cur.execute(
                f"INSERT INTO {self.SCRATCH_TABLE} (id, name) VALUES (%s, %s)", (1, "alpha")
            )
            cur.execute(f"SELECT name FROM {self.SCRATCH_TABLE} WHERE id = %s", (1,))
            inserted = cur.fetchone()
            cur.execute(f"UPDATE {self.SCRATCH_TABLE} SET name = %s WHERE id = %s", ("beta", 1))
            cur.execute(f"SELECT name FROM {self.SCRATCH_TABLE} WHERE id = %s", (1,))
            updated = cur.fetchone()
            cur.execute(f"DELETE FROM {self.SCRATCH_TABLE} WHERE id = %s", (1,))
            cur.execute(f"SELECT COUNT(*) FROM {self.SCRATCH_TABLE}")
            remaining = cur.fetchone()
            conn.commit()
            ok = inserted == ("alpha",) and updated == ("beta",) and remaining == (0,)
            detail = (
                "insert/select/update/delete round-trip OK" if ok
                else f"CRUD mismatch: inserted={inserted}, updated={updated}, remaining={remaining}"
            )
            return ValidationResult("crud", ok, detail)
        except Exception as e:  # noqa: BLE001
            return ValidationResult("crud", False, str(e))
        finally:
            self._drop_scratch(conn, cur)

    def check_data_integrity(self) -> ValidationResult:
        conn = self.connect()
        cur = conn.cursor()
        try:
            cur.execute(f"DROP TABLE IF EXISTS {self.SCRATCH_TABLE}")
            cur.execute(f"CREATE TABLE {self.SCRATCH_TABLE} (id INT PRIMARY KEY)")
            cur.execute(f"INSERT INTO {self.SCRATCH_TABLE} (id) VALUES (1)")
            duplicate_rejected = False
            try:
                cur.execute(f"INSERT INTO {self.SCRATCH_TABLE} (id) VALUES (1)")
                conn.commit()
            except Exception:  # noqa: BLE001 - the DB *should* reject this
                duplicate_rejected = True
                conn.rollback()
            detail = (
                "primary-key uniqueness enforced" if duplicate_rejected
                else "duplicate primary key was NOT rejected"
            )
            return ValidationResult("data_integrity", duplicate_rejected, detail)
        except Exception as e:  # noqa: BLE001
            return ValidationResult("data_integrity", False, str(e))
        finally:
            self._drop_scratch(conn, cur)

    # -- helpers ----------------------------------------------------------- #
    def _drop_scratch(self, conn: Any, cur: Any) -> None:
        try:
            cur.execute(f"DROP TABLE IF EXISTS {self.SCRATCH_TABLE}")
            conn.commit()
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass
        finally:
            try:
                cur.close()
            except Exception:  # noqa: BLE001
                pass

    # -- ContainerValidator hook ------------------------------------------- #
    def checks(self) -> list[ValidationResult]:
        """Run every configured check and collect the results."""
        results: list[ValidationResult] = [self.check_connectivity()]
        results.extend(self.check_schema())
        results.append(self.check_crud())
        results.append(self.check_data_integrity())
        return results
