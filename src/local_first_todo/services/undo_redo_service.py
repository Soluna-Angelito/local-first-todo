"""Undo/Redo service for Local-First To-Do application.

This module implements the persistent, crash-safe, and concurrency-aware undo/redo functionality
using JSON-Patch (RFC 6902) operations as specified in the SDD.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from local_first_todo.database.manager import DatabaseManager
from local_first_todo.database.models import Task, TaskStatus, UndoLogEntry, UndoLogStatus

logger = logging.getLogger(__name__)


class UndoRedoError(Exception):
    """Base exception for undo/redo operations."""
    pass


class UndoStackEmptyError(UndoRedoError):
    """Raised when trying to undo with an empty undo stack."""
    pass


class RedoStackEmptyError(UndoRedoError):
    """Raised when trying to redo with an empty redo stack."""
    pass


class UndoRedoService:
    """Service for managing persistent undo/redo operations using JSON-Patch."""
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        max_undo_entries: int = 1000,
        max_undo_size_mb: int = 50
    ):
        """Initialize the undo/redo service.
        
        Args:
            db_manager: Database manager instance
            max_undo_entries: Maximum number of undo entries to retain
            max_undo_size_mb: Maximum size of undo log in MB
        """
        self.db_manager = db_manager
        self.max_undo_entries = max_undo_entries
        self.max_undo_size_mb = max_undo_size_mb
        self._current_position = 0  # Current position in undo stack
    
    async def initialize(self) -> None:
        """Initialize the service and clean up any pending operations from crashes."""
        await self._cleanup_pending_operations()
        await self._update_current_position()
    
    async def record_task_operation(
        self,
        operation_type: str,
        task_before: Optional[Union[Task, List[Dict[str, Any]]]],
        task_after: Optional[Union[Task, List[Dict[str, Any]]]],
        hierarchy_info_before: Optional[Dict[str, Any]] = None,
        hierarchy_info_after: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record a task operation for undo/redo.
        
        Args:
            operation_type: Type of operation ('create', 'update', 'delete', 'restore', 'reorder')
            task_before: Task state before the operation (None for create, list for reorder)
            task_after: Task state after the operation (None for delete, list for reorder)
            hierarchy_info_before: Optional dict with 'parent_id' and 'sort_order' before operation
            hierarchy_info_after: Optional dict with 'parent_id' and 'sort_order' after operation
        
        Note: For 'move' operations, use record_move_operation() instead.
        """
        # Generate JSON-Patch for the operation
        patch_operations = self._generate_task_patch(
            operation_type, task_before, task_after,
            hierarchy_info_before, hierarchy_info_after
        )
        
        if not patch_operations:
            return  # No meaningful changes to record
        
        # Create undo log entry
        undo_entry = UndoLogEntry(
            command_payload=json.dumps(patch_operations),
            status=UndoLogStatus.APPLIED
        )
        
        # Clear any redo entries (when we record a new operation, redo history is invalidated)
        await self._clear_redo_entries()
        
        # Store the undo operation
        await self._store_undo_entry(undo_entry)
        
        # Truncate log if needed
        await self._truncate_log_if_needed()
        
        # Update current position
        await self._update_current_position()
        
        # Log with appropriate context
        if operation_type == "reorder":
            logger.debug(f"Recorded {operation_type} operation for task ordering")
        elif task_after and hasattr(task_after, 'id'):
            logger.debug(f"Recorded {operation_type} operation for task {task_after.id}")
        elif task_before and hasattr(task_before, 'id'):
            logger.debug(f"Recorded {operation_type} operation for task {task_before.id}")
        else:
            logger.debug(f"Recorded {operation_type} operation")
    
    async def record_move_operation(
        self,
        task_id: int,
        parent_info_before: Optional[Dict[str, Any]],
        parent_info_after: Optional[Dict[str, Any]]
    ) -> None:
        """Record a move operation with hierarchy info for proper undo.
        
        Args:
            task_id: ID of the moved task
            parent_info_before: Dict with 'parent_id' and 'sort_order' before move
            parent_info_after: Dict with 'parent_id' and 'sort_order' after move
        """
        patch_operations = [{
            "op": "move",
            "path": f"/tasks/{task_id}/hierarchy",
            "value": parent_info_after,
            "previous_value": parent_info_before
        }]
        
        undo_entry = UndoLogEntry(
            command_payload=json.dumps(patch_operations),
            status=UndoLogStatus.APPLIED
        )
        
        await self._clear_redo_entries()
        await self._store_undo_entry(undo_entry)
        await self._truncate_log_if_needed()
        await self._update_current_position()
        
        logger.debug(f"Recorded move operation for task {task_id}")
    
    async def undo(self) -> Dict[str, Any]:
        """Perform an undo operation.
        
        Returns:
            Dictionary describing what was undone
            
        Raises:
            UndoStackEmptyError: If there are no operations to undo
        """
        # Get the latest undo entry
        undo_entry = await self._get_latest_undo_entry()
        if not undo_entry:
            raise UndoStackEmptyError("No operations available to undo")
        
        # Parse the JSON-Patch operations
        patch_operations = json.loads(undo_entry.command_payload)
        
        # Generate reverse patch operations
        reverse_operations = self._reverse_patch_operations(patch_operations)
        
        # Apply the reverse operations
        applied_operations = await self._apply_patch_operations(reverse_operations)
        
        # Move the undo entry to mark it as undone (conceptually moving to redo stack)
        await self._mark_entry_as_undone(undo_entry.id)
        
        # Update current position
        self._current_position -= 1
        
        logger.info(f"Undid operation: {undo_entry.id}")
        
        return {
            "operation": "undo",
            "entry_id": undo_entry.id,
            "operations_applied": applied_operations
        }
    
    async def redo(self) -> Dict[str, Any]:
        """Perform a redo operation.
        
        Returns:
            Dictionary describing what was redone
            
        Raises:
            RedoStackEmptyError: If there are no operations to redo
        """
        # Get the next redo entry
        redo_entry = await self._get_next_redo_entry()
        if not redo_entry:
            raise RedoStackEmptyError("No operations available to redo")
        
        # Parse the JSON-Patch operations
        patch_operations = json.loads(redo_entry.command_payload)
        
        # Apply the original operations
        applied_operations = await self._apply_patch_operations(patch_operations)
        
        # Mark the entry as applied again
        await self._mark_entry_as_applied(redo_entry.id)
        
        # Update current position
        self._current_position += 1
        
        logger.info(f"Redid operation: {redo_entry.id}")
        
        return {
            "operation": "redo",
            "entry_id": redo_entry.id,
            "operations_applied": applied_operations
        }
    
    async def get_undo_status(self) -> Dict[str, Any]:
        """Get the current undo/redo status.
        
        Returns:
            Dictionary with undo/redo availability and statistics
        """
        # Count available undo/redo operations
        can_undo = await self._can_undo()
        can_redo = await self._can_redo()
        
        # Get total undo log statistics
        stats = await self._get_undo_log_stats()
        
        return {
            "can_undo": can_undo,
            "can_redo": can_redo,
            "current_position": self._current_position,
            "total_entries": stats["total_entries"],
            "total_size_bytes": stats["total_size_bytes"],
            "max_entries": self.max_undo_entries,
            "max_size_mb": self.max_undo_size_mb
        }
    
    def _generate_task_patch(
        self,
        operation_type: str,
        task_before: Optional[Union[Task, List[Dict[str, Any]]]],
        task_after: Optional[Union[Task, List[Dict[str, Any]]]],
        hierarchy_info_before: Optional[Dict[str, Any]] = None,
        hierarchy_info_after: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Generate JSON-Patch operations for a task change.
        
        Args:
            operation_type: Type of operation
            task_before: Task before the change
            task_after: Task after the change
            hierarchy_info_before: Optional hierarchy info before operation
            hierarchy_info_after: Optional hierarchy info after operation
            
        Returns:
            List of JSON-Patch operations
        """
        operations = []
        
        if operation_type == "create" and task_after:
            # For create operations, we need to be able to delete the task on undo
            # Include hierarchy info so we can restore the task in the correct location
            operations.append({
                "op": "add",
                "path": f"/tasks/{task_after.id}",
                "value": self._task_to_dict(task_after, hierarchy_info_after)
            })
        
        elif operation_type == "update" and task_before and task_after:
            # For updates, we record the specific field changes
            before_dict = self._task_to_dict(task_before)
            after_dict = self._task_to_dict(task_after)
            
            for field, after_value in after_dict.items():
                if field == "_hierarchy":
                    continue  # Skip hierarchy in field-level updates
                before_value = before_dict.get(field)
                if before_value != after_value:
                    operations.append({
                        "op": "replace",
                        "path": f"/tasks/{task_after.id}/{field}",
                        "value": after_value,
                        "previous_value": before_value  # Custom field for easier reversal
                    })
        
        elif operation_type == "delete" and task_before:
            # For delete operations, we need to be able to restore the task on undo
            # Include hierarchy info so task is restored in the correct location
            operations.append({
                "op": "remove",
                "path": f"/tasks/{task_before.id}",
                "previous_value": self._task_to_dict(task_before, hierarchy_info_before)
            })
        
        elif operation_type == "restore" and task_before and task_after:
            # For restore operations, record the state change with hierarchy
            operations.append({
                "op": "restore",
                "path": f"/tasks/{task_after.id}",
                "value": self._task_to_dict(task_after, hierarchy_info_after),
                "previous_value": self._task_to_dict(task_before, hierarchy_info_before)
            })
        
        elif operation_type == "move" and task_before and task_after:
            # For move operations, we primarily care about hierarchy changes
            # This is a simplified approach - full implementation would track closure table changes
            operations.append({
                "op": "move",
                "path": f"/tasks/{task_after.id}",
                "value": self._task_to_dict(task_after, hierarchy_info_after),
                "previous_value": self._task_to_dict(task_before, hierarchy_info_before)
            })
        
        elif operation_type == "reorder":
            # For reordering operations, task_before and task_after contain ordering state
            # Both are dicts with 'parent_id' and 'order' (list of {'id': task_id, 'sort_order': order})
            if isinstance(task_before, dict) and isinstance(task_after, dict):
                operations.append({
                    "op": "reorder",
                    "path": "/task_order",
                    "value": task_after,  # New ordering with parent_id
                    "previous_value": task_before  # Old ordering with parent_id
                })
        
        return operations
    
    def _reverse_patch_operations(self, operations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate reverse operations for a list of JSON-Patch operations.
        
        Args:
            operations: Original JSON-Patch operations
            
        Returns:
            Reversed JSON-Patch operations
        """
        reversed_ops = []
        
        # Process operations in reverse order
        for op in reversed(operations):
            if op["op"] == "add":
                # Reverse of add is remove
                reversed_ops.append({
                    "op": "remove",
                    "path": op["path"]
                })
            
            elif op["op"] == "remove":
                # Reverse of remove is add with the previous value
                reversed_ops.append({
                    "op": "add",
                    "path": op["path"],
                    "value": op["previous_value"]
                })
            
            elif op["op"] == "replace":
                # Reverse of replace is replace with the previous value
                reversed_ops.append({
                    "op": "replace",
                    "path": op["path"],
                    "value": op["previous_value"],
                    "previous_value": op["value"]
                })
            
            elif op["op"] == "restore":
                # Reverse of restore is soft_delete (return to deleted state, not permanent deletion)
                # We need to preserve the previous_value so we can restore the deleted_at timestamp
                reversed_ops.append({
                    "op": "soft_delete",
                    "path": op["path"],
                    "previous_value": op.get("previous_value")  # Contains the deleted state
                })
            
            elif op["op"] == "move":
                # Reverse of move is move back to previous location
                reversed_ops.append({
                    "op": "move",
                    "path": op["path"],
                    "value": op["previous_value"],  # Swap value and previous
                    "previous_value": op["value"]
                })
            
            elif op["op"] == "reorder":
                # Reverse of reorder is reorder back to previous order
                reversed_ops.append({
                    "op": "reorder",
                    "path": op["path"],
                    "value": op["previous_value"],  # Swap value and previous
                    "previous_value": op["value"]
                })
        
        return reversed_ops
    
    async def _apply_patch_operations(self, operations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply a list of JSON-Patch operations to the database.
        
        Args:
            operations: JSON-Patch operations to apply
            
        Returns:
            List of successfully applied operations
        """
        applied_operations = []
        
        for op in operations:
            try:
                path_parts = op["path"].strip("/").split("/")
                
                # Handle reorder operations (path format: /task_order)
                if op["op"] == "reorder" and path_parts[0] == "task_order":
                    await self._reorder_tasks(op["value"], op.get("previous_value"))
                    applied_operations.append(op)
                    continue
                
                # Handle task operations (path format: /tasks/{id} or /tasks/{id}/{field})
                if len(path_parts) < 2 or path_parts[0] != "tasks":
                    continue
                
                task_id = int(path_parts[1])
                
                if op["op"] == "add":
                    # Create or restore a task
                    task_data = op["value"]
                    await self._restore_task_from_dict(task_id, task_data)
                    applied_operations.append(op)
                
                elif op["op"] == "remove" or op["op"] == "delete":
                    # Hard delete a task (used for undoing create operations)
                    await self._delete_task_for_undo(task_id)
                    applied_operations.append(op)
                
                elif op["op"] == "soft_delete":
                    # Soft delete a task (used for undoing restore operations)
                    # This returns the task to its deleted state instead of permanently removing it
                    previous_value = op.get("previous_value", {})
                    await self._soft_delete_task_for_undo(task_id, previous_value)
                    applied_operations.append(op)
                
                elif op["op"] == "replace":
                    # Update a task field
                    if len(path_parts) >= 3:
                        field_name = path_parts[2]
                        await self._update_task_field(task_id, field_name, op["value"])
                        applied_operations.append(op)
                
                elif op["op"] == "restore":
                    # Restore a deleted task
                    task_data = op["value"]
                    await self._restore_task_from_dict(task_id, task_data)
                    applied_operations.append(op)
                
                elif op["op"] == "move":
                    # Move a task to new parent/position using hierarchy info
                    hierarchy_info = op["value"]
                    await self._move_task_to_hierarchy(task_id, hierarchy_info)
                    applied_operations.append(op)
            
            except Exception as e:
                logger.error(f"Failed to apply patch operation {op}: {e}")
                # Continue with other operations even if one fails
        
        return applied_operations
    
    def _task_to_dict(self, task: Task, hierarchy_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Convert a Task object to a dictionary for JSON serialization.
        
        Args:
            task: Task object to convert
            hierarchy_info: Optional dict with 'parent_id' and 'sort_order' for hierarchy preservation
        """
        result = {
            "id": task.id,
            "uuid": task.uuid,
            "revision": task.revision,
            "title": task.title,
            "description": task.description,
            "recurrence_rrule": task.recurrence_rrule,
            "recurrence_start_utc": task.recurrence_start_utc,
            "next_due_utc": task.next_due_utc,
            "status": task.status.value,
            "priority": task.priority,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "deleted_at": task.deleted_at
        }
        # Include hierarchy info if provided (for proper undo restoration)
        if hierarchy_info is not None:
            result["_hierarchy"] = hierarchy_info
        return result
    
    async def _store_undo_entry(self, entry: UndoLogEntry) -> int:
        """Store an undo log entry in the database."""
        cursor = await self.db_manager.execute_write(
            """
            INSERT INTO UndoLog (command_payload, applied_at, status)
            VALUES (?, ?, ?)
            """,
            (entry.command_payload, entry.applied_at, entry.status.value)
        )
        return cursor.lastrowid
    
    async def _get_latest_undo_entry(self) -> Optional[UndoLogEntry]:
        """Get the latest undoable entry."""
        rows = await self.db_manager.execute_read(
            """
            SELECT * FROM UndoLog 
            WHERE status = 'APPLIED'
            ORDER BY id DESC 
            LIMIT 1
            """
        )
        
        if not rows:
            return None
        
        row = rows[0]
        return UndoLogEntry(
            id=row["id"],
            command_payload=row["command_payload"],
            applied_at=row["applied_at"],
            status=UndoLogStatus(row["status"])
        )
    
    async def _get_next_redo_entry(self) -> Optional[UndoLogEntry]:
        """Get the next redoable entry."""
        rows = await self.db_manager.execute_read(
            """
            SELECT * FROM UndoLog 
            WHERE status = 'PENDING'
            ORDER BY id ASC 
            LIMIT 1
            """
        )
        
        if not rows:
            return None
        
        row = rows[0]
        return UndoLogEntry(
            id=row["id"],
            command_payload=row["command_payload"],
            applied_at=row["applied_at"],
            status=UndoLogStatus(row["status"])
        )
    
    async def _mark_entry_as_undone(self, entry_id: int) -> None:
        """Mark an entry as undone (moves it to redo stack conceptually)."""
        await self.db_manager.execute_write(
            "UPDATE UndoLog SET status = 'PENDING' WHERE id = ?",
            (entry_id,)
        )
    
    async def _mark_entry_as_applied(self, entry_id: int) -> None:
        """Mark an entry as applied (moves it back to undo stack)."""
        await self.db_manager.execute_write(
            "UPDATE UndoLog SET status = 'APPLIED' WHERE id = ?",
            (entry_id,)
        )
    
    async def _clear_redo_entries(self) -> None:
        """Clear all redo entries (PENDING status entries)."""
        await self.db_manager.execute_write(
            "DELETE FROM UndoLog WHERE status = 'PENDING'"
        )
    
    async def _can_undo(self) -> bool:
        """Check if undo is available."""
        rows = await self.db_manager.execute_read(
            "SELECT COUNT(*) as count FROM UndoLog WHERE status = 'APPLIED'"
        )
        return rows[0]["count"] > 0
    
    async def _can_redo(self) -> bool:
        """Check if redo is available."""
        rows = await self.db_manager.execute_read(
            "SELECT COUNT(*) as count FROM UndoLog WHERE status = 'PENDING'"
        )
        return rows[0]["count"] > 0
    
    async def _get_undo_log_stats(self) -> Dict[str, Any]:
        """Get statistics about the undo log."""
        rows = await self.db_manager.execute_read(
            """
            SELECT 
                COUNT(*) as total_entries,
                SUM(LENGTH(command_payload)) as total_size_bytes
            FROM UndoLog
            """
        )
        
        if not rows:
            return {"total_entries": 0, "total_size_bytes": 0}
        
        row = rows[0]
        return {
            "total_entries": row["total_entries"],
            "total_size_bytes": row["total_size_bytes"] or 0
        }
    
    async def _truncate_log_if_needed(self) -> None:
        """Truncate the undo log if it exceeds configured limits."""
        stats = await self._get_undo_log_stats()
        
        # Check entry count limit
        if stats["total_entries"] > self.max_undo_entries:
            entries_to_remove = stats["total_entries"] - self.max_undo_entries
            await self.db_manager.execute_write(
                """
                DELETE FROM UndoLog 
                WHERE id IN (
                    SELECT id FROM UndoLog 
                    ORDER BY id ASC 
                    LIMIT ?
                )
                """,
                (entries_to_remove,)
            )
            logger.info(f"Truncated {entries_to_remove} old undo log entries")
        
        # Check size limit
        max_size_bytes = self.max_undo_size_mb * 1024 * 1024
        if stats["total_size_bytes"] > max_size_bytes:
            # Remove oldest entries until under limit
            # Use MAX(1, COUNT(*) / 4) to ensure at least 1 entry is deleted
            # This prevents infinite loops when there are very few but large entries
            await self.db_manager.execute_write(
                """
                DELETE FROM UndoLog 
                WHERE id IN (
                    SELECT id FROM UndoLog 
                    ORDER BY id ASC 
                    LIMIT (
                        SELECT MAX(1, COUNT(*) / 4) FROM UndoLog
                    )
                )
                """
            )
            logger.info("Truncated undo log due to size limit")
    
    async def _cleanup_pending_operations(self) -> None:
        """Clean up any PENDING operations from crashes."""
        # According to SDD, PENDING entries from crashes should be discarded
        await self.db_manager.execute_write(
            "DELETE FROM UndoLog WHERE status = 'PENDING'"
        )
        logger.info("Cleaned up pending undo operations from potential crash")
    
    async def _update_current_position(self) -> None:
        """Update the current position in the undo stack."""
        rows = await self.db_manager.execute_read(
            "SELECT COUNT(*) as count FROM UndoLog WHERE status = 'APPLIED'"
        )
        self._current_position = rows[0]["count"] if rows else 0
    
    async def _restore_task_from_dict(self, task_id: int, task_data: Dict[str, Any]) -> None:
        """Restore a task from dictionary data, including hierarchy if available."""
        # Restore the task row
        await self.db_manager.execute_write(
            """
            INSERT OR REPLACE INTO Task (
                id, uuid, revision, title, description, recurrence_rrule,
                recurrence_start_utc, next_due_utc, status, priority,
                created_at, updated_at, deleted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_data["id"], task_data["uuid"], task_data["revision"],
                task_data["title"], task_data["description"], task_data["recurrence_rrule"],
                task_data["recurrence_start_utc"], task_data["next_due_utc"],
                task_data["status"], task_data["priority"],
                task_data["created_at"], task_data["updated_at"], task_data["deleted_at"]
            )
        )
        
        # Restore hierarchy if provided
        hierarchy_info = task_data.get("_hierarchy")
        if hierarchy_info is not None:
            await self._restore_task_hierarchy(task_id, hierarchy_info)
        else:
            # If no hierarchy info, ensure self-reference exists (for root tasks)
            await self._ensure_task_has_closure_entry(task_id)
    
    async def _ensure_task_has_closure_entry(self, task_id: int) -> None:
        """Ensure a task has at least a self-reference in the closure table."""
        rows = await self.db_manager.execute_read(
            "SELECT 1 FROM TaskClosure WHERE ancestor_id = ? AND descendant_id = ? AND depth = 0",
            (task_id, task_id)
        )
        if not rows:
            # Add self-reference for root-level task
            rows = await self.db_manager.execute_read(
                """
                SELECT COALESCE(MAX(tc.sort_order), 0) + 1 as next_sort_order
                FROM TaskClosure tc
                WHERE tc.depth = 0 AND tc.ancestor_id = tc.descendant_id
                AND NOT EXISTS (
                    SELECT 1 FROM TaskClosure tc2 
                    WHERE tc2.descendant_id = tc.descendant_id AND tc2.depth = 1
                )
                """
            )
            next_sort_order = rows[0]["next_sort_order"] if rows else 1
            await self.db_manager.execute_write(
                "INSERT INTO TaskClosure (ancestor_id, descendant_id, depth, sort_order) VALUES (?, ?, 0, ?)",
                (task_id, task_id, next_sort_order)
            )
    
    async def _restore_task_hierarchy(self, task_id: int, hierarchy_info: Dict[str, Any]) -> None:
        """Restore a task's hierarchy based on stored hierarchy info.
        
        Args:
            task_id: Task ID to restore hierarchy for
            hierarchy_info: Dict with 'parent_id' (int or None) and 'sort_order' (int)
        """
        parent_id = hierarchy_info.get('parent_id')
        target_sort_order = hierarchy_info.get('sort_order', 0)
        
        # First remove any existing hierarchy entries for this task
        await self.db_manager.execute_write(
            "DELETE FROM TaskClosure WHERE descendant_id = ?",
            (task_id,)
        )
        
        # Add self-reference
        await self.db_manager.execute_write(
            "INSERT INTO TaskClosure (ancestor_id, descendant_id, depth, sort_order) VALUES (?, ?, 0, ?)",
            (task_id, task_id, 0 if parent_id else target_sort_order)
        )
        
        if parent_id is not None:
            # Add hierarchy relationships to parent and all its ancestors
            await self.db_manager.execute_write(
                """
                INSERT INTO TaskClosure (ancestor_id, descendant_id, depth, sort_order)
                SELECT ancestor_id, ?, depth + 1, CASE WHEN depth = 0 THEN ? ELSE 0 END
                FROM TaskClosure
                WHERE descendant_id = ?
                """,
                (task_id, target_sort_order, parent_id)
            )
        
        logger.debug(f"Restored hierarchy for task {task_id}: parent={parent_id}, sort_order={target_sort_order}")
    
    async def _delete_task_for_undo(self, task_id: int) -> None:
        """Hard delete a task for undo purposes (used when undoing create)."""
        await self.db_manager.execute_write(
            "DELETE FROM Task WHERE id = ?",
            (task_id,)
        )
    
    async def _soft_delete_task_for_undo(self, task_id: int, previous_value: Dict[str, Any]) -> None:
        """Soft delete a task for undo purposes (used when undoing restore).
        
        This restores the task to its previous deleted state instead of permanently
        removing it, which preserves attachments and allows the restore to be redone.
        """
        # Get the deleted_at and status from previous state, or use current time
        deleted_at = previous_value.get("deleted_at")
        if not deleted_at:
            deleted_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        await self.db_manager.execute_write(
            """
            UPDATE Task 
            SET deleted_at = ?, status = 'deleted', updated_at = ?, revision = revision + 1
            WHERE id = ?
            """,
            (deleted_at, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), task_id)
        )
        logger.debug(f"Soft deleted task {task_id} for undo (restored to deleted state)")
    
    async def _update_task_field(self, task_id: int, field_name: str, value: Any) -> None:
        """Update a specific field of a task."""
        # Map field names to database columns
        field_mapping = {
            "title": "title",
            "description": "description",
            "status": "status",
            "priority": "priority",
            "next_due_utc": "next_due_utc",
            "recurrence_rrule": "recurrence_rrule",
            "recurrence_start_utc": "recurrence_start_utc",
            "deleted_at": "deleted_at"
        }
        
        if field_name not in field_mapping:
            logger.warning(f"Cannot update unknown field: {field_name}")
            return
        
        db_field = field_mapping[field_name]
        
        # Update revision and timestamp
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        await self.db_manager.execute_write(
            f"""
            UPDATE Task 
            SET {db_field} = ?, updated_at = ?, revision = revision + 1
            WHERE id = ?
            """,
            (value, now, task_id)
        )
    
    async def _move_task_to_hierarchy(self, task_id: int, hierarchy_info: Optional[Dict[str, Any]]) -> None:
        """Move a task to a specific parent and position in the hierarchy.
        
        This method properly handles descendants by:
        1. Getting all descendants before modifying anything
        2. Removing external ancestor relationships (preserving internal subtree relationships)
        3. Adding the task and descendants to the new location
        
        Args:
            task_id: ID of the task to move
            hierarchy_info: Dict with 'parent_id' (int or None) and 'sort_order' (int)
        """
        if hierarchy_info is None:
            logger.warning(f"No hierarchy info provided for moving task {task_id}")
            return
        
        parent_id = hierarchy_info.get('parent_id')
        target_sort_order = hierarchy_info.get('sort_order', 0)
        
        # STEP 1: Get all descendants BEFORE modifying the closure table
        descendant_rows = await self.db_manager.execute_read(
            "SELECT descendant_id, depth FROM TaskClosure WHERE ancestor_id = ? AND depth > 0",
            (task_id,)
        )
        descendants = [(row["descendant_id"], row["depth"]) for row in descendant_rows]
        descendant_ids = [d[0] for d in descendants]
        
        # The subtree includes the task and all its descendants
        subtree_ids = [task_id] + descendant_ids
        
        # STEP 2: Remove the task from old ancestors (except self-reference)
        await self.db_manager.execute_write(
            "DELETE FROM TaskClosure WHERE descendant_id = ? AND depth > 0",
            (task_id,)
        )
        
        # STEP 3: Remove descendants from old ancestors (external to subtree only)
        # We preserve internal relationships (e.g., task_id -> descendants)
        if descendant_ids:
            descendant_placeholders = ",".join("?" * len(descendant_ids))
            subtree_placeholders = ",".join("?" * len(subtree_ids))
            await self.db_manager.execute_write(
                f"""
                DELETE FROM TaskClosure 
                WHERE descendant_id IN ({descendant_placeholders})
                AND ancestor_id NOT IN ({subtree_placeholders})
                AND depth > 0
                """,
                tuple(descendant_ids) + tuple(subtree_ids)
            )
        
        # STEP 4: Add task to new parent (if not moving to root)
        if parent_id is not None:
            # Add relationship to new parent and all its ancestors
            await self.db_manager.execute_write(
                """
                INSERT INTO TaskClosure (ancestor_id, descendant_id, depth, sort_order)
                SELECT ancestor_id, ?, depth + 1, CASE WHEN depth = 0 THEN ? ELSE 0 END
                FROM TaskClosure
                WHERE descendant_id = ?
                """,
                (task_id, target_sort_order, parent_id)
            )
            
            # STEP 5: Re-add descendants to the new ancestor chain
            for desc_id, desc_depth_from_task in descendants:
                # Add relationships from task_id's NEW ancestors to this descendant
                await self.db_manager.execute_write(
                    """
                    INSERT OR IGNORE INTO TaskClosure (ancestor_id, descendant_id, depth, sort_order)
                    SELECT tc.ancestor_id, ?, tc.depth + ?, 0
                    FROM TaskClosure tc
                    WHERE tc.descendant_id = ? AND tc.depth > 0
                    """,
                    (desc_id, desc_depth_from_task, task_id)
                )
        else:
            # Task becomes a root task - update self-reference sort_order
            await self.db_manager.execute_write(
                """
                UPDATE TaskClosure SET sort_order = ?
                WHERE ancestor_id = ? AND descendant_id = ? AND depth = 0
                """,
                (target_sort_order, task_id, task_id)
            )
        
        logger.debug(f"Moved task {task_id} (with {len(descendants)} descendants) to parent {parent_id} with sort_order {target_sort_order}")
    
    async def _reorder_tasks(self, order_state: Dict[str, Any], old_order_state: Optional[Dict[str, Any]] = None) -> None:
        """Reorder tasks as part of undo/redo operation.
        
        Args:
            order_state: Dict with 'parent_id' and 'order' (list of {'id': task_id, 'sort_order': order})
            old_order_state: Previous ordering (unused, for logging context)
        """
        parent_id = order_state.get('parent_id')
        order_list = order_state.get('order', [])
        
        operations = []
        
        for order_item in order_list:
            task_id = order_item['id']
            sort_order = order_item['sort_order']
            
            if parent_id is not None:
                # Update sort_order for the specific parent-child relationship
                operations.append((
                    """
                    UPDATE TaskClosure 
                    SET sort_order = ? 
                    WHERE ancestor_id = ? AND descendant_id = ? AND depth = 1
                    """,
                    (sort_order, parent_id, task_id)
                ))
            else:
                # Root-level tasks: update self-reference sort_order
                operations.append((
                    """
                    UPDATE TaskClosure 
                    SET sort_order = ? 
                    WHERE ancestor_id = ? AND descendant_id = ? AND depth = 0
                    """,
                    (sort_order, task_id, task_id)
                ))
        
        await self.db_manager.execute_transaction(operations)
        logger.debug(f"Reordered {len(order_list)} tasks under parent {parent_id}") 