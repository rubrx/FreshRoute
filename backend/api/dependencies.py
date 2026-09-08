"""FastAPI dependencies. Kept intentionally small — one file, two helpers.

`get_db` is the request-scoped SQLAlchemy session. `commit_after` is opt-in
for endpoints that write; the demo API is read-only so most routes skip it.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from backend.db.connection import _session_factory


def get_db() -> Iterator[Session]:
    session = _session_factory()()
    try:
        yield session
    finally:
        session.close()
