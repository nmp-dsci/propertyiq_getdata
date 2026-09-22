"""Run the ``dbt/`` project against the owner connection.

dbt's profile (``dbt/profiles.yml``) reads ``DBT_HOST``/``DBT_PORT``/
``DBT_USER``/``DBT_PASSWORD``/``DBT_DBNAME``; this module derives them from
``PROPERTYIQ_DATABASE_URL`` so there is still exactly one place a URL lives.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlparse

from ..core.paths import REPO_ROOT
from .connection import database_url

DBT_DIR = REPO_ROOT / "dbt"


def dbt_env(url: str | None = None) -> dict[str, str]:
    """The ``DBT_*`` variables for ``profiles.yml``, derived from the owner URL."""

    parts = urlparse(url or database_url("owner"))
    env = {
        "DBT_HOST": parts.hostname or "localhost",
        "DBT_PORT": str(parts.port or 5432),
        "DBT_USER": unquote(parts.username or ""),
        "DBT_PASSWORD": unquote(parts.password or ""),
        "DBT_DBNAME": parts.path.lstrip("/"),
        "DBT_PROFILES_DIR": str(DBT_DIR),
    }
    if not env["DBT_USER"] or not env["DBT_DBNAME"]:
        raise ValueError("PROPERTYIQ_DATABASE_URL must carry a user and a database name")
    return env


def dbt_command(args: list[str], *, project_dir: Path = DBT_DIR) -> list[str]:
    exe = shutil.which("dbt")
    if exe is None:
        raise RuntimeError("dbt is not installed; run `uv sync --extra db`")
    return [
        exe,
        *args,
        "--project-dir",
        str(project_dir),
        "--profiles-dir",
        str(project_dir),
    ]


def run_dbt(args: list[str], *, project_dir: Path = DBT_DIR, log=print) -> int:
    """Run one dbt command with the derived env, streaming output. Returns the exit code."""

    cmd = dbt_command(args, project_dir=project_dir)
    log(f"==> dbt {' '.join(args)}")
    env = {**os.environ, **dbt_env()}
    return subprocess.run(cmd, env=env, cwd=project_dir).returncode


def test_counts(project_dir: Path = DBT_DIR) -> tuple[int | None, int | None]:
    """``(passed, total)`` tests from ``target/run_results.json``; ``(None, None)`` if absent.

    Read from dbt's own artifact, not parsed from stdout, so a log-format
    change cannot silently turn "all green" into "no data".
    """

    try:
        results = json.loads((project_dir / "target" / "run_results.json").read_text())
    except (OSError, ValueError):
        return None, None
    tests = [r for r in results.get("results", []) if str(r.get("unique_id", "")).startswith("test.")]
    if not tests:
        return None, None
    return sum(1 for r in tests if r.get("status") == "pass"), len(tests)


__all__ = ["DBT_DIR", "dbt_command", "dbt_env", "run_dbt", "test_counts"]
