"""Task API endpoints for Local-First To-Do application."""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field, field_validator

from local_first_todo.database.models import Task, TaskStatus
from local_first_todo.dependencies import get_task_repository, get_db_write_lock, get_undo_redo_service, get_attachment_service
from local_first_todo.api.websocket import broadcast_task_update

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


# Pydantic models for API requests/responses
class TaskCreate(BaseModel):
    """Request model for creating a new task."""
    title: str = Field(
        ..., 
        min_length=1, 
        max_length=500, 
        description="Task title (required)",
        json_schema_extra={"example": "Complete project documentation"}
    )
    description: Optional[str] = Field(
        None, 
        max_length=50000, 
        description="Task description in Markdown format",
        json_schema_extra={"example": "## Overview\n\nWrite comprehensive docs for the API."}
    )
    recurrence_rrule: Optional[str] = Field(
        None, 
        description="Recurrence rule following RFC 5545 iCalendar spec",
        json_schema_extra={"example": "FREQ=WEEKLY;BYDAY=MO,WE,FR"}
    )
    recurrence_start_utc: Optional[str] = Field(
        None, 
        description="Start date for recurrence calculation (ISO 8601 UTC)",
        json_schema_extra={"example": "2026-02-06T09:00:00Z"}
    )
    next_due_utc: Optional[str] = Field(
        None, 
        description="Next due date/time (ISO 8601 UTC)",
        json_schema_extra={"example": "2026-02-10T17:00:00Z"}
    )
    status: TaskStatus = Field(
        TaskStatus.PENDING, 
        description="Initial task status"
    )
    priority: Optional[int] = Field(
        None, 
        ge=1, 
        le=5, 
        description="Task priority: 1=Urgent, 2=High, 3=Medium, 4=Low, 5=None",
        json_schema_extra={"example": 2}
    )
    parent_id: Optional[int] = Field(
        None, 
        description="Parent task ID for creating subtasks (null for root-level tasks)",
        json_schema_extra={"example": 42}
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "Complete project documentation",
                    "description": "Write comprehensive API docs",
                    "priority": 2,
                    "next_due_utc": "2026-02-10T17:00:00Z"
                }
            ]
        }
    }

    @field_validator('next_due_utc', 'recurrence_start_utc')
    @classmethod
    def validate_utc_datetime(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize UTC datetime strings."""
        if v is None:
            return v
        
        try:
            # Parse the datetime string
            if isinstance(v, str):
                # Handle various input formats and normalize to required format
                from dateutil import parser
                dt = parser.parse(v)
                
                # Convert to UTC if timezone info is present
                if dt.tzinfo is not None:
                    dt = dt.astimezone(timezone.utc)
                else:
                    # If no timezone info, assume local time and convert to UTC
                    dt = dt.replace(tzinfo=timezone.utc)
                
                # Format to the exact format required by database constraint
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            return v
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid datetime format. Expected ISO 8601 UTC format (YYYY-MM-DDTHH:MM:SSZ): {e}")
        except ImportError:
            # Fallback if dateutil is not available
            try:
                dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError as e:
                raise ValueError(f"Invalid datetime format. Expected ISO 8601 UTC format (YYYY-MM-DDTHH:MM:SSZ): {e}")


class TaskUpdate(BaseModel):
    """Request model for updating an existing task. Only provided fields will be updated."""
    title: Optional[str] = Field(
        None, 
        min_length=1, 
        max_length=500, 
        description="Updated task title",
        json_schema_extra={"example": "Updated task title"}
    )
    description: Optional[str] = Field(
        None, 
        max_length=50000, 
        description="Updated task description in Markdown format",
        json_schema_extra={"example": "## Updated description\n\nNew content here."}
    )
    recurrence_rrule: Optional[str] = Field(
        None, 
        description="Updated recurrence rule (RFC 5545)",
        json_schema_extra={"example": "FREQ=DAILY"}
    )
    recurrence_start_utc: Optional[str] = Field(
        None, 
        description="Updated recurrence start time (ISO 8601 UTC)",
        json_schema_extra={"example": "2026-02-06T09:00:00Z"}
    )
    next_due_utc: Optional[str] = Field(
        None, 
        description="Updated due date/time (ISO 8601 UTC)",
        json_schema_extra={"example": "2026-02-15T17:00:00Z"}
    )
    status: Optional[TaskStatus] = Field(
        None, 
        description="Updated task status"
    )
    priority: Optional[int] = Field(
        None, 
        ge=1, 
        le=5, 
        description="Updated priority: 1=Urgent, 2=High, 3=Medium, 4=Low, 5=None",
        json_schema_extra={"example": 1}
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "completed"
                },
                {
                    "title": "Updated title",
                    "priority": 1,
                    "next_due_utc": "2026-02-15T17:00:00Z"
                }
            ]
        }
    }

    @field_validator('next_due_utc', 'recurrence_start_utc')
    @classmethod
    def validate_utc_datetime(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize UTC datetime strings."""
        if v is None:
            return v
        
        try:
            # Parse the datetime string
            if isinstance(v, str):
                # Handle various input formats and normalize to required format
                from dateutil import parser
                dt = parser.parse(v)
                
                # Convert to UTC if timezone info is present
                if dt.tzinfo is not None:
                    dt = dt.astimezone(timezone.utc)
                else:
                    # If no timezone info, assume local time and convert to UTC
                    dt = dt.replace(tzinfo=timezone.utc)
                
                # Format to the exact format required by database constraint
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            return v
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid datetime format. Expected ISO 8601 UTC format (YYYY-MM-DDTHH:MM:SSZ): {e}")
        except ImportError:
            # Fallback if dateutil is not available
            try:
                dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError as e:
                raise ValueError(f"Invalid datetime format. Expected ISO 8601 UTC format (YYYY-MM-DDTHH:MM:SSZ): {e}")


class TaskReorderRequest(BaseModel):
    """Request model for reordering tasks within a parent container."""
    task_ids: List[int] = Field(
        ..., 
        description="Array of task IDs in the desired display order",
        json_schema_extra={"example": [5, 3, 8, 1, 2]}
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [{"task_ids": [5, 3, 8, 1, 2]}]
        }
    }


class TaskMoveRequest(BaseModel):
    """Request model for moving a task to a different parent with optional position."""
    new_parent_id: Optional[int] = Field(
        None, 
        description="New parent task ID (null/omit to move to root level)",
        json_schema_extra={"example": 10}
    )
    position: Optional[int] = Field(
        None, 
        ge=0, 
        description="0-indexed position among siblings (omit to append at end)",
        json_schema_extra={"example": 0}
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {"new_parent_id": 10, "position": 0},
                {"new_parent_id": None}
            ]
        }
    }


class TaskReorderResponse(BaseModel):
    """Response model for task reordering operations."""
    success: bool = Field(..., description="Whether the reordering succeeded")
    updated_count: int = Field(..., description="Number of tasks that were reordered")
    
    model_config = {
        "json_schema_extra": {
            "examples": [{"success": True, "updated_count": 5}]
        }
    }


class TaskMoveResponse(BaseModel):
    """Response model for task move operations."""
    success: bool = Field(..., description="Whether the move succeeded")
    moved_task_count: int = Field(..., description="Total tasks moved (includes all descendants)")
    
    model_config = {
        "json_schema_extra": {
            "examples": [{"success": True, "moved_task_count": 3}]
        }
    }


class TaskResponse(BaseModel):
    """Response model for individual tasks."""
    id: int = Field(..., description="Unique task ID", json_schema_extra={"example": 1})
    uuid: str = Field(..., description="UUID for external references", json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"})
    revision: int = Field(..., description="Optimistic concurrency version number", json_schema_extra={"example": 3})
    title: str = Field(..., description="Task title", json_schema_extra={"example": "Complete project documentation"})
    description: Optional[str] = Field(None, description="Task description (Markdown)", json_schema_extra={"example": "## Overview\n\nDetailed task description."})
    recurrence_rrule: Optional[str] = Field(None, description="Recurrence rule (RFC 5545)", json_schema_extra={"example": "FREQ=WEEKLY;BYDAY=MO"})
    recurrence_start_utc: Optional[str] = Field(None, description="Recurrence start (ISO 8601 UTC)", json_schema_extra={"example": "2026-02-06T09:00:00Z"})
    next_due_utc: Optional[str] = Field(None, description="Next due date/time (ISO 8601 UTC)", json_schema_extra={"example": "2026-02-10T17:00:00Z"})
    status: TaskStatus = Field(..., description="Current task status")
    priority: Optional[int] = Field(None, description="Priority: 1=Urgent to 4=Low", json_schema_extra={"example": 2})
    created_at: str = Field(..., description="Creation timestamp (ISO 8601 UTC)", json_schema_extra={"example": "2026-02-01T10:30:00Z"})
    updated_at: str = Field(..., description="Last update timestamp (ISO 8601 UTC)", json_schema_extra={"example": "2026-02-05T14:20:00Z"})
    deleted_at: Optional[str] = Field(None, description="Soft deletion timestamp (null if active)", json_schema_extra={"example": None})
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "uuid": "550e8400-e29b-41d4-a716-446655440000",
                    "revision": 3,
                    "title": "Complete project documentation",
                    "description": "## Overview\n\nWrite comprehensive docs.",
                    "recurrence_rrule": None,
                    "recurrence_start_utc": None,
                    "next_due_utc": "2026-02-10T17:00:00Z",
                    "status": "pending",
                    "priority": 2,
                    "created_at": "2026-02-01T10:30:00Z",
                    "updated_at": "2026-02-05T14:20:00Z",
                    "deleted_at": None
                }
            ]
        }
    }


class TaskBulkRequest(BaseModel):
    """Request model for bulk task operations. Supports create, update, and delete operations."""
    operations: List[Dict[str, Any]] = Field(
        ..., 
        description="List of operations to perform atomically",
        json_schema_extra={
            "example": [
                {"type": "create", "data": {"title": "New task", "priority": 2}},
                {"type": "update", "id": 5, "data": {"status": "completed"}},
                {"type": "delete", "id": 3}
            ]
        }
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "operations": [
                        {"type": "create", "data": {"title": "New task", "priority": 2}},
                        {"type": "update", "id": 5, "data": {"status": "completed"}},
                        {"type": "delete", "id": 3}
                    ]
                }
            ]
        }
    }


class TaskBulkResponse(BaseModel):
    """Response model for bulk task operations."""
    results: List[Dict[str, Any]] = Field(
        ..., 
        description="Results for each operation in the same order as requested",
        json_schema_extra={
            "example": [
                {"success": True, "id": 10, "uuid": "abc-123"},
                {"success": True, "id": 5, "uuid": "def-456"},
                {"success": True, "id": 3}
            ]
        }
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "results": [
                        {"success": True, "id": 10, "uuid": "abc-123"},
                        {"success": True, "id": 5, "uuid": "def-456"},
                        {"success": False, "error": {"code": "NOT_FOUND", "message": "Task 3 not found"}}
                    ]
                }
            ]
        }
    }


def task_to_response(task: Task) -> TaskResponse:
    """Convert a Task object to TaskResponse."""
    return TaskResponse(
        id=task.id,
        uuid=task.uuid,
        revision=task.revision,
        title=task.title,
        description=task.description,
        recurrence_rrule=task.recurrence_rrule,
        recurrence_start_utc=task.recurrence_start_utc,
        next_due_utc=task.next_due_utc,
        status=task.status,
        priority=task.priority,
        created_at=task.created_at,
        updated_at=task.updated_at,
        deleted_at=task.deleted_at
    )


@router.get(
    "/", 
    response_model=List[TaskResponse],
    summary="List Tasks",
    response_description="List of tasks matching the filter criteria"
)
async def list_tasks(
    parent_id: Optional[int] = Query(None, description="Filter by parent task ID (omit for all tasks)"),
    order_by: str = Query("created_at", description="Sort order: 'created_at' (chronological) or 'custom' (user-defined)")
) -> List[TaskResponse]:
    """List all tasks or filter by parent.
    
    - **parent_id**: If provided, returns only direct children of that task
    - **order_by**: Sort by creation time or custom user-defined order
    """
    task_repository = get_task_repository()
    
    try:
        if parent_id is not None:
            # Get children of specific parent
            order_by_custom = (order_by == "custom")
            tasks = await task_repository.get_children(parent_id, order_by_custom=order_by_custom)
        else:
            # Get all tasks
            tasks = await task_repository.get_all_tasks()
        
        return [task_to_response(task) for task in tasks]
        
    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list tasks"
        )


@router.get(
    "/root", 
    response_model=List[TaskResponse],
    summary="List Root Tasks",
    response_description="List of root-level tasks (no parent)"
)
async def list_root_tasks(
    order_by: str = Query("custom", description="Sort order: 'created_at' or 'custom' (user-defined)")
) -> List[TaskResponse]:
    """Get all root-level tasks (tasks without a parent).
    
    Root tasks are the top level of the task hierarchy. Use this endpoint
    to get the starting point for navigating the task tree.
    """
    task_repository = get_task_repository()
    try:
        order_by_custom = (order_by == "custom")
        tasks = await task_repository.get_root_tasks(order_by_custom=order_by_custom)
        return [task_to_response(task) for task in tasks]
    except Exception as e:
        logger.error(f"Error listing root tasks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list root tasks"
        )


class TaskWithChildren(BaseModel):
    """Task with nested children for hierarchical tree representation."""
    id: int = Field(..., description="Unique task ID")
    uuid: str = Field(..., description="UUID for external references")
    revision: int = Field(..., description="Version number for optimistic concurrency")
    title: str = Field(..., description="Task title")
    description: Optional[str] = Field(None, description="Task description (Markdown)")
    recurrence_rrule: Optional[str] = Field(None, description="Recurrence rule (RFC 5545)")
    recurrence_start_utc: Optional[str] = Field(None, description="Recurrence start (ISO 8601 UTC)")
    next_due_utc: Optional[str] = Field(None, description="Next due date/time (ISO 8601 UTC)")
    status: TaskStatus = Field(..., description="Current task status")
    priority: Optional[int] = Field(None, description="Priority: 1=Urgent to 4=Low")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601 UTC)")
    updated_at: str = Field(..., description="Last update timestamp (ISO 8601 UTC)")
    deleted_at: Optional[str] = Field(None, description="Soft deletion timestamp")
    parent_id: Optional[int] = Field(None, description="Parent task ID (null for root tasks)")
    children: List["TaskWithChildren"] = Field(default=[], description="Nested child tasks")


class TaskTreeResponse(BaseModel):
    """Response model for the full task tree with nested hierarchy."""
    tasks: List[TaskWithChildren] = Field(..., description="Root-level tasks with nested children")
    total_count: int = Field(..., description="Total number of tasks in the tree")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "tasks": [
                        {
                            "id": 1,
                            "uuid": "abc-123",
                            "revision": 1,
                            "title": "Project A",
                            "description": None,
                            "recurrence_rrule": None,
                            "recurrence_start_utc": None,
                            "next_due_utc": None,
                            "status": "pending",
                            "priority": 2,
                            "created_at": "2026-02-01T10:00:00Z",
                            "updated_at": "2026-02-01T10:00:00Z",
                            "deleted_at": None,
                            "parent_id": None,
                            "children": [
                                {
                                    "id": 2,
                                    "uuid": "def-456",
                                    "revision": 1,
                                    "title": "Subtask 1",
                                    "description": None,
                                    "recurrence_rrule": None,
                                    "recurrence_start_utc": None,
                                    "next_due_utc": None,
                                    "status": "completed",
                                    "priority": None,
                                    "created_at": "2026-02-01T11:00:00Z",
                                    "updated_at": "2026-02-02T09:00:00Z",
                                    "deleted_at": None,
                                    "parent_id": 1,
                                    "children": []
                                }
                            ]
                        }
                    ],
                    "total_count": 2
                }
            ]
        }
    }


# Allow self-referencing type
TaskWithChildren.model_rebuild()


@router.get(
    "/tree", 
    response_model=TaskTreeResponse,
    summary="Get Full Task Tree",
    response_description="Complete task hierarchy with nested children"
)
async def get_task_tree(
    order_by: str = Query("custom", description="Sort order: 'created_at' or 'custom' (user-defined)")
) -> TaskTreeResponse:
    """Get the complete task tree in a single optimized request.
    
    Returns all tasks organized as a nested tree structure. This endpoint is
    **optimized to avoid N+1 queries** by fetching all data in one database call.
    
    Use this for:
    - Initial page load
    - Full tree synchronization
    - Tree visualization components
    """
    task_repository = get_task_repository()
    
    try:
        # Get all tasks
        all_tasks = await task_repository.get_all_tasks()
        
        # Build a map of task_id -> task data with children list
        tasks_map: Dict[int, Dict[str, Any]] = {}
        for task in all_tasks:
            tasks_map[task.id] = {
                "id": task.id,
                "uuid": task.uuid,
                "revision": task.revision,
                "title": task.title,
                "description": task.description,
                "recurrence_rrule": task.recurrence_rrule,
                "recurrence_start_utc": task.recurrence_start_utc,
                "next_due_utc": task.next_due_utc,
                "status": task.status,
                "priority": task.priority,
                "created_at": task.created_at,
                "updated_at": task.updated_at,
                "deleted_at": task.deleted_at,
                "parent_id": None,
                "children": [],
                "_sort_order": 0
            }
        
        # Get all parent-child relationships in a single query
        rows = await task_repository.db_manager.execute_read(
            """
            SELECT tc.ancestor_id, tc.descendant_id, tc.sort_order
            FROM TaskClosure tc
            JOIN Task t ON t.id = tc.descendant_id
            WHERE tc.depth = 1 AND t.deleted_at IS NULL
            ORDER BY tc.sort_order
            """
        )
        
        # Build parent-child relationships
        child_ids = set()
        for row in rows:
            ancestor_id = row["ancestor_id"]
            descendant_id = row["descendant_id"]
            sort_order = row["sort_order"]
            
            if descendant_id in tasks_map:
                tasks_map[descendant_id]["parent_id"] = ancestor_id
                tasks_map[descendant_id]["_sort_order"] = sort_order
                child_ids.add(descendant_id)
                
                if ancestor_id in tasks_map:
                    tasks_map[ancestor_id]["children"].append(tasks_map[descendant_id])
        
        # Get root task ordering
        root_order_rows = await task_repository.db_manager.execute_read(
            """
            SELECT tc.descendant_id, tc.sort_order
            FROM TaskClosure tc
            JOIN Task t ON t.id = tc.descendant_id
            WHERE tc.depth = 0 AND tc.ancestor_id = tc.descendant_id
            AND t.deleted_at IS NULL
            AND NOT EXISTS (
                SELECT 1 FROM TaskClosure tc2 
                WHERE tc2.descendant_id = tc.descendant_id AND tc2.depth = 1
            )
            ORDER BY tc.sort_order
            """
        )
        
        # Identify root tasks (tasks without parents)
        root_task_order = {row["descendant_id"]: row["sort_order"] for row in root_order_rows}
        root_tasks = []
        for task_id, task_data in tasks_map.items():
            if task_id not in child_ids:
                task_data["_sort_order"] = root_task_order.get(task_id, 0)
                root_tasks.append(task_data)
        
        # Sort root tasks and children by sort_order or created_at
        if order_by == "custom":
            root_tasks.sort(key=lambda t: t["_sort_order"])
            for task_data in tasks_map.values():
                task_data["children"].sort(key=lambda t: t["_sort_order"])
        else:
            root_tasks.sort(key=lambda t: t["created_at"])
            for task_data in tasks_map.values():
                task_data["children"].sort(key=lambda t: t["created_at"])
        
        # Remove internal _sort_order field from response
        def clean_task(task: Dict[str, Any]) -> Dict[str, Any]:
            task.pop("_sort_order", None)
            for child in task["children"]:
                clean_task(child)
            return task
        
        cleaned_root_tasks = [clean_task(t) for t in root_tasks]
        
        return TaskTreeResponse(
            tasks=cleaned_root_tasks,
            total_count=len(all_tasks)
        )
        
    except Exception as e:
        logger.error(f"Error getting task tree: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get task tree"
        )


@router.get(
    "/{task_id}", 
    response_model=TaskResponse,
    summary="Get Task by ID",
    response_description="The requested task"
)
async def get_task(task_id: int) -> TaskResponse:
    """Get a specific task by its numeric ID."""
    task_repository = get_task_repository()
    
    task = await task_repository.get_task_by_id(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found"
        )
    
    return task_to_response(task)


@router.post(
    "/root/reorder", 
    response_model=TaskReorderResponse,
    summary="Reorder Root Tasks",
    response_description="Reorder operation result"
)
async def reorder_root_tasks(request_data: TaskReorderRequest) -> TaskReorderResponse:
    """Reorder root-level tasks by specifying the desired order.
    
    Provide an array of task IDs in the order you want them displayed.
    Only root tasks (tasks without parents) can be reordered with this endpoint.
    """
    task_repository = get_task_repository()
    db_write_lock = get_db_write_lock()
    undo_service = get_undo_redo_service()
    
    async with db_write_lock:
        try:
            # Get current root tasks to validate
            current_root_tasks = await task_repository.get_root_tasks(order_by_custom=True)
            current_root_ids = {task.id for task in current_root_tasks}
            
            # Validate that all task_ids are root tasks
            for task_id in request_data.task_ids:
                if task_id not in current_root_ids:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Task {task_id} is not a root-level task"
                    )
            
            # Record the current order for undo
            current_order = await task_repository.db_manager.execute_read(
                """
                SELECT tc.descendant_id, tc.sort_order 
                FROM TaskClosure tc
                JOIN Task t ON t.id = tc.descendant_id
                WHERE tc.depth = 0 AND tc.ancestor_id = tc.descendant_id
                AND t.deleted_at IS NULL
                AND NOT EXISTS (
                    SELECT 1 FROM TaskClosure tc2 
                    WHERE tc2.descendant_id = tc.descendant_id AND tc2.depth = 1
                )
                ORDER BY tc.sort_order
                """
            )
            
            # Apply the reordering (parent_id=None for root tasks)
            await task_repository.reorder_tasks(None, request_data.task_ids)
            
            # Record undo operation
            old_state = {
                'parent_id': None,
                'order': [{'id': row['descendant_id'], 'sort_order': row['sort_order']} for row in current_order]
            }
            new_state = {
                'parent_id': None,
                'order': [{'id': task_id, 'sort_order': i + 1} for i, task_id in enumerate(request_data.task_ids)]
            }
            await undo_service.record_task_operation("reorder", old_state, new_state)
            
            # Broadcast reordering to WebSocket clients
            await broadcast_task_update("reordered", {
                "parent_id": None,
                "task_ids": request_data.task_ids
            })
            
            logger.info(f"Reordered {len(request_data.task_ids)} root tasks")
            return TaskReorderResponse(success=True, updated_count=len(request_data.task_ids))
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error reordering root tasks: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reorder root tasks"
            )


@router.post(
    "/{parent_id}/reorder", 
    response_model=TaskReorderResponse,
    summary="Reorder Subtasks",
    response_description="Reorder operation result"
)
async def reorder_tasks(parent_id: int, request_data: TaskReorderRequest) -> TaskReorderResponse:
    """Reorder child tasks within a specific parent task.
    
    Provide an array of task IDs in the order you want them displayed.
    All specified task IDs must be direct children of the given parent.
    """
    task_repository = get_task_repository()
    db_write_lock = get_db_write_lock()
    undo_service = get_undo_redo_service()
    
    async with db_write_lock:
        try:
            # Validate that parent exists
            parent_task = await task_repository.get_task_by_id(parent_id)
            if not parent_task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Parent task with ID {parent_id} not found"
                )
            
            # Validate that all task_ids belong to this parent
            current_children = await task_repository.get_children(parent_id)
            current_child_ids = {task.id for task in current_children}
            
            for task_id in request_data.task_ids:
                if task_id not in current_child_ids:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Task {task_id} is not a child of parent {parent_id}"
                    )
            
            # Record the current order for undo
            current_order = await task_repository.db_manager.execute_read(
                "SELECT descendant_id, sort_order FROM TaskClosure WHERE ancestor_id = ? AND depth = 1 ORDER BY sort_order",
                (parent_id,)
            )
            
            # Apply the reordering
            await task_repository.reorder_tasks(parent_id, request_data.task_ids)
            
            # Record undo operation with parent_id for proper reversal
            old_state = {
                'parent_id': parent_id,
                'order': [{'id': row['descendant_id'], 'sort_order': row['sort_order']} for row in current_order]
            }
            new_state = {
                'parent_id': parent_id,
                'order': [{'id': task_id, 'sort_order': i + 1} for i, task_id in enumerate(request_data.task_ids)]
            }
            await undo_service.record_task_operation("reorder", old_state, new_state)
            
            # Broadcast reordering to WebSocket clients
            await broadcast_task_update("reordered", {
                "parent_id": parent_id,
                "task_ids": request_data.task_ids
            })
            
            logger.info(f"Reordered {len(request_data.task_ids)} tasks under parent {parent_id}")
            return TaskReorderResponse(success=True, updated_count=len(request_data.task_ids))
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error reordering tasks: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reorder tasks"
            )


@router.get(
    "/uuid/{task_uuid}", 
    response_model=TaskResponse,
    summary="Get Task by UUID",
    response_description="The requested task"
)
async def get_task_by_uuid(task_uuid: str) -> TaskResponse:
    """Get a specific task by its UUID.
    
    UUIDs are stable identifiers suitable for external references and synchronization.
    """
    try:
        task_repository = get_task_repository()
        task = await task_repository.get_task_by_uuid(task_uuid)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with UUID {task_uuid} not found"
            )
        return task_to_response(task)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task by UUID {task_uuid}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve task"
        )


@router.get(
    "/status/{task_status}", 
    response_model=List[TaskResponse],
    summary="Get Tasks by Status",
    response_description="Tasks with the specified status"
)
async def get_tasks_by_status(task_status: TaskStatus) -> List[TaskResponse]:
    """Get all tasks with a specific status (pending, in_progress, completed, etc.)."""
    try:
        task_repository = get_task_repository()
        tasks = await task_repository.get_tasks_by_status(task_status)
        return [task_to_response(task) for task in tasks]
    except Exception as e:
        logger.error(f"Error getting tasks by status {task_status}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tasks by status"
        )


@router.post(
    "/", 
    response_model=TaskResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create Task",
    response_description="The newly created task"
)
async def create_task(task_data: TaskCreate) -> TaskResponse:
    """Create a new task with optional hierarchy placement.
    
    - Set **parent_id** to create a subtask under an existing task
    - Omit **parent_id** to create a root-level task
    - The task is automatically added to the undo history
    """
    task_repository = get_task_repository()
    db_write_lock = get_db_write_lock()
    undo_service = get_undo_redo_service()
    
    async with db_write_lock:
        try:
            # Create Task object
            task = Task(
                title=task_data.title,
                description=task_data.description,
                recurrence_rrule=task_data.recurrence_rrule,
                recurrence_start_utc=task_data.recurrence_start_utc,
                next_due_utc=task_data.next_due_utc,
                status=task_data.status,
                priority=task_data.priority,
            )
            
            # Create task in database
            task_id = await task_repository.create_task(task, task_data.parent_id)
            
            # Retrieve the created task
            created_task = await task_repository.get_task_by_id(task_id)
            if not created_task:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to retrieve created task"
                )
            
            # Get hierarchy info for undo
            hierarchy_info = await task_repository.get_parent_info(task_id)
            
            # Record undo operation with hierarchy info
            await undo_service.record_task_operation(
                "create", None, created_task,
                hierarchy_info_after=hierarchy_info
            )
            
            # Broadcast task creation to WebSocket clients
            await broadcast_task_update("created", {
                "id": created_task.id,
                "uuid": created_task.uuid,
                "title": created_task.title,
                "status": created_task.status.value,
                "parent_id": task_data.parent_id
            })
            
            logger.info(f"Created task {task_id}: {task_data.title}")
            return task_to_response(created_task)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create task"
            )


@router.put(
    "/{task_id}", 
    response_model=TaskResponse,
    summary="Update Task",
    response_description="The updated task with incremented revision"
)
async def update_task(task_id: int, task_data: TaskUpdate) -> TaskResponse:
    """Update an existing task (partial update supported).
    
    Only the fields provided in the request body will be updated.
    The task's **revision** number is automatically incremented for 
    optimistic concurrency control.
    """
    task_repository = get_task_repository()
    db_write_lock = get_db_write_lock()
    undo_service = get_undo_redo_service()
    
    async with db_write_lock:
        try:
            # Get existing task
            existing_task = await task_repository.get_task_by_id(task_id)
            if not existing_task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Task with ID {task_id} not found"
                )
            
            # Make a copy of the task before changes for undo recording
            from copy import deepcopy
            task_before = deepcopy(existing_task)
            
            # Update fields that were provided
            update_data = task_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(existing_task, field, value)
            
            # Increment revision and update timestamp
            existing_task.revision += 1
            existing_task.updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            
            # Update in database
            await task_repository.update_task(existing_task)
            
            # Record undo operation
            await undo_service.record_task_operation("update", task_before, existing_task)
            
            # Broadcast task update to WebSocket clients
            await broadcast_task_update("updated", {
                "id": existing_task.id,
                "uuid": existing_task.uuid,
                "title": existing_task.title,
                "status": existing_task.status.value,
                "changes": update_data
            })
            
            logger.info(f"Updated task {task_id}")
            return task_to_response(existing_task)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating task {task_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update task"
            )


@router.delete(
    "/{task_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Task",
    response_description="No content on success"
)
async def delete_task(
    task_id: int, 
    hard_delete: bool = Query(False, description="If true, permanently delete (cannot be undone)")
) -> None:
    """Delete a task and all its descendants.
    
    - **Soft delete** (default): Marks task as deleted, can be restored via undo
    - **Hard delete**: Permanently removes task and attachments (irreversible)
    
    Both operations cascade to all descendant tasks in the hierarchy.
    """
    task_repository = get_task_repository()
    db_write_lock = get_db_write_lock()
    undo_service = get_undo_redo_service()
    attachment_service = get_attachment_service()
    
    async with db_write_lock:
        try:
            # Check if task exists
            existing_task = await task_repository.get_task_by_id(task_id)
            if not existing_task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Task with ID {task_id} not found"
                )
            
            # Get hierarchy info before deletion for undo
            hierarchy_info = await task_repository.get_parent_info(task_id)
            
            # Get all descendants for undo recording
            descendants = await task_repository.get_descendants(task_id)
            all_tasks = [existing_task] + descendants
            
            # Make copies for undo recording with hierarchy info
            from copy import deepcopy
            tasks_with_hierarchy = []
            for task in all_tasks:
                task_copy = deepcopy(task)
                task_hierarchy = await task_repository.get_parent_info(task.id)
                tasks_with_hierarchy.append((task_copy, task_hierarchy))
            
            if hard_delete:
                # For hard delete, delete attachments for all tasks in the tree
                if attachment_service:
                    for task in all_tasks:
                        attachments = await attachment_service.get_task_attachments(task.id)
                        for attachment in attachments:
                            try:
                                await attachment_service.delete_attachment(attachment["id"])
                                logger.info(f"Deleted attachment {attachment['id']} for task {task.id}")
                            except Exception as att_err:
                                logger.warning(f"Failed to delete attachment {attachment['id']}: {att_err}")
                
                # Hard delete all tasks in the tree (descendants first, then the task itself)
                for task in reversed(all_tasks):
                    await task_repository.hard_delete_task(task.id)
                
                # Note: We intentionally do NOT record undo for hard deletes.
                # Hard delete is explicitly permanent - attachments are deleted and cannot
                # be recovered. Recording undo would create a false expectation that
                # full restoration is possible. Users should use soft delete for recoverable deletion.
                logger.info(f"Hard deleted task {task_id} and {len(descendants)} descendants (permanent, no undo)")
            else:
                # Soft delete: DO NOT delete attachments - they should be preserved for restore
                # Just soft delete the task and all descendants
                deleted_count = await task_repository.soft_delete_task_with_descendants(task_id)
                
                # Record undo operation for each deleted task with hierarchy info
                for task_before, task_hierarchy in tasks_with_hierarchy:
                    await undo_service.record_task_operation(
                        "delete", task_before, None,
                        hierarchy_info_before=task_hierarchy
                    )
                logger.info(f"Soft deleted task {task_id} and {deleted_count - 1} descendants")
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting task {task_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete task"
            )


@router.post(
    "/{task_id}/complete-tree", 
    status_code=status.HTTP_200_OK,
    summary="Complete Task Tree",
    response_description="Operation result with count of updated tasks"
)
async def complete_task_tree(
    task_id: int, 
    complete: bool = Query(True, description="True to complete, False to reopen")
) -> Dict[str, Any]:
    """Complete or reopen a task and all its descendants.
    
    - **complete=true**: Mark task and all subtasks as completed
    - **complete=false**: Reopen task and all subtasks (set to pending)
    
    Useful for completing entire project branches at once.
    """
    task_repository = get_task_repository()
    db_write_lock = get_db_write_lock()
    undo_service = get_undo_redo_service()
    
    async with db_write_lock:
        try:
            # Verify task exists
            task = await task_repository.get_task_by_id(task_id)
            if not task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Task with ID {task_id} not found"
                )
            
            new_status = TaskStatus.COMPLETED if complete else TaskStatus.PENDING
            
            # Get all tasks that will be affected for undo recording
            descendants = await task_repository.get_descendants(task_id)
            all_tasks = [task] + descendants
            
            # Record undo operation with all affected tasks
            from copy import deepcopy
            tasks_before = [deepcopy(t) for t in all_tasks]
            
            # Update all tasks
            updated_count = await task_repository.update_task_status_with_descendants(task_id, new_status)
            
            # Record bulk update for undo (simplified - records as update for each task)
            for task_before in tasks_before:
                task_after = await task_repository.get_task_by_id(task_before.id)
                if task_after and task_before.status != task_after.status:
                    await undo_service.record_task_operation("update", task_before, task_after)
            
            # Broadcast update
            await broadcast_task_update("updated", {
                "id": task_id,
                "status": new_status.value,
                "cascade": True,
                "updated_count": updated_count
            })
            
            status_text = "completed" if complete else "reopened"
            logger.info(f"Cascade {status_text} task {task_id} and {updated_count - 1} descendants")
            
            return {
                "success": True,
                "updated_count": updated_count,
                "status": new_status.value
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in cascade complete for task {task_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to complete task tree"
            )


@router.post(
    "/{task_id}/restore", 
    response_model=TaskResponse,
    summary="Restore Task",
    response_description="The restored task"
)
async def restore_task(task_id: int) -> TaskResponse:
    """Restore a soft-deleted task.
    
    Only works for tasks that were soft-deleted. Hard-deleted tasks cannot be restored.
    """
    task_repository = get_task_repository()
    db_write_lock = get_db_write_lock()
    undo_service = get_undo_redo_service()
    
    async with db_write_lock:
        try:
            # Get the task before restore (in deleted state)
            # Note: We need to get the task including soft-deleted ones
            rows = await task_repository.db_manager.execute_read(
                "SELECT * FROM Task WHERE id = ?", (task_id,)
            )
            if not rows:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Task with ID {task_id} not found"
                )
            
            from copy import deepcopy
            task_before = task_repository._row_to_task(rows[0])
            
            # Get hierarchy info (should still exist for soft-deleted tasks)
            hierarchy_info = await task_repository.get_parent_info(task_id)
            
            await task_repository.restore_task(task_id)
            
            # Get the restored task
            restored_task = await task_repository.get_task_by_id(task_id)
            if not restored_task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Task with ID {task_id} not found after restore"
                )
            
            # Record undo operation with hierarchy info
            await undo_service.record_task_operation(
                "restore", task_before, restored_task,
                hierarchy_info_before=hierarchy_info,
                hierarchy_info_after=hierarchy_info
            )
            
            logger.info(f"Restored task {task_id}")
            return task_to_response(restored_task)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error restoring task {task_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to restore task"
            )


@router.get(
    "/{task_id}/children", 
    response_model=List[TaskResponse],
    summary="Get Task Children",
    response_description="Direct child tasks"
)
async def get_task_children(
    task_id: int,
    order_by: str = Query("created_at", description="Sort order: 'created_at' or 'custom'")
) -> List[TaskResponse]:
    """Get direct children of a task (one level deep only)."""
    try:
        task_repository = get_task_repository()
        order_by_custom = (order_by == "custom")
        children = await task_repository.get_children(task_id, order_by_custom=order_by_custom)
        return [task_to_response(child) for child in children]
    except Exception as e:
        logger.error(f"Error getting children of task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve task children"
        )


@router.get(
    "/{task_id}/descendants", 
    response_model=List[TaskResponse],
    summary="Get Task Descendants",
    response_description="All descendant tasks (all levels)"
)
async def get_task_descendants(task_id: int) -> List[TaskResponse]:
    """Get all descendants of a task (children, grandchildren, etc.)."""
    try:
        task_repository = get_task_repository()
        descendants = await task_repository.get_descendants(task_id)
        return [task_to_response(descendant) for descendant in descendants]
    except Exception as e:
        logger.error(f"Error getting descendants of task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve task descendants"
        )


@router.get(
    "/{task_id}/ancestors", 
    response_model=List[TaskResponse],
    summary="Get Task Ancestors",
    response_description="All ancestor tasks (breadcrumb path to root)"
)
async def get_task_ancestors(task_id: int) -> List[TaskResponse]:
    """Get all ancestors of a task (parent, grandparent, etc. up to root)."""
    try:
        task_repository = get_task_repository()
        ancestors = await task_repository.get_ancestors(task_id)
        return [task_to_response(ancestor) for ancestor in ancestors]
    except Exception as e:
        logger.error(f"Error getting ancestors of task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve task ancestors"
        )


@router.put(
    "/{task_id}/move", 
    response_model=TaskMoveResponse,
    summary="Move Task",
    response_description="Move operation result with affected task count"
)
async def move_task_with_position(task_id: int, request_data: TaskMoveRequest) -> TaskMoveResponse:
    """Move a task to a different parent with optional position.
    
    - Set **new_parent_id** to move under a different task
    - Set **new_parent_id** to null to move to root level
    - Set **position** to specify exact placement among siblings
    - All descendants move with the task
    
    Circular moves (moving a task into its own subtree) are rejected.
    """
    task_repository = get_task_repository()
    db_write_lock = get_db_write_lock()
    undo_service = get_undo_redo_service()
    
    async with db_write_lock:
        try:
            # Get task before move for undo recording
            task_before = await task_repository.get_task_by_id(task_id)
            if not task_before:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Task with ID {task_id} not found"
                )
            
            # Capture hierarchy info BEFORE the move for undo
            parent_info_before = await task_repository.get_parent_info(task_id)
            
            # Validate new parent exists if specified
            if request_data.new_parent_id is not None:
                parent_task = await task_repository.get_task_by_id(request_data.new_parent_id)
                if not parent_task:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Parent task with ID {request_data.new_parent_id} not found"
                    )
            
            # Count descendants (for response)
            descendants = await task_repository.get_descendants(task_id)
            moved_count = len(descendants) + 1  # Include the task itself
            
            # Move the task
            if request_data.position is not None:
                await task_repository.move_task_with_position(
                    task_id, request_data.new_parent_id, request_data.position
                )
            else:
                await task_repository.move_task(task_id, request_data.new_parent_id)
            
            # Get the moved task and new hierarchy info for undo recording
            moved_task = await task_repository.get_task_by_id(task_id)
            if not moved_task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Task with ID {task_id} not found after move"
                )
            parent_info_after = await task_repository.get_parent_info(task_id)
            
            # Record undo operation with hierarchy info
            await undo_service.record_move_operation(
                task_id=task_id,
                parent_info_before=parent_info_before,
                parent_info_after=parent_info_after
            )
            
            # Broadcast task move to WebSocket clients
            await broadcast_task_update("moved", {
                "id": moved_task.id,
                "uuid": moved_task.uuid,
                "title": moved_task.title,
                "new_parent_id": request_data.new_parent_id,
                "position": request_data.position
            })
            
            logger.info(f"Moved task {task_id} to parent {request_data.new_parent_id} at position {request_data.position}")
            return TaskMoveResponse(success=True, moved_task_count=moved_count)
            
        except HTTPException:
            raise
        except ValueError as e:
            # Handle circular move attempt (moving task into its own descendant)
            logger.warning(f"Invalid move operation for task {task_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Error moving task {task_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to move task"
            )


@router.get(
    "/search/{query}", 
    response_model=List[TaskResponse],
    summary="Search Tasks",
    response_description="Tasks matching the search query"
)
async def search_tasks(query: str) -> List[TaskResponse]:
    """Search tasks using full-text search (FTS5).
    
    Searches both task titles and descriptions. For advanced filtering,
    use the `/search/` endpoint in the search API.
    """
    try:
        if not query.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Search query cannot be empty"
            )
        
        task_repository = get_task_repository()
        tasks = await task_repository.search_tasks(query)
        return [task_to_response(task) for task in tasks]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching tasks with query '{query}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search tasks"
        )


@router.post(
    "/bulk", 
    response_model=TaskBulkResponse,
    summary="Bulk Operations",
    response_description="Results for each operation in order"
)
async def bulk_operations(request: TaskBulkRequest) -> TaskBulkResponse:
    """Perform multiple task operations in a single request.
    
    Supported operation types:
    - **create**: Create a new task
    - **update**: Update an existing task by ID
    - **delete**: Delete a task by ID (soft or hard delete)
    
    Operations are executed in order but **not atomically** - partial success is possible.
    """
    task_repository = get_task_repository()
    db_write_lock = get_db_write_lock()
    undo_service = get_undo_redo_service()
    
    async with db_write_lock:
        results = []
        
        for operation in request.operations:
            try:
                op_type = operation.get("type")
                
                if op_type == "create":
                    task_data = TaskCreate(**operation.get("data", {}))
                    task = Task(
                        title=task_data.title,
                        description=task_data.description,
                        recurrence_rrule=task_data.recurrence_rrule,
                        recurrence_start_utc=task_data.recurrence_start_utc,
                        next_due_utc=task_data.next_due_utc,
                        status=task_data.status,
                        priority=task_data.priority,
                    )
                    task_id = await task_repository.create_task(task, task_data.parent_id)
                    results.append({"success": True, "id": task_id, "uuid": task.uuid})
                    
                elif op_type == "update":
                    task_id = operation.get("id")
                    update_data = TaskUpdate(**operation.get("data", {}))
                    
                    existing_task = await task_repository.get_task_by_id(task_id)
                    if not existing_task:
                        results.append({"success": False, "error": {"code": "NOT_FOUND", "message": f"Task {task_id} not found"}})
                        continue
                    
                    # Update fields
                    for field, value in update_data.model_dump(exclude_unset=True).items():
                        setattr(existing_task, field, value)
                    
                    existing_task.revision += 1
                    existing_task.updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    
                    await task_repository.update_task(existing_task)
                    results.append({"success": True, "id": task_id, "uuid": existing_task.uuid})
                    
                elif op_type == "delete":
                    task_id = operation.get("id")
                    hard_delete = operation.get("hard_delete", False)
                    
                    if hard_delete:
                        await task_repository.hard_delete_task(task_id)
                    else:
                        await task_repository.soft_delete_task(task_id)
                    
                    results.append({"success": True, "id": task_id})
                    
                else:
                    results.append({"success": False, "error": {"code": "INVALID_OPERATION", "message": f"Unknown operation type: {op_type}"}})
                    
            except Exception as e:
                logger.error(f"Error in bulk operation: {e}")
                results.append({"success": False, "error": {"code": "OPERATION_FAILED", "message": str(e)}})
        
        return TaskBulkResponse(results=results) 