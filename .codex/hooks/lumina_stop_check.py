#!/usr/bin/env python3
"""Print non-blocking workflow reminders for Lumina-Omax Codex sessions."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _run(args: list[str]) -> str:
    result = subprocess.run(args, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return ""
    return result.stdout


def _changed_files() -> set[str]:
    files: set[str] = set()
    for cmd in (
        ["git", "diff", "--name-only", "HEAD"],
        ["git", "diff", "--name-only", "--cached"],
    ):
        files.update(line.strip() for line in _run(cmd).splitlines() if line.strip())
    return files


def main() -> int:
    root = _run(["git", "rev-parse", "--show-toplevel"]).strip()
    if not root:
        return 0
    if Path.cwd().resolve() != Path(root).resolve():
        return 0

    changed = _changed_files()
    if not changed:
        return 0

    frontend_visible = {
        path
        for path in changed
        if path.startswith("frontend/src/")
        and path.endswith((".tsx", ".ts", ".css"))
        and "/lib/locales/" not in path
        and not path.endswith((".test.ts", ".test.tsx"))
    }
    locale_changed = any(path.startswith("frontend/src/lib/locales/") for path in changed)
    customization_changed = "docs/8-CUSTOMIZATION/00-index.md" in changed

    reminders: list[str] = []
    if frontend_visible and not locale_changed:
        reminders.append(
            "Lumina-Omax reminder: frontend-visible changes detected; confirm i18n keys are not needed."
        )

    durable_paths = (
        "api/",
        "commands/",
        "frontend/src/",
        "open_notebook/",
        "prompts/",
        "Makefile",
        ".codex/",
        ".agents/",
    )
    durable_change = any(
        path.startswith(durable_paths) or path in {"AGENTS.md", "DESIGN.md"}
        for path in changed
    )
    if durable_change and not customization_changed:
        reminders.append(
            "Lumina-Omax reminder: durable project behavior changed; update docs/8-CUSTOMIZATION/00-index.md or note why it is unnecessary."
        )

    if reminders:
        print("\n".join(reminders))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
