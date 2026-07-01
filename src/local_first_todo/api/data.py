"""Data management API endpoints for Local-First To-Do application.

This module provides REST API endpoints for:
- Data export to .tar.gz archives  
- Data import from .tar.gz archives
- Delta synchronization
- Database integrity checks
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from pydantic import BaseModel, Field

from local_first_todo.dependencies import get_database_manager, get_task_repository
from local_first_todo.database.manager import DatabaseManager
from local_first_todo.database.crud import TaskRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data", tags=["data-management"])


# Pydantic models for API requests/responses
class ExportResponse(BaseModel):
    """Response model for data export operations."""
    
    success: bool = Field(description="Whether export succeeded", json_schema_extra={"example": True})
    filename: str = Field(description="Name of the exported archive file", json_schema_extra={"example": "todo-export-2026-02-06.tar.gz"})
    size_bytes: int = Field(description="Size of export file in bytes", json_schema_extra={"example": 1048576})
    exported_at: str = Field(description="Export timestamp (ISO 8601 UTC)", json_schema_extra={"example": "2026-02-06T10:30:00Z"})
    task_count: int = Field(description="Number of tasks exported", json_schema_extra={"example": 150})
    attachment_count: int = Field(description="Number of attachments exported", json_schema_extra={"example": 25})
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "filename": "todo-export-2026-02-06.tar.gz",
                    "size_bytes": 1048576,
                    "exported_at": "2026-02-06T10:30:00Z",
                    "task_count": 150,
                    "attachment_count": 25
                }
            ]
        }
    }


class ImportResponse(BaseModel):
    """Response model for data import operations."""
    
    success: bool = Field(description="Whether import succeeded", json_schema_extra={"example": True})
    imported_at: str = Field(description="Import timestamp (ISO 8601 UTC)", json_schema_extra={"example": "2026-02-06T10:35:00Z"})
    task_count: int = Field(description="Number of tasks imported", json_schema_extra={"example": 150})
    attachment_count: int = Field(description="Number of attachments imported", json_schema_extra={"example": 25})
    conflicts_resolved: int = Field(description="Number of UUID conflicts resolved", json_schema_extra={"example": 3})
    warnings: list[str] = Field(description="Any non-fatal warnings during import", json_schema_extra={"example": ["Skipped 2 duplicate attachments"]})
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "imported_at": "2026-02-06T10:35:00Z",
                    "task_count": 150,
                    "attachment_count": 25,
                    "conflicts_resolved": 3,
                    "warnings": ["Skipped 2 duplicate attachments"]
                }
            ]
        }
    }


class SyncResponse(BaseModel):
    """Response model for delta synchronization."""
    
    since_revision: int = Field(description="The revision number from the request", json_schema_extra={"example": 100})
    current_revision: int = Field(description="Current highest revision in database", json_schema_extra={"example": 105})
    changes: list[Dict[str, Any]] = Field(
        description="List of changes since the requested revision",
        json_schema_extra={"example": [{"type": "update", "task_id": 5, "revision": 101}]}
    )
    has_more: bool = Field(description="True if more changes exist beyond the limit", json_schema_extra={"example": False})
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "since_revision": 100,
                    "current_revision": 105,
                    "changes": [
                        {"type": "update", "task_id": 5, "revision": 101},
                        {"type": "create", "task_id": 10, "revision": 102}
                    ],
                    "has_more": False
                }
            ]
        }
    }


class IntegrityCheckResponse(BaseModel):
    """Response model for database integrity and health checks."""
    
    is_healthy: bool = Field(description="True if database passes all checks", json_schema_extra={"example": True})
    integrity_check: str = Field(description="SQLite PRAGMA integrity_check result", json_schema_extra={"example": "ok"})
    foreign_key_violations: int = Field(description="Count of foreign key constraint violations", json_schema_extra={"example": 0})
    schema_version: int = Field(description="Current database schema version", json_schema_extra={"example": 3})
    expected_version: int = Field(description="Expected schema version for this app version", json_schema_extra={"example": 3})
    tables_present: list[str] = Field(
        description="Database tables found",
        json_schema_extra={"example": ["Task", "TaskClosure", "Attachment", "Blob", "UndoLog", "TaskFTS"]}
    )
    missing_tables: list[str] = Field(
        description="Expected tables that are missing",
        json_schema_extra={"example": []}
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "is_healthy": True,
                    "integrity_check": "ok",
                    "foreign_key_violations": 0,
                    "schema_version": 3,
                    "expected_version": 3,
                    "tables_present": ["Task", "TaskClosure", "Attachment", "Blob", "UndoLog", "TaskFTS"],
                    "missing_tables": []
                }
            ]
        }
    }


@router.post(
    "/export", 
    response_model=ExportResponse, 
    status_code=501,
    summary="Export Data",
    response_description="Export operation result (NOT YET IMPLEMENTED)"
)
async def export_data(
    include_attachments: bool = Query(True, description="Include attachment files in export"),
    db_manager: DatabaseManager = Depends(get_database_manager),
    task_repository: TaskRepository = Depends(get_task_repository)
) -> ExportResponse:
    """Export all application data to a .tar.gz archive.
    
    **Status: Not Yet Implemented** (returns 501)
    
    Planned features:
    - Export all tasks with hierarchy preserved
    - Optionally include attachment files
    - Compatible with import endpoint for backup/restore
    """
    raise HTTPException(
        status_code=501,
        detail={
            "type": "not_implemented",
            "title": "Not Implemented",
            "detail": "Data export functionality is not yet implemented. This feature is planned for a future release.",
            "status": 501
        }
    )


@router.post(
    "/import", 
    response_model=ImportResponse, 
    status_code=501,
    summary="Import Data",
    response_description="Import operation result (NOT YET IMPLEMENTED)"
)
async def import_data(
    file: UploadFile = File(..., description="Archive file (.tar.gz) to import"),
    merge_strategy: str = Query("merge", description="Conflict strategy: 'merge' (combine), 'overwrite' (replace), 'skip' (ignore conflicts)"),
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> ImportResponse:
    """Import data from a .tar.gz archive created by the export endpoint.
    
    **Status: Not Yet Implemented** (returns 501)
    
    Planned merge strategies:
    - **merge**: Combine with existing data, resolve conflicts by UUID
    - **overwrite**: Replace existing tasks with imported ones
    - **skip**: Skip any tasks with conflicting UUIDs
    """
    raise HTTPException(
        status_code=501,
        detail={
            "type": "not_implemented",
            "title": "Not Implemented",
            "detail": "Data import functionality is not yet implemented. This feature is planned for a future release.",
            "status": 501
        }
    )


@router.get(
    "/sync", 
    response_model=SyncResponse,
    summary="Get Sync Delta",
    response_description="Changes since the specified revision"
)
async def get_sync_delta(
    since_revision: int = Query(..., description="Last known revision number from previous sync"),
    limit: int = Query(1000, ge=1, le=10000, description="Maximum changes to return (pagination)"),
    task_repository: TaskRepository = Depends(get_task_repository)
) -> SyncResponse:
    """Get incremental changes since a specific revision for synchronization.
    
    Use this endpoint to sync a client that has been offline:
    1. Store the `current_revision` after each sync
    2. On reconnect, request changes since that revision
    3. If `has_more` is true, continue fetching with updated revision
    
    Note: Full implementation pending. Currently returns revision info only.
    """
    try:
        # This is a placeholder implementation
        # In a full implementation, this would:
        # 1. Query changes since the given revision
        # 2. Format changes as JSON-Patch or similar
        # 3. Include task hierarchy changes
        # 4. Handle revision gaps and resets
        
        # Determine current revision without loading the whole table
        rows = await task_repository.db_manager.execute_read(
            "SELECT COALESCE(MAX(revision), 0) as max_revision FROM Task"
        )
        current_revision = rows[0]["max_revision"] if rows else 0
        
        # Mock changes response
        changes = []
        has_more = False
        
        return SyncResponse(
            since_revision=since_revision,
            current_revision=current_revision,
            changes=changes,
            has_more=has_more
        )
        
    except Exception as e:
        logger.error(f"Sync delta failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get sync delta"
        )


@router.get(
    "/integrity", 
    response_model=IntegrityCheckResponse,
    summary="Check Integrity",
    response_description="Database health and integrity status"
)
async def check_integrity(
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> IntegrityCheckResponse:
    """Check database integrity and schema health.
    
    Performs the following checks:
    - SQLite `PRAGMA integrity_check`
    - Foreign key constraint validation
    - Schema version verification
    - Required tables presence
    
    Use this endpoint to diagnose database issues or verify backup integrity.
    """
    try:
        integrity_status = await db_manager.verify_schema_integrity()
        
        return IntegrityCheckResponse(
            is_healthy=integrity_status["is_healthy"],
            integrity_check=integrity_status["integrity_check"],
            foreign_key_violations=integrity_status["foreign_key_violations"],
            schema_version=integrity_status["schema_version"],
            expected_version=integrity_status["expected_version"],
            tables_present=integrity_status["tables_present"],
            missing_tables=integrity_status["missing_tables"]
        )
        
    except Exception as e:
        logger.error(f"Integrity check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to check database integrity"
        ) 