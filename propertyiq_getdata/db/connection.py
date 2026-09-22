"""Database URLs come from the environment, never from code (PLATFORM.md).

``make -C nmp-central-ai db-init`` writes the P7 block of ``.db-urls.env``;
that block is pasted into this repo's ``.env`` and loaded with
``uv run --env-file .env``. Three roles, three variables:

===============================  ==================  =====================================
variable                         role                used by
===============================  ==================  =====================================
``PROPERTYIQ_ADMIN_DATABASE_URL``  ``nmp`` (superuser)  ``db init`` only (platform D16)
``PROPERTYIQ_DATABASE_URL``        ``propertyiq_owner`` loader, dbt, ``db update``
``PROPERTYIQ_RO_DATABASE_URL``     ``propertyiq_ro``    consumers' fdw mappings, ``db smoke``
===============================  ==================  =====================================
"""

from __future__ import annotations

import os
from typing import Literal

Role = Literal["admin", "owner", "ro"]

ENV_VARS: dict[Role, str] = {
    "admin": "PROPERTYIQ_ADMIN_DATABASE_URL",
    "owner": "PROPERTYIQ_DATABASE_URL",
    "ro": "PROPERTYIQ_RO_DATABASE_URL",
}

PLATFORM_UP_HINT = "make -C ~/git/nmp-ai-portfolio/nmp-central-ai up"


class DatabaseUnavailable(RuntimeError):
    """The central Postgres is not reachable. There is no local fallback by design."""


def database_url(role: Role = "owner") -> str:
    var = ENV_VARS[role]
    url = os.environ.get(var, "").strip()
    if not url:
        raise DatabaseUnavailable(
            f"{var} is not set. Run `make -C ~/git/nmp-ai-portfolio/nmp-central-ai db-init`, "
            "paste the P7 block of .db-urls.env into this repo's .env, and run with `uv run --env-file .env`."
        )
    # SQLAlchemy-style driver suffixes are accepted so a URL copied from another
    # project's .env still works; psycopg wants the bare scheme.
    return url.replace("postgresql+psycopg://", "postgresql://").replace("postgresql+asyncpg://", "postgresql://")


def connect(role: Role = "owner", *, autocommit: bool = True):
    """A psycopg connection as ``role``; wraps connection errors in the platform message.

    Autocommit by default so that ``with conn.transaction():`` blocks are real
    transactions (one per partition in the loader), not savepoints inside an
    implicit never-committed transaction.
    """

    import psycopg

    url = database_url(role)
    try:
        return psycopg.connect(url, autocommit=autocommit, connect_timeout=10)
    except psycopg.OperationalError as exc:
        raise DatabaseUnavailable(
            f"cannot reach the central Postgres ({exc}). Is the platform up? `{PLATFORM_UP_HINT}`"
        ) from exc


__all__ = ["ENV_VARS", "DatabaseUnavailable", "Role", "connect", "database_url"]
