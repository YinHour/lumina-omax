from __future__ import annotations

import asyncio
import os
import random
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypeVar, Union

from loguru import logger
from surrealdb import AsyncSurreal, RecordID  # type: ignore

T = TypeVar("T", Dict[str, Any], List[Dict[str, Any]])

DEFAULT_SURREAL_POOL_SIZE = 10
DEFAULT_SURREAL_POOL_ACQUIRE_TIMEOUT = 5.0
DEFAULT_SURREAL_QUERY_TIMEOUT = 30.0
DEFAULT_SURREAL_TRANSACTION_RETRY_ATTEMPTS = 10


class DatabaseConnectionPool:
    """Small async connection pool for process-local SurrealDB clients."""

    def __init__(
        self,
        *,
        size: int,
        acquire_timeout: float,
        client_factory: Optional[Any] = None,
    ) -> None:
        self.size = size
        self.acquire_timeout = acquire_timeout
        self.client_factory = client_factory or AsyncSurreal
        self._available: Optional[asyncio.Queue[Any]] = None
        self._created: list[Any] = []
        self._init_lock = asyncio.Lock()
        self._closed = False

    @property
    def initialized(self) -> bool:
        return self._available is not None

    @property
    def settings(self) -> tuple[int, float]:
        return (self.size, self.acquire_timeout)

    async def initialize(self) -> None:
        async with self._init_lock:
            if self._available is not None:
                return

            self._available = asyncio.Queue(maxsize=self.size)
            try:
                for _ in range(self.size):
                    connection = await self._open_connection()
                    self._created.append(connection)
                    self._available.put_nowait(connection)
            except Exception:
                await self.close()
                raise

    async def acquire(self) -> Any:
        if self._closed:
            raise RuntimeError("Database connection pool is closed")
        await self.initialize()
        assert self._available is not None

        try:
            return await asyncio.wait_for(
                self._available.get(),
                timeout=self.acquire_timeout,
            )
        except asyncio.TimeoutError as exc:
            raise RuntimeError(
                "Timed out waiting for an available SurrealDB connection "
                f"after {self.acquire_timeout}s"
            ) from exc

    async def release(self, connection: Any) -> None:
        if self._closed or self._available is None:
            await self._close_connection(connection)
            return
        self._available.put_nowait(connection)

    async def close(self) -> None:
        self._closed = True
        for connection in self._created:
            await self._close_connection(connection)
        self._created.clear()
        self._available = None

    async def _open_connection(self) -> Any:
        connection = self.client_factory(get_database_url())
        await connection.signin(
            {
                "username": os.environ.get("SURREAL_USER"),
                "password": get_database_password(),
            }
        )
        await connection.use(
            os.environ.get("SURREAL_NAMESPACE"), os.environ.get("SURREAL_DATABASE")
        )
        return connection

    async def _close_connection(self, connection: Any) -> None:
        with suppress(Exception):
            await connection.close()


_database_pools: dict[int, DatabaseConnectionPool] = {}


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return max(minimum, int(value))
    except ValueError:
        logger.warning(f"Invalid {name}={value!r}; using {default}")
        return default


def _env_float(name: str, default: float, *, minimum: float = 0.0) -> float:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return max(minimum, float(value))
    except ValueError:
        logger.warning(f"Invalid {name}={value!r}; using {default}")
        return default


def _pool_settings() -> tuple[int, float]:
    return (
        _env_int("SURREAL_POOL_SIZE", DEFAULT_SURREAL_POOL_SIZE),
        _env_float(
            "SURREAL_POOL_ACQUIRE_TIMEOUT", DEFAULT_SURREAL_POOL_ACQUIRE_TIMEOUT
        ),
    )


def _get_database_pool() -> DatabaseConnectionPool:
    loop_key = id(asyncio.get_running_loop())
    size, acquire_timeout = _pool_settings()
    pool = _database_pools.get(loop_key)

    if pool is None:
        pool = DatabaseConnectionPool(
            size=size,
            acquire_timeout=acquire_timeout,
        )
        _database_pools[loop_key] = pool
    elif pool.settings != (size, acquire_timeout):
        if pool.initialized:
            raise RuntimeError(
                "SurrealDB pool settings changed after initialization; "
                "restart the process or close the pool before changing settings."
            )
        pool = DatabaseConnectionPool(
            size=size,
            acquire_timeout=acquire_timeout,
        )
        _database_pools[loop_key] = pool
    return pool


async def initialize_database_pool() -> None:
    """Pre-warm the process-local SurrealDB connection pool."""
    await _get_database_pool().initialize()


async def close_database_pool() -> None:
    """Close all event-loop-local SurrealDB connection pools in this process."""

    pools = list(_database_pools.values())
    _database_pools.clear()
    for pool in pools:
        await pool.close()


async def _run_with_query_timeout(operation: Any) -> Any:
    timeout = _env_float("SURREAL_QUERY_TIMEOUT", DEFAULT_SURREAL_QUERY_TIMEOUT)
    if timeout <= 0:
        return await operation
    try:
        return await asyncio.wait_for(operation, timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise RuntimeError(f"SurrealDB query timed out after {timeout}s") from exc


def _is_transaction_conflict(error: Exception) -> bool:
    message = str(error).lower()
    return (
        "transaction" in message
        or "conflict" in message
        or "write-write" in message
    )


def get_database_url():
    """Get database URL with backward compatibility"""
    surreal_url = os.getenv("SURREAL_URL")
    if surreal_url:
        return surreal_url

    # Fallback to old format - WebSocket URL format
    address = os.getenv("SURREAL_ADDRESS", "localhost")
    port = os.getenv("SURREAL_PORT", "8000")
    return f"ws://{address}:{port}/rpc"


def get_database_password():
    """Get password with backward compatibility"""
    return os.getenv("SURREAL_PASSWORD") or os.getenv("SURREAL_PASS")


def parse_record_ids(obj: Any) -> Any:
    """Recursively parse and convert RecordIDs into strings."""
    if isinstance(obj, dict):
        return {k: parse_record_ids(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [parse_record_ids(item) for item in obj]
    elif isinstance(obj, RecordID):
        return str(obj)
    return obj


def ensure_record_id(value: Union[str, RecordID]) -> RecordID:
    """Ensure a value is a RecordID."""
    if isinstance(value, RecordID):
        return value
    return RecordID.parse(value)


@asynccontextmanager
async def db_connection():
    pool = _get_database_pool()
    db = await pool.acquire()
    try:
        yield db
    finally:
        await pool.release(db)


def _extract_query_results(response: Any) -> Any:
    """Extract results from a raw SurrealDB query response.

    The surrealdb client's ``query()`` only returns the first statement's
    result (``response["result"][0]["result"]``), silently dropping data from
    multi-statement queries such as ``LET ...; RETURN ...``. Parse the raw
    response here instead and return the last statement's result - the
    conventional final RETURN - while keeping single-statement behavior
    unchanged. Any statement-level ``ERR`` status is raised as RuntimeError
    so transaction-conflict retry semantics are preserved.
    """
    if not isinstance(response, dict):
        return response
    if response.get("error") is not None:
        error = response.get("error")
        if isinstance(error, dict):
            raise RuntimeError(error.get("message", "Unknown SurrealDB error"))
        raise RuntimeError(str(error))
    statements = response.get("result")
    if not isinstance(statements, list) or not statements:
        return response
    for item in statements:
        if isinstance(item, dict) and item.get("status") == "ERR":
            raise RuntimeError(item.get("detail", "Unknown SurrealDB error"))
    last = statements[-1]
    if isinstance(last, dict):
        return last.get("result")
    return response


async def repo_query(
    query_str: str, vars: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Execute a SurrealQL query and return the results"""

    async with db_connection() as connection:
        try:
            raw_response = await _run_with_query_timeout(
                connection.query_raw(query_str, vars)
            )
            result = parse_record_ids(_extract_query_results(raw_response))
            if isinstance(result, str):
                raise RuntimeError(result)
            return result
        except RuntimeError as e:
            # RuntimeError is raised for retriable transaction conflicts - log at debug to avoid noise
            logger.debug(str(e))
            raise
        except Exception as e:
            logger.exception(e)
            raise


async def repo_transaction(
    query_body: str, vars: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Execute a SurrealQL transaction body and return the results."""
    query = f"""
    BEGIN TRANSACTION;
    {query_body}
    COMMIT TRANSACTION;
    """
    max_attempts = _env_int(
        "SURREAL_TRANSACTION_RETRY_ATTEMPTS",
        DEFAULT_SURREAL_TRANSACTION_RETRY_ATTEMPTS,
    )
    for attempt in range(1, max_attempts + 1):
        try:
            return await repo_query(query, vars)
        except RuntimeError as e:
            if attempt >= max_attempts or not _is_transaction_conflict(e):
                raise
            delay = random.uniform(0.1, min(1.0, 0.1 * (2**attempt)))
            logger.debug(
                "Retrying SurrealDB transaction after conflict "
                f"(attempt {attempt + 1}/{max_attempts}, delay={delay:.3f}s): {e}"
            )
            await asyncio.sleep(delay)

    raise RuntimeError("SurrealDB transaction retry loop exited unexpectedly")


async def repo_create(table: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new record in the specified table"""
    # Remove 'id' attribute if it exists in data
    data.pop("id", None)
    data["created"] = datetime.now(timezone.utc)
    data["updated"] = datetime.now(timezone.utc)
    try:
        query = f"CREATE {table} CONTENT $data;"
        result = await repo_transaction(query, {"data": data})
        return parse_record_ids(result)
    except RuntimeError as e:
        logger.error(str(e))
        raise
    except Exception as e:
        logger.exception(e)
        raise RuntimeError("Failed to create record")


async def repo_relate(
    source: str, relationship: str, target: str, data: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Create a relationship between two records with optional data"""
    if data is None:
        data = {}
    query = f"RELATE {source}->{relationship}->{target} CONTENT $data;"
    # logger.debug(f"Relate query: {query}")

    return await repo_transaction(
        query,
        {
            "data": data,
        },
    )


async def repo_upsert(
    table: str, id: Optional[str], data: Dict[str, Any], add_timestamp: bool = False
) -> List[Dict[str, Any]]:
    """Create or update a record in the specified table"""
    data.pop("id", None)
    if add_timestamp:
        data["updated"] = datetime.now(timezone.utc)
    query = f"UPSERT {id if id else table} MERGE $data;"
    return await repo_transaction(query, {"data": data})


async def repo_update(
    table: str, id: str, data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Update an existing record by table and id"""
    # If id already contains the table name, use it as is
    try:
        if isinstance(id, RecordID) or (":" in id and id.startswith(f"{table}:")):
            record_id = id
        else:
            record_id = f"{table}:{id}"
        data.pop("id", None)
        if "created" in data and isinstance(data["created"], str):
            data["created"] = datetime.fromisoformat(data["created"])
        data["updated"] = datetime.now(timezone.utc)
        query = f"UPDATE {record_id} MERGE $data;"
        # logger.debug(f"Update query: {query}")
        result = await repo_transaction(query, {"data": data})
        # if isinstance(result, list):
        #     return [_return_data(item) for item in result]
        return parse_record_ids(result)
    except Exception as e:
        raise RuntimeError(f"Failed to update record: {str(e)}")


async def repo_delete(record_id: Union[str, RecordID]):
    """Delete a record by record id"""
    try:
        query = f"DELETE {ensure_record_id(record_id)};"
        return await repo_transaction(query)
    except Exception as e:
        logger.exception(e)
        raise RuntimeError(f"Failed to delete record: {str(e)}")


async def repo_insert(
    table: str, data: List[Dict[str, Any]], ignore_duplicates: bool = False
) -> List[Dict[str, Any]]:
    """Create a new record in the specified table"""
    try:
        async with db_connection() as connection:
            result = parse_record_ids(
                await _run_with_query_timeout(connection.insert(table, data))
            )
            # SurrealDB may return a string error message instead of the expected records
            if isinstance(result, str):
                raise RuntimeError(result)
            return result
    except RuntimeError as e:
        if ignore_duplicates and "already contains" in str(e):
            return []
        # Log transaction conflicts at debug level (they are expected during concurrent operations)
        error_str = str(e).lower()
        if "transaction" in error_str or "conflict" in error_str:
            logger.debug(str(e))
        else:
            logger.error(str(e))
        raise
    except Exception as e:
        if ignore_duplicates and "already contains" in str(e):
            return []
        logger.exception(e)
        raise RuntimeError("Failed to create record")
