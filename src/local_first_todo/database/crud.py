"""CRUD operations for Local-First To-Do application.

This module provides create, read, update, and delete operations for tasks,
as well as hierarchical operations using the closure table.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

import aiosqlite

from local_first_todo.database.manager import DatabaseManager
from local_first_todo.database.models import Task, TaskStatus, TaskClosure

logger = logging.getLogger(__name__)


class TaskRepository:
    """Repository for task CRUD operations."""
    
    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize the task repository.
        
        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager
    
    async def create_task(self, task: Task, parent_id: Optional[int] = None) -> int:
        """Create a new task and optionally attach it to a parent.
        
        Args:
            task: Task to create
            parent_id: Optional parent task ID for hierarchical structure
            
        Returns:
            The ID of the created task
        """
        # Update timestamp
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        task.updated_at = now
        if not task.created_at:
            task.created_at = now
        
        operations = []
        
        # Insert the task
        task_insert = (
            """
            INSERT INTO Task (
                uuid, revision, title, description, recurrence_rrule,
                recurrence_start_utc, next_due_utc, status, priority,
                created_at, updated_at, deleted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.uuid, task.revision, task.title, task.description,
                task.recurrence_rrule, task.recurrence_start_utc, task.next_due_utc,
                task.status.value, task.priority, task.created_at, task.updated_at,
                task.deleted_at
            )
        )
        operations.append(task_insert)
        
        # Execute the operations
        await self.db_manager.execute_transaction(operations)
        
        # Get the created task ID
        rows = await self.db_manager.execute_read(
            "SELECT id FROM Task WHERE uuid = ?", (task.uuid,)
        )
        task_id = rows[0]["id"]
        task.id = task_id
        
        # Handle hierarchy if parent specified
        if parent_id is not None:
            await self._add_to_hierarchy(task_id, parent_id)
        else:
            # Add self-reference for root tasks
            await self._add_self_reference(task_id)
        
        logger.info(f"Created task {task_id} with UUID {task.uuid}")
        return task_id
    
    async def get_task_by_id(self, task_id: int) -> Optional[Task]:
        """Get a task by its ID.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task instance or None if not found
        """
        rows = await self.db_manager.execute_read(
            "SELECT * FROM Task WHERE id = ? AND deleted_at IS NULL", (task_id,)
        )
        
        if not rows:
            return None
        
        return self._row_to_task(rows[0])
    
    async def get_task_by_uuid(self, uuid: str) -> Optional[Task]:
        """Get a task by its UUID.
        
        Args:
            uuid: Task UUID
            
        Returns:
            Task instance or None if not found
        """
        rows = await self.db_manager.execute_read(
            "SELECT * FROM Task WHERE uuid = ? AND deleted_at IS NULL", (uuid,)
        )
        
        if not rows:
            return None
        
        return self._row_to_task(rows[0])
    
    async def get_all_tasks(self) -> List[Task]:
        """Get all active tasks (not soft-deleted).
        
        Returns:
            List of all active tasks
        """
        rows = await self.db_manager.execute_read(
            "SELECT * FROM Task WHERE deleted_at IS NULL ORDER BY created_at"
        )
        
        return [self._row_to_task(row) for row in rows]

    async def get_root_tasks(self, order_by_custom: bool = False) -> List[Task]:
        """Get root-level tasks (no parent).
        
        Args:
            order_by_custom: If True, order by TaskClosure.sort_order
        
        Returns:
            List of root tasks in the desired order
        """
        if order_by_custom:
            order_clause = "ORDER BY tc.sort_order, t.created_at"
        else:
            order_clause = "ORDER BY t.created_at"

        rows = await self.db_manager.execute_read(
            f"""
            SELECT t.* FROM Task t
            JOIN TaskClosure tc
                ON t.id = tc.descendant_id
                AND tc.depth = 0
                AND tc.ancestor_id = tc.descendant_id
            WHERE t.deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM TaskClosure tc2
                  WHERE tc2.descendant_id = t.id AND tc2.depth = 1
              )
            {order_clause}
            """
        )

        return [self._row_to_task(row) for row in rows]
    
    async def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """Get all tasks with a specific status.
        
        Args:
            status: Task status to filter by
            
        Returns:
            List of tasks with the specified status
        """
        rows = await self.db_manager.execute_read(
            "SELECT * FROM Task WHERE status = ? AND deleted_at IS NULL ORDER BY created_at",
            (status.value,)
        )
        
        return [self._row_to_task(row) for row in rows]
    
    async def update_task(self, task: Task) -> None:
        """Update an existing task.
        
        Args:
            task: Task with updated data (revision and updated_at should be set by caller)
        """
        await self.db_manager.execute_write(
            """
            UPDATE Task SET
                revision = ?, title = ?, description = ?, recurrence_rrule = ?,
                recurrence_start_utc = ?, next_due_utc = ?, status = ?, priority = ?,
                updated_at = ?, deleted_at = ?
            WHERE id = ?
            """,
            (
                task.revision, task.title, task.description, task.recurrence_rrule,
                task.recurrence_start_utc, task.next_due_utc, task.status.value,
                task.priority, task.updated_at, task.deleted_at, task.id
            )
        )
        
        logger.debug(f"Persisted task {task.id} (revision {task.revision})")
    
    async def soft_delete_task(self, task_id: int) -> None:
        """Soft delete a task by setting deleted_at timestamp.
        
        Args:
            task_id: ID of task to delete
        """
        # Get parent info before deletion for renormalization
        parent_info = await self.get_parent_info(task_id)
        parent_id = parent_info['parent_id'] if parent_info else None
        
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        await self.db_manager.execute_write(
            "UPDATE Task SET deleted_at = ?, status = ? WHERE id = ?",
            (now, TaskStatus.DELETED.value, task_id)
        )
        
        # Renormalize sort_order for siblings
        await self._renormalize_sort_order(parent_id, exclude_task_id=task_id)
        
        logger.info(f"Soft deleted task {task_id}")
    
    async def soft_delete_task_with_descendants(self, task_id: int) -> int:
        """Soft delete a task and all its descendants.
        
        Args:
            task_id: ID of task to delete
            
        Returns:
            Number of tasks deleted (including the task itself)
        """
        # Get parent info before deletion for renormalization
        parent_info = await self.get_parent_info(task_id)
        parent_id = parent_info['parent_id'] if parent_info else None
        
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Get all descendant IDs first (for counting)
        descendants = await self.get_descendants(task_id)
        all_task_ids = [task_id] + [d.id for d in descendants]
        
        # Delete all in one transaction
        operations = []
        for tid in all_task_ids:
            operations.append((
                "UPDATE Task SET deleted_at = ?, status = ? WHERE id = ?",
                (now, TaskStatus.DELETED.value, tid)
            ))
        
        await self.db_manager.execute_transaction(operations)
        
        # Renormalize sort_order for siblings of the deleted task
        await self._renormalize_sort_order(parent_id, exclude_task_id=task_id)
        
        logger.info(f"Soft deleted task {task_id} and {len(descendants)} descendants")
        return len(all_task_ids)
    
    async def update_task_status_with_descendants(self, task_id: int, status: TaskStatus) -> int:
        """Update status for a task and all its descendants.
        
        Args:
            task_id: ID of the parent task
            status: New status to set
            
        Returns:
            Number of tasks updated (including the task itself)
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Get all descendant IDs
        descendants = await self.get_descendants(task_id)
        all_task_ids = [task_id] + [d.id for d in descendants]
        
        # Update all in one transaction
        operations = []
        for tid in all_task_ids:
            operations.append((
                "UPDATE Task SET status = ?, updated_at = ?, revision = revision + 1 WHERE id = ? AND deleted_at IS NULL",
                (status.value, now, tid)
            ))
        
        await self.db_manager.execute_transaction(operations)
        
        logger.info(f"Updated status to {status.value} for task {task_id} and {len(descendants)} descendants")
        return len(all_task_ids)
    
    async def restore_task(self, task_id: int, restore_status: Optional[TaskStatus] = None) -> None:
        """Restore a soft-deleted task.
        
        Args:
            task_id: ID of task to restore
            restore_status: Status to restore to (defaults to PENDING if not provided)
        """
        status = restore_status or TaskStatus.PENDING
        await self.db_manager.execute_write(
            "UPDATE Task SET deleted_at = NULL, status = ? WHERE id = ?",
            (status.value, task_id)
        )
        
        logger.info(f"Restored task {task_id} to status {status.value}")
    
    async def hard_delete_task(self, task_id: int) -> None:
        """Permanently delete a task and all its relationships.
        
        Args:
            task_id: ID of task to delete
        """
        # Get parent info before deletion for renormalization
        parent_info = await self.get_parent_info(task_id)
        parent_id = parent_info['parent_id'] if parent_info else None
        
        await self.db_manager.execute_write(
            "DELETE FROM Task WHERE id = ?", (task_id,)
        )
        
        # Renormalize sort_order for siblings
        await self._renormalize_sort_order(parent_id)
        
        logger.info(f"Hard deleted task {task_id}")
    
    async def add_child_task(self, parent_id: int, child_id: int) -> None:
        """Add a child task to a parent task in the hierarchy.
        
        Args:
            parent_id: Parent task ID
            child_id: Child task ID to add
        """
        operations = []
        
        # First ensure self-reference exists for child (if not already)
        operations.append((
            "INSERT OR IGNORE INTO TaskClosure (ancestor_id, descendant_id, depth, sort_order) VALUES (?, ?, 0, 0)",
            (child_id, child_id)
        ))
        
        # Get the next sort_order for this parent's children
        rows = await self.db_manager.execute_read(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 as next_sort_order FROM TaskClosure WHERE ancestor_id = ? AND depth = 1",
            (parent_id,)
        )
        next_sort_order = rows[0]["next_sort_order"] if rows else 1
        
        # Add direct parent-child relationship
        operations.append((
            "INSERT INTO TaskClosure (ancestor_id, descendant_id, depth, sort_order) VALUES (?, ?, 1, ?)",
            (parent_id, child_id, next_sort_order)
        ))
        
        # Add relationships for all ancestors of parent to the child
        operations.append((
            """
            INSERT INTO TaskClosure (ancestor_id, descendant_id, depth, sort_order)
            SELECT tc.ancestor_id, ?, tc.depth + 1, 0
            FROM TaskClosure tc
            WHERE tc.descendant_id = ? AND tc.depth > 0
            """,
            (child_id, parent_id)
        ))
        
        await self.db_manager.execute_transaction(operations)
        logger.info(f"Added task {child_id} as child of task {parent_id}")
    
    async def is_descendant_of(self, potential_descendant_id: int, potential_ancestor_id: int) -> bool:
        """Check if a task is a descendant of another task.
        
        Args:
            potential_descendant_id: Task ID to check if it's a descendant
            potential_ancestor_id: Task ID to check if it's an ancestor
            
        Returns:
            True if potential_descendant_id is a descendant of potential_ancestor_id
        """
        rows = await self.db_manager.execute_read(
            """
            SELECT 1 FROM TaskClosure 
            WHERE ancestor_id = ? AND descendant_id = ? AND depth > 0
            """,
            (potential_ancestor_id, potential_descendant_id)
        )
        return len(rows) > 0
    
    async def move_task(self, task_id: int, new_parent_id: Optional[int]) -> None:
        """Move a task to a new parent in the hierarchy.
        
        Args:
            task_id: Task to move
            new_parent_id: New parent ID (None for root level)
            
        Raises:
            ValueError: If attempting to move a task into one of its own descendants
        """
        # Guard: prevent moving a task into one of its own descendants
        if new_parent_id is not None:
            if new_parent_id == task_id:
                raise ValueError("Cannot move a task to be its own parent")
            
            if await self.is_descendant_of(new_parent_id, task_id):
                raise ValueError("Cannot move a task into one of its own descendants")
        
        # Get all descendants of the task being moved (needed for proper closure table updates)
        descendants = await self.get_descendants(task_id)
        descendant_ids = [d.id for d in descendants]
        
        # The subtree being moved includes the task itself and all its descendants
        # We need to preserve relationships WITHIN the subtree (e.g., task->child, child->grandchild)
        # but remove relationships FROM external ancestors TO the subtree
        subtree_ids = [task_id] + descendant_ids
        
        # Remove the task itself from old ancestors (except self-reference)
        await self.db_manager.execute_write(
            "DELETE FROM TaskClosure WHERE descendant_id = ? AND depth > 0",
            (task_id,)
        )
        
        # Remove relationships where OLD ancestors (external to subtree) point to descendants
        # Important: We must include task_id in the exclusion set to preserve internal subtree relationships
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
        
        # Add to new hierarchy
        if new_parent_id is not None:
            await self._add_to_hierarchy(task_id, new_parent_id)
            
            # Re-add the descendants to the new ancestor chain
            # We need to add relationships from task_id's NEW ancestors to each descendant
            # Query task_id's ancestors (which now include new_parent, grandparent, etc.)
            # and create relationships to each descendant with correct depth
            for desc in descendants:
                # Get the depth from task_id to this descendant (preserved from before the move)
                depth_rows = await self.db_manager.execute_read(
                    "SELECT depth FROM TaskClosure WHERE ancestor_id = ? AND descendant_id = ?",
                    (task_id, desc.id)
                )
                if not depth_rows:
                    continue  # Skip if relationship not found (shouldn't happen)
                
                desc_depth_from_task = depth_rows[0]["depth"]
                
                # Add relationships from all of task_id's NEW ancestors to this descendant
                # task_id's ancestors are queried via descendant_id = task_id (depth > 0 excludes self-ref)
                await self.db_manager.execute_write(
                    """
                    INSERT OR IGNORE INTO TaskClosure (ancestor_id, descendant_id, depth, sort_order)
                    SELECT tc.ancestor_id, ?, tc.depth + ?, 0
                    FROM TaskClosure tc
                    WHERE tc.descendant_id = ? AND tc.depth > 0
                    """,
                    (desc.id, desc_depth_from_task, task_id)
                )
        
        logger.info(f"Moved task {task_id} to parent {new_parent_id}")
    
    async def reorder_tasks(self, parent_id: Optional[int], task_ids: List[int]) -> None:
        """Reorder tasks within a specific parent (or root level if parent_id is None).
        
        Args:
            parent_id: Parent task ID (None for root-level tasks)
            task_ids: List of task IDs in desired order
        """
        operations = []
        
        for index, task_id in enumerate(task_ids):
            new_sort_order = index + 1
            if parent_id is not None:
                # Update sort_order for parent-child relationship
                operations.append((
                    "UPDATE TaskClosure SET sort_order = ? WHERE ancestor_id = ? AND descendant_id = ? AND depth = 1",
                    (new_sort_order, parent_id, task_id)
                ))
            else:
                # For root-level tasks, update the self-reference sort_order
                operations.append((
                    "UPDATE TaskClosure SET sort_order = ? WHERE ancestor_id = ? AND descendant_id = ? AND depth = 0",
                    (new_sort_order, task_id, task_id)
                ))
        
        await self.db_manager.execute_transaction(operations)
        logger.info(f"Reordered {len(task_ids)} tasks under parent {parent_id}")
    
    async def move_task_with_position(self, task_id: int, new_parent_id: Optional[int], position: int) -> None:
        """Move a task to a new parent at a specific position.
        
        Args:
            task_id: Task to move
            new_parent_id: New parent ID (None for root level)
            position: 0-indexed position in the new parent's children
        """
        # First move the task to the new parent
        await self.move_task(task_id, new_parent_id)
        
        # Get current children of the new parent (or root tasks if parent is None)
        if new_parent_id is not None:
            rows = await self.db_manager.execute_read(
                "SELECT descendant_id FROM TaskClosure WHERE ancestor_id = ? AND depth = 1 ORDER BY sort_order",
                (new_parent_id,)
            )
        else:
            # Root tasks are those with self-reference (depth=0) but no parent (no depth=1 entry)
            rows = await self.db_manager.execute_read(
                """
                SELECT tc.descendant_id
                FROM TaskClosure tc
                WHERE tc.depth = 0 AND tc.ancestor_id = tc.descendant_id
                AND NOT EXISTS (
                    SELECT 1 FROM TaskClosure tc2 
                    WHERE tc2.descendant_id = tc.descendant_id AND tc2.depth = 1
                )
                ORDER BY tc.sort_order
                """
            )
        
        current_children = [row["descendant_id"] for row in rows]
        
        # Insert the moved task at the desired position
        if task_id in current_children:
            current_children.remove(task_id)
        
        # Clamp position to valid range
        position = max(0, min(position, len(current_children)))
        current_children.insert(position, task_id)
        
        # Reorder all children
        await self.reorder_tasks(new_parent_id, current_children)
    
    async def get_children(self, parent_id: int, order_by_custom: bool = False) -> List[Task]:
        """Get direct children of a task.
        
        Args:
            parent_id: Parent task ID
            order_by_custom: If True, order by sort_order; if False, order by created_at
            
        Returns:
            List of child tasks
        """
        if order_by_custom:
            order_clause = "ORDER BY tc.sort_order, t.created_at"
        else:
            order_clause = "ORDER BY t.created_at"
            
        rows = await self.db_manager.execute_read(
            f"""
            SELECT t.* FROM Task t
            JOIN TaskClosure tc ON t.id = tc.descendant_id
            WHERE tc.ancestor_id = ? AND tc.depth = 1 AND t.deleted_at IS NULL
            {order_clause}
            """,
            (parent_id,)
        )
        
        return [self._row_to_task(row) for row in rows]
    
    async def get_descendants(self, ancestor_id: int) -> List[Task]:
        """Get all descendants of a task (recursive children).
        
        Args:
            ancestor_id: Ancestor task ID
            
        Returns:
            List of descendant tasks
        """
        rows = await self.db_manager.execute_read(
            """
            SELECT t.* FROM Task t
            JOIN TaskClosure tc ON t.id = tc.descendant_id
            WHERE tc.ancestor_id = ? AND tc.depth > 0 AND t.deleted_at IS NULL
            ORDER BY tc.depth, t.created_at
            """,
            (ancestor_id,)
        )
        
        return [self._row_to_task(row) for row in rows]
    
    async def get_ancestors(self, descendant_id: int) -> List[Task]:
        """Get all ancestors of a task (recursive parents).
        
        Args:
            descendant_id: Descendant task ID
            
        Returns:
            List of ancestor tasks
        """
        rows = await self.db_manager.execute_read(
            """
            SELECT t.* FROM Task t
            JOIN TaskClosure tc ON t.id = tc.ancestor_id
            WHERE tc.descendant_id = ? AND tc.depth > 0 AND t.deleted_at IS NULL
            ORDER BY tc.depth DESC
            """,
            (descendant_id,)
        )
        
        return [self._row_to_task(row) for row in rows]
    
    async def get_parent_info(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Get the direct parent and position info for a task.
        
        Args:
            task_id: Task ID
            
        Returns:
            Dict with 'parent_id' (int or None) and 'sort_order' (int),
            or None if task has no closure entries
        """
        # Get the direct parent (depth = 1)
        rows = await self.db_manager.execute_read(
            """
            SELECT ancestor_id, sort_order FROM TaskClosure 
            WHERE descendant_id = ? AND depth = 1
            """,
            (task_id,)
        )
        
        if rows:
            return {
                'parent_id': rows[0]['ancestor_id'],
                'sort_order': rows[0]['sort_order']
            }
        
        # No depth-1 entry means this is a root task
        # Get sort_order from self-reference (depth = 0)
        rows = await self.db_manager.execute_read(
            """
            SELECT sort_order FROM TaskClosure 
            WHERE ancestor_id = ? AND descendant_id = ? AND depth = 0
            """,
            (task_id, task_id)
        )
        
        if rows:
            return {
                'parent_id': None,
                'sort_order': rows[0]['sort_order']
            }
        
        return None
    
    async def _add_to_hierarchy(self, task_id: int, parent_id: int) -> None:
        """Add a task to the hierarchy under a parent."""
        operations = []
        
        # Add self-reference
        operations.append((
            "INSERT OR IGNORE INTO TaskClosure (ancestor_id, descendant_id, depth, sort_order) VALUES (?, ?, 0, 0)",
            (task_id, task_id)
        ))
        
        # Get the next sort_order for this parent's children
        rows = await self.db_manager.execute_read(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 as next_sort_order FROM TaskClosure WHERE ancestor_id = ? AND depth = 1",
            (parent_id,)
        )
        next_sort_order = rows[0]["next_sort_order"] if rows else 1
        
        # Add relationship to parent and all ancestors
        operations.append((
            """
            INSERT INTO TaskClosure (ancestor_id, descendant_id, depth, sort_order)
            SELECT ancestor_id, ?, depth + 1, CASE WHEN depth = 0 THEN ? ELSE 0 END
            FROM TaskClosure
            WHERE descendant_id = ?
            """,
            (task_id, next_sort_order, parent_id)
        ))
        
        await self.db_manager.execute_transaction(operations)
    
    async def _add_self_reference(self, task_id: int) -> None:
        """Add self-reference for root tasks with proper sort_order."""
        # Get the next sort_order for root tasks
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
            "INSERT OR IGNORE INTO TaskClosure (ancestor_id, descendant_id, depth, sort_order) VALUES (?, ?, 0, ?)",
            (task_id, task_id, next_sort_order)
        )
    
    async def _renormalize_sort_order(self, parent_id: Optional[int], exclude_task_id: Optional[int] = None) -> None:
        """Renormalize sort_order values for siblings after a task is deleted.
        
        This ensures sort_order values are contiguous (1, 2, 3, ...) without gaps.
        
        Args:
            parent_id: Parent task ID (None for root-level tasks)
            exclude_task_id: Optional task ID to exclude (for soft-deleted tasks still in DB)
        """
        if parent_id is not None:
            # Get children of the parent, ordered by current sort_order
            exclude_clause = f"AND tc.descendant_id != {exclude_task_id}" if exclude_task_id else ""
            rows = await self.db_manager.execute_read(
                f"""
                SELECT tc.descendant_id 
                FROM TaskClosure tc
                JOIN Task t ON t.id = tc.descendant_id
                WHERE tc.ancestor_id = ? AND tc.depth = 1 
                AND t.deleted_at IS NULL {exclude_clause}
                ORDER BY tc.sort_order
                """,
                (parent_id,)
            )
            task_ids = [row["descendant_id"] for row in rows]
            
            # Reorder with contiguous values
            if task_ids:
                await self.reorder_tasks(parent_id, task_ids)
        else:
            # Get root tasks, ordered by current sort_order
            exclude_clause = f"AND tc.descendant_id != {exclude_task_id}" if exclude_task_id else ""
            rows = await self.db_manager.execute_read(
                f"""
                SELECT tc.descendant_id
                FROM TaskClosure tc
                JOIN Task t ON t.id = tc.descendant_id
                WHERE tc.depth = 0 AND tc.ancestor_id = tc.descendant_id
                AND t.deleted_at IS NULL {exclude_clause}
                AND NOT EXISTS (
                    SELECT 1 FROM TaskClosure tc2 
                    WHERE tc2.descendant_id = tc.descendant_id AND tc2.depth = 1
                )
                ORDER BY tc.sort_order
                """
            )
            task_ids = [row["descendant_id"] for row in rows]
            
            # Reorder with contiguous values
            if task_ids:
                await self.reorder_tasks(None, task_ids)
    
    def _row_to_task(self, row: aiosqlite.Row) -> Task:
        """Convert a database row to a Task object."""
        return Task(
            id=row["id"],
            uuid=row["uuid"],
            revision=row["revision"],
            title=row["title"],
            description=row["description"],
            recurrence_rrule=row["recurrence_rrule"],
            recurrence_start_utc=row["recurrence_start_utc"],
            next_due_utc=row["next_due_utc"],
            status=TaskStatus(row["status"]),
            priority=row["priority"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            deleted_at=row["deleted_at"]
        )
    
    async def search_tasks(self, query: str) -> List[Task]:
        """Search tasks using FTS5 full-text search.
        
        Args:
            query: Search query
            
        Returns:
            List of matching tasks
        """
        rows = await self.db_manager.execute_read(
            """
            SELECT t.* FROM Task t
            JOIN TaskFTS fts ON t.id = fts.rowid
            WHERE TaskFTS MATCH ? AND t.deleted_at IS NULL
            ORDER BY bm25(TaskFTS)
            """,
            (query,)
        )
        
        return [self._row_to_task(row) for row in rows] 