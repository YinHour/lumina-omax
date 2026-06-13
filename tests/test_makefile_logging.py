from pathlib import Path


def test_source_frontend_targets_write_frontend_log():
    makefile = Path("Makefile").read_text()

    assert "tee logs/frontend.log" in makefile
    assert "npm run dev -- -H 0.0.0.0 -p 3001) 2>&1" in makefile


def test_database_target_follows_surrealdb_log():
    makefile = Path("Makefile").read_text()

    assert "docker logs -f surrealdb-v2" in makefile
    assert "logs/surrealdb.log" in makefile


def test_makefile_version_does_not_require_python_command():
    makefile = Path("Makefile").read_text()

    assert "python -c" not in makefile
    assert "sed -n" in makefile


def test_makefile_logging_timestamps_do_not_use_gawk_only_strftime():
    makefile = Path("Makefile").read_text()

    assert "strftime(" not in makefile
    assert "date '+%Y-%m-%d %H:%M:%S'" in makefile
    assert "logs/api.log" in makefile
    assert "logs/worker.log" in makefile
    assert "logs/frontend.log" in makefile
