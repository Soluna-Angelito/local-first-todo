"""Dependency injection for Local-First To-Do application."""

import asyncio
from typing import Optional

from local_first_todo.database.manager import DatabaseManager
from local_first_todo.database.crud import TaskRepository
from local_first_todo.services.undo_redo_service import UndoRedoService
from local_first_todo.services.search_service import SearchService
from local_first_todo.services.attachment_service import AttachmentService

# Global instances
_db_manager: Optional[DatabaseManager] = None
_task_repository: Optional[TaskRepository] = None
_db_write_lock: Optional[asyncio.Lock] = None
_undo_redo_service: Optional[UndoRedoService] = None
_search_service: Optional[SearchService] = None
_attachment_service: Optional[AttachmentService] = None


def set_database_manager(db_manager: DatabaseManager) -> None:
    """Set the global database manager instance."""
    global _db_manager
    _db_manager = db_manager


def set_task_repository(task_repository: TaskRepository) -> None:
    """Set the global task repository instance."""
    global _task_repository
    _task_repository = task_repository


def set_db_write_lock(lock: asyncio.Lock) -> None:
    """Set the global database write lock."""
    global _db_write_lock
    _db_write_lock = lock


def set_undo_redo_service(undo_redo_service: UndoRedoService) -> None:
    """Set the global undo/redo service instance."""
    global _undo_redo_service
    _undo_redo_service = undo_redo_service


def set_search_service(search_service: SearchService) -> None:
    """Set the global search service instance."""
    global _search_service
    _search_service = search_service


def set_attachment_service(attachment_service: AttachmentService) -> None:
    """Set the global attachment service instance."""
    global _attachment_service
    _attachment_service = attachment_service


def get_database_manager() -> DatabaseManager:
    """Get the database manager instance."""
    if _db_manager is None:
        raise RuntimeError("Database manager not initialized")
    return _db_manager


def get_task_repository() -> TaskRepository:
    """Get the task repository instance."""
    if _task_repository is None:
        raise RuntimeError("Task repository not initialized")
    return _task_repository


def get_db_write_lock() -> asyncio.Lock:
    """Get the database write lock."""
    if _db_write_lock is None:
        raise RuntimeError("Database write lock not initialized")
    return _db_write_lock


def get_undo_redo_service() -> UndoRedoService:
    """Get the undo/redo service instance."""
    if _undo_redo_service is None:
        raise RuntimeError("Undo/redo service not initialized")
    return _undo_redo_service


def get_search_service() -> SearchService:
    """Get the search service instance."""
    if _search_service is None:
        raise RuntimeError("Search service not initialized")
    return _search_service


def get_attachment_service() -> AttachmentService:
    """Get the attachment service instance."""
    if _attachment_service is None:
        raise RuntimeError("Attachment service not initialized")
    return _attachment_service 