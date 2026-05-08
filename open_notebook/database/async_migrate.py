"""
Async migration system for SurrealDB using the official Python client.
Based on patterns from sblpy migration system.
"""

import os
from pathlib import Path
from typing import List

from loguru import logger

from .repository import db_connection, repo_query


class AsyncMigration:
    """
    Handles individual migration operations with async support.
    """

    def __init__(self, sql: str) -> None:
        """Initialize migration with SQL content."""
        self.sql = sql

    @classmethod
    def from_file(cls, file_path: str) -> "AsyncMigration":
        """Create migration from SQL file."""
        with open(file_path, "r", encoding="utf-8") as file:
            raw_content = file.read()
            # Clean up SQL content
            lines = []
            for line in raw_content.split("\n"):
                line = line.strip()
                if line and not line.startswith("--"):
                    lines.append(line)
            sql = " ".join(lines)
            return cls(sql)

    async def run(self, bump: bool = True) -> None:
        """Run the migration."""
        try:
            if self.sql.strip():
                async with db_connection() as connection:
                    await connection.query(self.sql)

            if bump:
                await bump_version()
            else:
                await lower_version()

        except Exception as e:
            logger.error(f"Migration failed: {str(e)}")
            raise


class AsyncMigrationRunner:
    """
    Handles running multiple migrations in sequence.
    """

    def __init__(
        self,
        up_migrations: List[AsyncMigration],
        down_migrations: List[AsyncMigration],
    ) -> None:
        """Initialize runner with migration lists."""
        self.up_migrations = up_migrations
        self.down_migrations = down_migrations

    async def run_all(self) -> None:
        """Run all pending up migrations."""
        current_version = await get_latest_version()

        for i in range(current_version, len(self.up_migrations)):
            logger.info(f"Running migration {i + 1}")
            await self.up_migrations[i].run(bump=True)

    async def run_one_up(self) -> None:
        """Run one up migration."""
        current_version = await get_latest_version()

        if current_version < len(self.up_migrations):
            logger.info(f"Running migration {current_version + 1}")
            await self.up_migrations[current_version].run(bump=True)

    async def run_one_down(self) -> None:
        """Run one down migration."""
        current_version = await get_latest_version()

        if current_version > 0:
            logger.info(f"Rolling back migration {current_version}")
            await self.down_migrations[current_version - 1].run(bump=False)


class AsyncMigrationManager:
    """
    Main migration manager with async support.
    """

    def __init__(self):
        """Initialize migration manager dynamically."""
        self.up_migrations = []
        self.down_migrations = []
        self._load_migrations()
        self.runner = AsyncMigrationRunner(
            up_migrations=self.up_migrations,
            down_migrations=self.down_migrations,
        )

    def _load_migrations(self):
        """Dynamically load migrations from the migrations directory."""
        migrations_dir = Path("open_notebook/database/migrations")
        
        # Get all valid .surrealql files that start with a number
        # Up migrations are like "1.surrealql", "2.surrealql", etc.
        # Down migrations are like "1_down.surrealql", "2_down.surrealql", etc.
        
        if not migrations_dir.exists():
            logger.warning(f"Migrations directory not found at {migrations_dir}")
            return
            
        up_files = []
        for f in migrations_dir.glob("*.surrealql"):
            if not f.name.endswith("_down.surrealql") and f.name.split(".")[0].isdigit():
                up_files.append(f)
                
        # Sort them numerically based on the prefix number
        up_files.sort(key=lambda x: int(x.name.split(".")[0]))
        
        max_migration_num = 0
        if up_files:
            max_migration_num = int(up_files[-1].name.split(".")[0])
            
        # Ensure there are no gaps in the migration sequence up to the maximum number
        for i in range(1, max_migration_num + 1):
            up_path = migrations_dir / f"{i}.surrealql"
            down_path = migrations_dir / f"{i}_down.surrealql"
            
            # Use empty migration if the file is missing to preserve version continuity
            # (Though ideally there shouldn't be missing files in a sequence)
            if up_path.exists():
                self.up_migrations.append(AsyncMigration.from_file(str(up_path)))
            else:
                logger.warning(f"Missing up migration file: {up_path}, using empty migration")
                self.up_migrations.append(AsyncMigration(""))
                
            if down_path.exists():
                self.down_migrations.append(AsyncMigration.from_file(str(down_path)))
            else:
                # Down migrations are optional, but we add an empty one to keep array indexes aligned
                self.down_migrations.append(AsyncMigration(""))

    async def get_current_version(self) -> int:
        """Get current database version."""
        return await get_latest_version()

    async def needs_migration(self) -> bool:
        """Check if migration is needed."""
        current_version = await self.get_current_version()
        return current_version < len(self.up_migrations)

    async def run_migration_up(self):
        """Run all pending migrations."""
        current_version = await self.get_current_version()
        logger.info(f"Current version before migration: {current_version}")

        if await self.needs_migration():
            try:
                await self.runner.run_all()
                new_version = await self.get_current_version()
                logger.info(f"Migration successful. New version: {new_version}")
            except Exception as e:
                logger.error(f"Migration failed: {str(e)}")
                raise
        else:
            logger.info("Database is already at the latest version")


# Database version management functions
async def get_latest_version() -> int:
    """Get the latest version from the migrations table."""
    try:
        versions = await get_all_versions()
        if not versions:
            return 0
        return max(version["version"] for version in versions)
    except Exception:
        # If migrations table doesn't exist, we're at version 0
        return 0


async def get_all_versions() -> List[dict]:
    """Get all versions from the migrations table."""
    try:
        result = await repo_query("SELECT * FROM _sbl_migrations ORDER BY version;")
        return result
    except Exception:
        # If table doesn't exist, return empty list
        return []


async def bump_version() -> None:
    """Bump the version by adding a new entry to migrations table."""
    current_version = await get_latest_version()
    new_version = current_version + 1

    await repo_query(
        "CREATE type::thing('_sbl_migrations', $version) SET version = $version, applied_at = time::now();",
        {"version": new_version},
    )


async def lower_version() -> None:
    """Lower the version by removing the latest entry from migrations table."""
    current_version = await get_latest_version()
    if current_version > 0:
        await repo_query(
            "DELETE type::thing('_sbl_migrations', $version);",
            {"version": current_version},
        )
