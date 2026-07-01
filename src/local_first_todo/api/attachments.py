"""Attachment API endpoints for Local-First To-Do application.

This module provides REST API endpoints for:
- File upload with security validation
- File download with proper headers
- Attachment deletion
- Attachment listing and metadata
- Disk quota information
"""

import logging
from typing import List, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from local_first_todo.services.attachment_service import (
    AttachmentService, 
    SecurityValidationError, 
    DiskQuotaExceededError, 
    AttachmentNotFoundError,
    AttachmentError
)
from local_first_todo.dependencies import get_attachment_service, get_task_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/attachments", tags=["attachments"])


# Pydantic models for API responses
class AttachmentInfo(BaseModel):
    """Information about an uploaded attachment."""
    
    id: int = Field(..., description="Unique attachment ID", json_schema_extra={"example": 1})
    uuid: str = Field(..., description="UUID for external references", json_schema_extra={"example": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"})
    filename: str = Field(..., description="Original filename", json_schema_extra={"example": "document.pdf"})
    size_bytes: int = Field(..., description="File size in bytes", json_schema_extra={"example": 102400})
    sha256: str = Field(..., description="SHA-256 hash for content-addressing", json_schema_extra={"example": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"})
    created_at: str = Field(..., description="Upload timestamp (ISO 8601 UTC)", json_schema_extra={"example": "2026-02-06T10:30:00Z"})
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "filename": "document.pdf",
                    "size_bytes": 102400,
                    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                    "created_at": "2026-02-06T10:30:00Z"
                }
            ]
        }
    }


class AttachmentUploadResponse(BaseModel):
    """Response model for successful attachment upload."""
    
    success: bool = Field(..., description="Whether upload succeeded", json_schema_extra={"example": True})
    attachment: AttachmentInfo = Field(..., description="Uploaded attachment details")
    was_deduplicated: bool = Field(..., description="True if file already existed (content-addressed)", json_schema_extra={"example": False})
    message: str = Field(..., description="Human-readable status message", json_schema_extra={"example": "File uploaded successfully"})
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "attachment": {
                        "id": 1,
                        "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "filename": "document.pdf",
                        "size_bytes": 102400,
                        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                        "created_at": "2026-02-06T10:30:00Z"
                    },
                    "was_deduplicated": False,
                    "message": "File uploaded successfully"
                }
            ]
        }
    }


class AttachmentStatsResponse(BaseModel):
    """Response model for attachment storage statistics."""
    
    attachment_count: int = Field(..., description="Total number of attachments", json_schema_extra={"example": 25})
    blob_count: int = Field(..., description="Number of unique file blobs (deduplicated)", json_schema_extra={"example": 20})
    total_size_bytes: int = Field(..., description="Total storage used by blobs", json_schema_extra={"example": 52428800})
    disk_usage: Dict[str, int] = Field(..., description="Disk usage breakdown", json_schema_extra={"example": {"attachments": 52428800, "database": 1048576}})
    quota: Dict[str, int] = Field(..., description="Storage quota limits", json_schema_extra={"example": {"max_file_size": 104857600, "max_total_size": 1073741824}})
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "attachment_count": 25,
                    "blob_count": 20,
                    "total_size_bytes": 52428800,
                    "disk_usage": {"attachments": 52428800, "database": 1048576},
                    "quota": {"max_file_size": 104857600, "max_total_size": 1073741824}
                }
            ]
        }
    }


class ErrorResponse(BaseModel):
    """Error response model following RFC 7807 Problem Details."""
    
    type: str = Field(..., description="Error type URI", json_schema_extra={"example": "task_not_found"})
    title: str = Field(..., description="Short, human-readable title", json_schema_extra={"example": "Task Not Found"})
    detail: str = Field(..., description="Detailed error description", json_schema_extra={"example": "Task with ID 123 does not exist"})
    status: int = Field(..., description="HTTP status code", json_schema_extra={"example": 404})
    instance: Optional[str] = Field(None, description="URI of the specific occurrence", json_schema_extra={"example": "/api/v1/attachments/upload/123"})


@router.post(
    "/upload/{task_id}",
    response_model=AttachmentUploadResponse,
    summary="Upload Attachment",
    response_description="Upload result with attachment metadata",
    responses={
        400: {"model": ErrorResponse, "description": "Security validation failed (dangerous file type)"},
        413: {"model": ErrorResponse, "description": "File too large or disk quota exceeded"},
        404: {"model": ErrorResponse, "description": "Task not found"},
        500: {"model": ErrorResponse, "description": "Upload failed due to server error"}
    }
)
async def upload_attachment(
    task_id: int,
    file: UploadFile = File(..., description="File to upload (max 100MB)"),
    attachment_service: AttachmentService = Depends(get_attachment_service)
) -> AttachmentUploadResponse:
    """Upload a file attachment to a task.
    
    Features:
    - **Content-addressed storage**: Identical files are automatically deduplicated
    - **Security validation**: Dangerous file types are rejected
    - **Disk quota**: Upload fails if quota would be exceeded
    
    Supported file types include documents, images, and common formats.
    Executable files (.exe, .bat, etc.) are blocked for security.
    """
    # Verify task exists
    task_repo = get_task_repository()
    task = await task_repo.get_task_by_id(task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "task_not_found",
                "title": "Task Not Found",
                "detail": f"Task with ID {task_id} does not exist",
                "status": 404
            }
        )
    
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail={
                "type": "invalid_filename",
                "title": "Invalid Filename",
                "detail": "Filename is required",
                "status": 400
            }
        )
    
    try:
        # Stream file directly without loading entire content into memory
        # FastAPI's UploadFile.file is a SpooledTemporaryFile that supports streaming
        # Use the file handle directly instead of reading all bytes into BytesIO
        result = await attachment_service.upload_attachment(
            task_id=task_id,
            file_data=file.file,
            original_filename=file.filename
        )
        
        attachment_info = AttachmentInfo(
            id=result.attachment.id or 0,
            uuid=result.attachment.uuid,
            filename=result.attachment.original_filename,
            size_bytes=result.blob.size_bytes,
            sha256=result.blob.sha256,
            created_at=result.attachment.created_at
        )
        
        message = (
            f"File uploaded successfully"
            f"{' (deduplicated)' if result.was_deduplicated else ''}"
        )
        
        logger.info(f"Uploaded attachment {result.attachment.id} to task {task_id}")
        
        return AttachmentUploadResponse(
            success=True,
            attachment=attachment_info,
            was_deduplicated=result.was_deduplicated,
            message=message
        )
        
    except SecurityValidationError as e:
        logger.warning(f"Security validation failed for upload: {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "type": "security_validation_error",
                "title": "Security Validation Failed",
                "detail": str(e),
                "status": 400
            }
        )
    
    except DiskQuotaExceededError as e:
        logger.warning(f"Disk quota exceeded for upload: {e}")
        raise HTTPException(
            status_code=413,
            detail={
                "type": "quota_exceeded",
                "title": "Disk Quota Exceeded",
                "detail": str(e),
                "status": 413
            }
        )
    
    except AttachmentError as e:
        logger.error(f"Attachment upload failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "type": "upload_failed",
                "title": "Upload Failed",
                "detail": str(e),
                "status": 500
            }
        )


@router.get(
    "/download/{attachment_id}",
    summary="Download Attachment",
    response_description="File content with appropriate headers",
    responses={
        200: {"description": "File content returned as binary stream"},
        404: {"model": ErrorResponse, "description": "Attachment not found"},
        500: {"model": ErrorResponse, "description": "Download failed due to server error"}
    }
)
async def download_attachment(
    attachment_id: int,
    attachment_service: AttachmentService = Depends(get_attachment_service)
) -> FileResponse:
    """Download an attachment file by its ID.
    
    Returns the file with:
    - Original filename in Content-Disposition header
    - Appropriate Content-Type for the file type
    """
    try:
        file_path, original_filename = await attachment_service.download_attachment(attachment_id)
        
        logger.info(f"Downloaded attachment {attachment_id}: {original_filename}")
        
        return FileResponse(
            path=str(file_path),
            filename=original_filename,
            media_type="application/octet-stream"
        )
        
    except AttachmentNotFoundError as e:
        logger.warning(f"Attachment not found for download: {e}")
        raise HTTPException(
            status_code=404,
            detail={
                "type": "attachment_not_found",
                "title": "Attachment Not Found",
                "detail": str(e),
                "status": 404
            }
        )
    
    except Exception as e:
        logger.error(f"Attachment download failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "type": "download_failed",
                "title": "Download Failed",
                "detail": "Failed to download attachment",
                "status": 500
            }
        )


@router.delete(
    "/{attachment_id}",
    summary="Delete Attachment",
    response_description="Deletion confirmation",
    responses={
        200: {"description": "Attachment deleted successfully"},
        404: {"model": ErrorResponse, "description": "Attachment not found"},
        500: {"model": ErrorResponse, "description": "Delete failed due to server error"}
    }
)
async def delete_attachment(
    attachment_id: int,
    attachment_service: AttachmentService = Depends(get_attachment_service)
) -> JSONResponse:
    """Delete an attachment by its ID.
    
    The underlying file blob is only deleted if no other attachments reference it
    (content-addressed deduplication).
    """
    try:
        await attachment_service.delete_attachment(attachment_id)
        
        logger.info(f"Deleted attachment {attachment_id}")
        
        return JSONResponse(
            content={
                "success": True,
                "message": f"Attachment {attachment_id} deleted successfully"
            }
        )
        
    except AttachmentNotFoundError as e:
        logger.warning(f"Attachment not found for deletion: {e}")
        raise HTTPException(
            status_code=404,
            detail={
                "type": "attachment_not_found",
                "title": "Attachment Not Found",
                "detail": str(e),
                "status": 404
            }
        )
    
    except Exception as e:
        logger.error(f"Attachment deletion failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "type": "delete_failed",
                "title": "Delete Failed",
                "detail": "Failed to delete attachment",
                "status": 500
            }
        )


@router.get(
    "/task/{task_id}",
    response_model=List[AttachmentInfo],
    summary="Get Task Attachments",
    response_description="List of attachments for the task",
    responses={
        404: {"model": ErrorResponse, "description": "Task not found"},
        500: {"model": ErrorResponse, "description": "Failed to retrieve attachments"}
    }
)
async def get_task_attachments(
    task_id: int,
    attachment_service: AttachmentService = Depends(get_attachment_service)
) -> List[AttachmentInfo]:
    """Get all attachments associated with a specific task."""
    # Verify task exists
    task_repo = get_task_repository()
    task = await task_repo.get_task_by_id(task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "task_not_found",
                "title": "Task Not Found",
                "detail": f"Task with ID {task_id} does not exist",
                "status": 404
            }
        )
    
    try:
        attachments = await attachment_service.get_task_attachments(task_id)
        
        return [
            AttachmentInfo(
                id=attachment["id"],
                uuid=attachment["uuid"],
                filename=attachment["filename"],
                size_bytes=attachment["size_bytes"],
                sha256=attachment["sha256"],
                created_at=attachment["created_at"]
            )
            for attachment in attachments
        ]
        
    except Exception as e:
        logger.error(f"Failed to get attachments for task {task_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "type": "get_attachments_failed",
                "title": "Failed to Get Attachments",
                "detail": "Failed to retrieve task attachments",
                "status": 500
            }
        )


@router.get(
    "/stats",
    response_model=AttachmentStatsResponse,
    summary="Get Attachment Stats",
    response_description="Storage statistics and usage breakdown",
    responses={
        500: {"model": ErrorResponse, "description": "Failed to retrieve statistics"}
    }
)
async def get_attachment_stats(
    attachment_service: AttachmentService = Depends(get_attachment_service)
) -> AttachmentStatsResponse:
    """Get attachment storage statistics including disk usage and quota information.
    
    Shows deduplication efficiency (blob_count vs attachment_count).
    """
    try:
        stats = await attachment_service.get_attachment_stats()
        
        return AttachmentStatsResponse(
            attachment_count=stats["attachment_count"],
            blob_count=stats["blob_count"],
            total_size_bytes=stats["total_size_bytes"],
            disk_usage=stats["disk_usage"],
            quota=stats["quota"]
        )
        
    except Exception as e:
        logger.error(f"Failed to get attachment statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "type": "stats_failed",
                "title": "Failed to Get Statistics",
                "detail": "Failed to retrieve attachment statistics",
                "status": 500
            }
        )


@router.get(
    "/quota",
    summary="Get Quota Info",
    response_description="Current disk quota and available space",
    responses={
        200: {"description": "Quota information with available space"},
        500: {"model": ErrorResponse, "description": "Failed to retrieve quota information"}
    }
)
async def get_quota_info(
    attachment_service: AttachmentService = Depends(get_attachment_service)
) -> JSONResponse:
    """Get current disk quota and available space for uploads.
    
    Returns:
    - Total disk space
    - Available space
    - Space used by attachments
    - Maximum single file upload size
    """
    try:
        quota_info = await attachment_service.check_disk_quota(0)
        
        return JSONResponse(
            content={
                "total_space": quota_info.total_space,
                "available_space": quota_info.available_space,
                "used_by_attachments": quota_info.used_by_attachments,
                "can_upload": quota_info.can_upload,
                "max_upload_size": quota_info.max_upload_size,
                "max_attachment_size": attachment_service.max_attachment_size
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get quota information: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "type": "quota_info_failed",
                "title": "Failed to Get Quota Information",
                "detail": "Failed to retrieve quota information",
                "status": 500
            }
        ) 