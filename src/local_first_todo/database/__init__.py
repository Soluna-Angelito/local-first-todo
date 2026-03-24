"""Database package for Local-First To-Do application.

This package contains all database-related functionality including:
- Database schema and migrations
- Connection management
- CRUD operations
- FTS5 full-text search
- Closure table operations for hierarchical tasks
"""

from local_first_todo.database.manager import DatabaseManager
from local_first_todo.database.models import TaskStatus, UndoLogEntry, UndoLogStatus
from local_first_todo.database.crud import TaskRepository

__all__ = ["DatabaseManager", "TaskStatus", "UndoLogEntry", "UndoLogStatus", "TaskRepository"] 