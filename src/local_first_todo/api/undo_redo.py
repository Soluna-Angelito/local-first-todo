"""Undo/Redo API endpoints for Local-First To-Do application.

This module provides REST API endpoints for undo/redo functionality,
including status checking and operation execution.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from local_first_todo.dependencies import get_undo_redo_service, get_db_write_lock
from local_first_todo.services.undo_redo_service import (
    UndoRedoService,
    UndoStackEmptyError,
    RedoStackEmptyError,
    UndoRedoError
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/undo-redo", tags=["undo-redo"])


class UndoRedoResponse(BaseModel):
    """Response model for successful undo/redo operations."""
    
    operation: str = Field(description="Type of operation that was undone/redone", json_schema_extra={"example": "update"})
    entry_id: int = Field(description="ID of the undo log entry", json_schema_extra={"example": 42})
    operations_applied: list[Dict[str, Any]] = Field(
        description="Details of the operations that were applied",
        json_schema_extra={"example": [{"type": "restore_task", "task_id": 5}]}
    )
    message: str = Field(description="Human-readable result message", json_schema_extra={"example": "Successfully undid operation 42"})
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "operation": "update",
                    "entry_id": 42,
                    "operations_applied": [{"type": "restore_task", "task_id": 5, "field": "status", "old_value": "pending", "new_value": "completed"}],
                    "message": "Successfully undid operation 42"
                }
            ]
        }
    }


class UndoRedoStatusResponse(BaseModel):
    """Response model for undo/redo stack status."""
    
    can_undo: bool = Field(description="True if undo is available", json_schema_extra={"example": True})
    can_redo: bool = Field(description="True if redo is available", json_schema_extra={"example": False})
    current_position: int = Field(description="Current position in the undo stack", json_schema_extra={"example": 5})
    total_entries: int = Field(description="Total number of undo entries", json_schema_extra={"example": 10})
    total_size_bytes: int = Field(description="Total size of undo log in bytes", json_schema_extra={"example": 15360})
    max_entries: int = Field(description="Maximum undo entries allowed", json_schema_extra={"example": 1000})
    max_size_mb: int = Field(description="Maximum undo log size in MB", json_schema_extra={"example": 50})
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "can_undo": True,
                    "can_redo": False,
                    "current_position": 5,
                    "total_entries": 10,
                    "total_size_bytes": 15360,
                    "max_entries": 1000,
                    "max_size_mb": 50
                }
            ]
        }
    }


class ErrorResponse(BaseModel):
    """Error response model following RFC 7807 Problem Details."""
    
    type: str = Field(description="Error type URI", json_schema_extra={"example": "urn:local-first-todo:error:undo-stack-empty"})
    title: str = Field(description="Short error title", json_schema_extra={"example": "Undo Stack Empty"})
    status: int = Field(description="HTTP status code", json_schema_extra={"example": 409})
    detail: str = Field(description="Detailed error description", json_schema_extra={"example": "No operations available to undo"})
    instance: str = Field(description="URI of the specific request", json_schema_extra={"example": "/api/v1/undo-redo/undo"})


@router.post(
    "/undo", 
    response_model=UndoRedoResponse,
    summary="Undo Operation",
    response_description="Details of the undone operation",
    responses={
        409: {"description": "Undo stack is empty - nothing to undo"}
    }
)
async def undo_operation(
    undo_service: UndoRedoService = Depends(get_undo_redo_service)
) -> UndoRedoResponse:
    """Undo the most recent task operation.
    
    Supported operations:
    - Task create (deletes the task)
    - Task update (reverts to previous values)
    - Task delete (restores the task)
    - Task move (moves back to original parent)
    - Task reorder (restores previous order)
    
    Returns 409 Conflict if undo stack is empty.
    """
    db_write_lock = get_db_write_lock()
    
    async with db_write_lock:
        try:
            result = await undo_service.undo()
            
            return UndoRedoResponse(
                operation=result["operation"],
                entry_id=result["entry_id"],
                operations_applied=result["operations_applied"],
                message=f"Successfully undid operation {result['entry_id']}"
            )
        
        except UndoStackEmptyError as e:
            logger.warning("Undo attempted with empty stack")
            raise HTTPException(
                status_code=409,
                detail={
                    "type": "urn:local-first-todo:error:undo-stack-empty",
                    "title": "Undo Stack Empty",
                    "status": 409,
                    "detail": str(e),
                    "instance": "/api/v1/undo-redo/undo"
                }
            )
        
        except UndoRedoError as e:
            logger.error(f"Undo operation failed: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "type": "urn:local-first-todo:error:undo-failed",
                    "title": "Undo Operation Failed",
                    "status": 500,
                    "detail": str(e),
                    "instance": "/api/v1/undo-redo/undo"
                }
            )


@router.post(
    "/redo", 
    response_model=UndoRedoResponse,
    summary="Redo Operation",
    response_description="Details of the redone operation",
    responses={
        409: {"description": "Redo stack is empty - nothing to redo"}
    }
)
async def redo_operation(
    undo_service: UndoRedoService = Depends(get_undo_redo_service)
) -> UndoRedoResponse:
    """Redo a previously undone operation.
    
    Only available after an undo. The redo stack is cleared when a new
    operation is performed (standard undo/redo behavior).
    
    Returns 409 Conflict if redo stack is empty.
    """
    db_write_lock = get_db_write_lock()
    
    async with db_write_lock:
        try:
            result = await undo_service.redo()
            
            return UndoRedoResponse(
                operation=result["operation"],
                entry_id=result["entry_id"],
                operations_applied=result["operations_applied"],
                message=f"Successfully redid operation {result['entry_id']}"
            )
        
        except RedoStackEmptyError as e:
            logger.warning("Redo attempted with empty stack")
            raise HTTPException(
                status_code=409,
                detail={
                    "type": "urn:local-first-todo:error:redo-stack-empty",
                    "title": "Redo Stack Empty",
                    "status": 409,
                    "detail": str(e),
                    "instance": "/api/v1/undo-redo/redo"
                }
            )
        
        except UndoRedoError as e:
            logger.error(f"Redo operation failed: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "type": "urn:local-first-todo:error:redo-failed",
                    "title": "Redo Operation Failed",
                    "status": 500,
                    "detail": str(e),
                    "instance": "/api/v1/undo-redo/redo"
                }
            )


@router.get(
    "/status", 
    response_model=UndoRedoStatusResponse,
    summary="Get Undo/Redo Status",
    response_description="Current undo/redo availability and statistics"
)
async def get_undo_redo_status(
    undo_service: UndoRedoService = Depends(get_undo_redo_service)
) -> UndoRedoStatusResponse:
    """Get the current undo/redo stack status.
    
    Use this to:
    - Enable/disable undo/redo buttons in UI
    - Show undo history count
    - Monitor undo log storage usage
    """
    try:
        status = await undo_service.get_undo_status()
        
        return UndoRedoStatusResponse(
            can_undo=status["can_undo"],
            can_redo=status["can_redo"],
            current_position=status["current_position"],
            total_entries=status["total_entries"],
            total_size_bytes=status["total_size_bytes"],
            max_entries=status["max_entries"],
            max_size_mb=status["max_size_mb"]
        )
    
    except Exception as e:
        logger.error(f"Failed to get undo/redo status: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "type": "urn:local-first-todo:error:status-failed",
                "title": "Status Retrieval Failed",
                "status": 500,
                "detail": str(e),
                "instance": "/api/v1/undo-redo/status"
            }
        ) 