"""Notebook schema migration safeguards."""

from pathlib import Path


def test_notebook_schema_defines_created_by_field():
    migrations_dir = Path("open_notebook/database/migrations")
    migration_sql = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(migrations_dir.glob("*.surrealql"))
        if not path.name.endswith("_down.surrealql")
    )

    assert "DEFINE FIELD IF NOT EXISTS created_by ON TABLE notebook TYPE option<string>;" in migration_sql
