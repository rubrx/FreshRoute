"""Plain-SQL migration runner.

Reads `backend/db/migrations/*.sql` in filename order, applies any that
aren't yet recorded in the `schema_migrations` table, and records them.

Migration files must be named `NNN_description.sql` (three-digit prefix).
"""

from __future__ import annotations

import re
from pathlib import Path

import structlog
from sqlalchemy import text

from backend.db.connection import get_engine

log = structlog.get_logger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
VERSION_RE = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$")


def _discover_migrations() -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        match = VERSION_RE.match(path.name)
        if not match:
            raise ValueError(
                f"Migration filename {path.name!r} does not match NNN_description.sql"
            )
        files.append((match.group(1), path))
    return files


def _applied_versions(conn) -> set[str]:
    # First migration creates the bookkeeping table, so treat missing as empty.
    exists = conn.execute(
        text(
            "SELECT to_regclass('public.schema_migrations') IS NOT NULL AS exists"
        )
    ).scalar_one()
    if not exists:
        return set()
    rows = conn.execute(text("SELECT version FROM schema_migrations")).all()
    return {row[0] for row in rows}


def apply_pending() -> list[str]:
    """Apply any migrations not yet recorded. Returns the versions applied."""
    engine = get_engine()
    applied: list[str] = []

    with engine.begin() as conn:
        existing = _applied_versions(conn)

        for version, path in _discover_migrations():
            if version in existing:
                continue
            sql = path.read_text()
            log.info("applying_migration", version=version, file=path.name)
            # DDL and hypertable creation are safe inside the outer transaction.
            conn.execute(text(sql))
            conn.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:v)"),
                {"v": version},
            )
            applied.append(version)

    if not applied:
        log.info("no_pending_migrations")
    return applied


if __name__ == "__main__":
    apply_pending()
