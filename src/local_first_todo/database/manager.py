"""Database manager for Local-First To-Do application.

This module provides the DatabaseManager class which handles:
- Database connection management
- Schema creation and migrations
- Connection configuration (WAL mode, foreign keys, etc.)
- Basic database operations
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional, Any, Dict, List

import aiosqlite

from local_first_todo.database.schema import (
    SCHEMA_VERSION,
    SCHEMA_DDL,
    DATABASE_PRAGMAS,
    FTS_TRIGGERS,
    SCHEMA_MIGRATIONS,
)
from local_first_todo.database.models import Task, TaskStatus

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database connections and operations."""
    
    def __init__(self, db_path: str = "app.db") -> None:
        """Initialize the database manager.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        self._write_lock = asyncio.Lock()
        
    async def initialize(self) -> None:
        """Initialize the database, creating schema if needed."""
        logger.info(f"Initializing database at {self.db_path}")
        
        # Handle in-memory vs file databases differently
        is_memory_db = str(self.db_path) == ":memory:"
        
        if not is_memory_db:
            # Ensure the directory exists for file databases
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            # Check if database file exists
            db_exists = self.db_path.exists()
        else:
            # In-memory databases always need schema creation
            db_exists = False
        
        async with aiosqlite.connect(self.db_path) as conn:
            # Apply pragmas
            await self._apply_pragmas(conn)
            
            logger.debug(f"db_exists = {db_exists}, is_memory_db = {is_memory_db}")
            
            if not db_exists:
                logger.info("Creating new database schema")
                await self._create_schema(conn)
            else:
                logger.info("Database exists, checking for migrations")
                await self._check_and_migrate_schema(conn)
    
    async def _apply_pragmas(self, conn: aiosqlite.Connection) -> None:
        """Apply database pragmas for optimal configuration."""
        for pragma in DATABASE_PRAGMAS:
            logger.debug(f"Applying pragma: {pragma}")
            await conn.execute(pragma)
        await conn.commit()
    
    async def _create_schema(self, conn: aiosqlite.Connection) -> None:
        """Create the complete database schema."""
        try:
            # Create all tables and indexes
            for ddl in SCHEMA_DDL:
                await conn.execute(ddl.strip())
            
            # Create FTS triggers
            for trigger in FTS_TRIGGERS:
                await conn.execute(trigger.strip())
            
            # Set schema version
            await conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            
            await conn.commit()
            logger.info(f"Database schema created successfully (version {SCHEMA_VERSION})")
            
        except Exception as e:
            await conn.rollback()
            logger.error(f"Failed to create database schema: {e}")
            raise
    
    async def _check_and_migrate_schema(self, conn: aiosqlite.Connection) -> None:
        """Check schema version and perform migrations if needed."""
        cursor = await conn.execute("PRAGMA user_version")
        row = await cursor.fetchone()
        current_version = row[0] if row else 0
        
        logger.info(f"Current database version: {current_version}, target: {SCHEMA_VERSION}")
        
        if current_version == SCHEMA_VERSION:
            logger.debug("Database schema is up to date")
            return
        
        if current_version > SCHEMA_VERSION:
            raise RuntimeError(
                f"Database version {current_version} is newer than supported version {SCHEMA_VERSION}. "
                "Please update the application."
            )
        
        # Perform migration
        await self._migrate_schema(conn, current_version, SCHEMA_VERSION)
    
    async def _migrate_schema(
        self, 
        conn: aiosqlite.Connection, 
        from_version: int, 
        to_version: int
    ) -> None:
        """Perform schema migration from one version to another."""
        logger.info(f"Migrating database from version {from_version} to {to_version}")
        
        try:
            if from_version == 0:
                # This is a fresh database, create the schema
                for ddl in SCHEMA_DDL:
                    await conn.execute(ddl.strip())
                
                for trigger in FTS_TRIGGERS:
                    await conn.execute(trigger.strip())
            else:
                # Apply incremental migrations
                for version in range(from_version + 1, to_version + 1):
                    if version in SCHEMA_MIGRATIONS:
                        logger.info(f"Applying migration to version {version}")
                        for migration_ddl in SCHEMA_MIGRATIONS[version]:
                            await conn.execute(migration_ddl.strip())
            
            # Update schema version
            await conn.execute(f"PRAGMA user_version = {to_version}")
            await conn.commit()
            
            logger.info(f"Database migration completed successfully")
            
        except Exception as e:
            await conn.rollback()
            logger.error(f"Database migration failed: {e}")
            raise
    
    async def get_connection(self) -> aiosqlite.Connection:
        """Get a database connection with proper configuration."""
        conn = await aiosqlite.connect(self.db_path)
        await self._apply_pragmas(conn)
        return conn
    
    async def execute_read(self, query: str, params: Optional[tuple] = None) -> List[aiosqlite.Row]:
        """Execute a read-only query and return all results."""
        async with aiosqlite.connect(self.db_path) as conn:
            await self._apply_pragmas(conn)
            conn.row_factory = aiosqlite.Row
            
            cursor = await conn.execute(query, params or ())
            return await cursor.fetchall()
    
    async def execute_write(
        self, 
        query: str, 
        params: Optional[tuple] = None
    ) -> aiosqlite.Cursor:
        """Execute a write query with proper locking."""
        async with self._write_lock:
            async with aiosqlite.connect(self.db_path) as conn:
                await self._apply_pragmas(conn)
                
                cursor = await conn.execute(query, params or ())
                await conn.commit()
                return cursor
    
    async def execute_transaction(self, operations: List[tuple[str, tuple]]) -> None:
        """Execute multiple operations in a single transaction."""
        async with self._write_lock:
            async with aiosqlite.connect(self.db_path) as conn:
                await self._apply_pragmas(conn)
                
                try:
                    for query, params in operations:
                        await conn.execute(query, params)
                    await conn.commit()
                except Exception:
                    await conn.rollback()
                    raise
    
    async def verify_schema_integrity(self) -> Dict[str, Any]:
        """Verify database schema integrity and return status."""
        async with aiosqlite.connect(self.db_path) as conn:
            await self._apply_pragmas(conn)
            
            # Check PRAGMA integrity
            cursor = await conn.execute("PRAGMA integrity_check")
            integrity_result = await cursor.fetchone()
            
            # Check foreign key integrity
            cursor = await conn.execute("PRAGMA foreign_key_check")
            fk_violations = await cursor.fetchall()
            
            # Check schema version
            cursor = await conn.execute("PRAGMA user_version")
            version_row = await cursor.fetchone()
            current_version = version_row[0] if version_row else 0
            
            # Check if tables exist
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row[0] for row in await cursor.fetchall()]
            
            expected_tables = {'Task', 'TaskClosure', 'Blob', 'Attachment', 'UndoLog', 'TaskFTS'}
            missing_tables = expected_tables - set(tables)
            
            return {
                "integrity_check": integrity_result[0] if integrity_result else "Unknown",
                "foreign_key_violations": len(fk_violations),
                "schema_version": current_version,
                "expected_version": SCHEMA_VERSION,
                "tables_present": tables,
                "missing_tables": list(missing_tables),
                "is_healthy": (
                    integrity_result and integrity_result[0] == "ok" and
                    len(fk_violations) == 0 and
                    current_version == SCHEMA_VERSION and
                    len(missing_tables) == 0
                )
            }
    
    async def truncate_wal(self) -> None:
        """Truncate the WAL file to manage growth."""
        async with self._write_lock:
            async with aiosqlite.connect(self.db_path) as conn:
                await self._apply_pragmas(conn)
                await conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                await conn.commit()
                logger.debug("WAL file truncated")
    
    async def close(self) -> None:
        """Close database connections and clean up resources."""
        # Perform final WAL checkpoint
        try:
            await self.truncate_wal()
        except Exception as e:
            logger.warning(f"Failed to truncate WAL on close: {e}")
        
        logger.info("Database manager closed") 