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


def test_chat_transcript_schema_has_stable_session_sequence_index():
    migration_sql = Path(
        "open_notebook/database/migrations/27.surrealql"
    ).read_text(encoding="utf-8")

    assert "DEFINE TABLE IF NOT EXISTS chat_message SCHEMAFULL;" in migration_sql
    assert "chat_message_session_sequence_idx" in migration_sql
    assert "COLUMNS session, sequence UNIQUE" in migration_sql
