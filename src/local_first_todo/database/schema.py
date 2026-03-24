"""Database schema definitions for Local-First To-Do application.

This module contains the SQL DDL statements for creating and managing
the database schema as specified in the SDD.
"""

# Current schema version - increment when making schema changes
SCHEMA_VERSION = 3

# Schema creation statements in dependency order
SCHEMA_DDL = [
    # Main table for tasks
    """
    CREATE TABLE Task (
        id INTEGER PRIMARY KEY,
        uuid TEXT UNIQUE NOT NULL,
        revision INTEGER NOT NULL DEFAULT 0,
        title TEXT NOT NULL,
        description TEXT,
        recurrence_rrule TEXT,
        recurrence_start_utc TEXT CHECK(strftime('%Y-%m-%dT%H:%M:%SZ', recurrence_start_utc) = recurrence_start_utc),
        next_due_utc TEXT CHECK(strftime('%Y-%m-%dT%H:%M:%SZ', next_due_utc) = next_due_utc),
        status TEXT CHECK(status IN ('pending', 'in_progress', 'completed', 'deleted', 'deferred')),
        priority INTEGER,
        created_at TEXT CHECK(strftime('%Y-%m-%dT%H:%M:%SZ', created_at) = created_at),
        updated_at TEXT CHECK(strftime('%Y-%m-%dT%H:%M:%SZ', updated_at) = updated_at),
        deleted_at TEXT CHECK(strftime('%Y-%m-%dT%H:%M:%SZ', deleted_at) = deleted_at)
    )
    """,
    
    # Index to accelerate dashboard and status-based queries
    """
    CREATE INDEX idx_task_status_due ON Task(status, next_due_utc)
    """,
    
    # Space-optimized closure table for infinite task hierarchy with ordering
    """
    CREATE TABLE TaskClosure (
        ancestor_id INTEGER NOT NULL,
        descendant_id INTEGER NOT NULL,
        depth INTEGER NOT NULL,
        sort_order INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (ancestor_id, descendant_id),
        FOREIGN KEY(ancestor_id) REFERENCES Task(id) ON DELETE CASCADE,
        FOREIGN KEY(descendant_id) REFERENCES Task(id) ON DELETE CASCADE
    ) WITHOUT ROWID
    """,
    
    # Index for descendant lookups
    """
    CREATE INDEX idx_taskclosure_descendant ON TaskClosure(descendant_id)
    """,
    
    # Index for efficient ordering queries
    """
    CREATE INDEX idx_taskclosure_order ON TaskClosure(ancestor_id, depth, sort_order)
    """,
    
    # Table for physical, deduplicated file blobs
    """
    CREATE TABLE Blob (
        sha256 TEXT PRIMARY KEY,
        size_bytes INTEGER NOT NULL,
        created_at TEXT CHECK(strftime('%Y-%m-%dT%H:%M:%SZ', created_at) = created_at)
    ) WITHOUT ROWID
    """,
    
    # Linking table for task attachments
    """
    CREATE TABLE Attachment (
        id INTEGER PRIMARY KEY,
        uuid TEXT UNIQUE NOT NULL,
        task_id INTEGER NOT NULL,
        blob_sha256 TEXT NOT NULL,
        original_filename TEXT NOT NULL,
        created_at TEXT CHECK(strftime('%Y-%m-%dT%H:%M:%SZ', created_at) = created_at),
        FOREIGN KEY(task_id) REFERENCES Task(id) ON DELETE CASCADE,
        FOREIGN KEY(blob_sha256) REFERENCES Blob(sha256)
    )
    """,
    
    # Unique constraint to prevent duplicate filenames within a task
    """
    CREATE UNIQUE INDEX idx_attachment_task_filename ON Attachment(task_id, original_filename)
    """,
    
    # Virtual table for full-text search using FTS5
    """
    CREATE VIRTUAL TABLE TaskFTS USING fts5(title, description, tokenize='unicode61')
    """,
    
    # Table for persistent undo/redo history
    """
    CREATE TABLE UndoLog (
        id INTEGER PRIMARY KEY,
        command_payload TEXT NOT NULL,
        applied_at TEXT NOT NULL CHECK(strftime('%Y-%m-%dT%H:%M:%SZ', applied_at) = applied_at),
        status TEXT NOT NULL DEFAULT 'APPLIED' CHECK(status IN ('PENDING', 'APPLIED'))
    )
    """,
]

# Schema migration statements for upgrading from older versions
SCHEMA_MIGRATIONS = {
    # Migration from version 1 to version 2: Add status column to UndoLog
    2: [
        """
        ALTER TABLE UndoLog ADD COLUMN status TEXT NOT NULL DEFAULT 'APPLIED' CHECK(status IN ('PENDING', 'APPLIED'))
        """
    ],
    
    # Migration from version 2 to version 3: Add sort_order column and index to TaskClosure
    3: [
        """
        ALTER TABLE TaskClosure ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0
        """,
        """
        CREATE INDEX idx_taskclosure_order ON TaskClosure(ancestor_id, depth, sort_order)
        """
    ]
}

# Database pragmas to be applied on every connection
DATABASE_PRAGMAS = [
    "PRAGMA foreign_keys=ON",  # Enforce foreign key constraints
    "PRAGMA journal_mode=WAL", # Write-Ahead Logging for better concurrency
    "PRAGMA synchronous=NORMAL", # Balance between safety and performance
    "PRAGMA temp_store=MEMORY",  # Store temporary tables in memory
    "PRAGMA cache_size=-64000",  # 64MB cache size (negative = KB)
]

# FTS5 trigger statements to keep TaskFTS in sync with Task table
FTS_TRIGGERS = [
    # Insert trigger - MUST set rowid explicitly to match Task.id
    # Without this, FTS5 auto-generates rowids which drift after hard deletes
    """
    CREATE TRIGGER task_fts_insert AFTER INSERT ON Task
    BEGIN
        INSERT INTO TaskFTS(rowid, title, description) 
        VALUES (NEW.id, NEW.title, COALESCE(NEW.description, ''));
    END
    """,
    
    # Update trigger
    """
    CREATE TRIGGER task_fts_update AFTER UPDATE ON Task
    BEGIN
        UPDATE TaskFTS SET title = NEW.title, description = COALESCE(NEW.description, '') 
        WHERE rowid = NEW.id;
    END
    """,
    
    # Delete trigger
    """
    CREATE TRIGGER task_fts_delete AFTER DELETE ON Task
    BEGIN
        DELETE FROM TaskFTS WHERE rowid = OLD.id;
    END
    """,
] 