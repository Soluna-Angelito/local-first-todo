"""Data models and types for the Local-First To-Do application."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class TaskStatus(str, Enum):
    """Task status enumeration matching the database CHECK constraint."""
    
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DELETED = "deleted"
    DEFERRED = "deferred"


@dataclass
class Task:
    """Task data model matching the database schema.
    
    Attributes:
        id: Database primary key (auto-generated)
        uuid: Unique identifier for external references
        revision: Optimistic concurrency control version number
        title: Task title (required, max 500 chars)
        description: Optional markdown-formatted description
        recurrence_rrule: RFC 5545 recurrence rule (e.g., "FREQ=WEEKLY;BYDAY=MO")
        recurrence_start_utc: Start date for recurrence calculation
        next_due_utc: Next due date/time in ISO 8601 UTC format
        status: Current task status (pending, in_progress, completed, deleted, deferred)
        priority: Task priority (1-4, lower is higher priority):
            - 1: Urgent (highest priority)
            - 2: High
            - 3: Medium  
            - 4: Low (lowest priority)
            - None: No priority set
        created_at: Creation timestamp (UTC, auto-set)
        updated_at: Last modification timestamp (UTC, auto-updated)
        deleted_at: Soft deletion timestamp (None if not deleted)
    """
    
    id: Optional[int] = None
    uuid: str = ""
    revision: int = 0
    title: str = ""
    description: Optional[str] = None
    recurrence_rrule: Optional[str] = None
    recurrence_start_utc: Optional[str] = None
    next_due_utc: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    priority: Optional[int] = None  # 1=Urgent, 2=High, 3=Medium, 4=Low (lower number = higher priority)
    created_at: str = ""
    updated_at: str = ""
    deleted_at: Optional[str] = None
    
    def __post_init__(self) -> None:
        """Generate UUID if not provided."""
        if not self.uuid:
            self.uuid = str(uuid.uuid4())
        
        # Set timestamps if not provided
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now


@dataclass
class TaskClosure:
    """Task closure table entry for hierarchical relationships."""
    
    ancestor_id: int
    descendant_id: int
    depth: int
    sort_order: int = 0


@dataclass
class Blob:
    """File blob metadata for attachments."""
    
    sha256: str
    size_bytes: int
    created_at: str = ""
    
    def __post_init__(self) -> None:
        """Set timestamp if not provided."""
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Attachment:
    """Task attachment linking to a blob."""
    
    id: Optional[int] = None
    uuid: str = ""
    task_id: int = 0
    blob_sha256: str = ""
    original_filename: str = ""
    created_at: str = ""
    
    def __post_init__(self) -> None:
        """Generate UUID and set timestamp if not provided."""
        if not self.uuid:
            self.uuid = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class UndoLogStatus(str, Enum):
    """Undo log status enumeration for crash-safety tracking."""
    
    PENDING = "PENDING"
    APPLIED = "APPLIED"


@dataclass
class UndoLogEntry:
    """Undo/redo log entry with JSON-Patch payload."""
    
    id: Optional[int] = None
    command_payload: str = ""  # JSON-Patch operation
    applied_at: str = ""
    status: UndoLogStatus = UndoLogStatus.APPLIED
    
    def __post_init__(self) -> None:
        """Set timestamp if not provided."""
        if not self.applied_at:
            self.applied_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") 