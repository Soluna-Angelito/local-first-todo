"""Attachment service for Local-First To-Do application.

This module provides secure file attachment functionality including:
- SHA-256 streaming hash computation
- File deduplication
- Security validation (MIME type, extension, filename sanitization)
- Disk quota management
- Content-addressable storage

Security Configuration:
    The following settings control security behavior. Defaults are optimized
    for local-first/air-gapped environments where convenience is prioritized
    over network-facing security:
    
    - BLOCK_EXECUTABLES (default: False)
        When True, blocks .exe, .bat, .vbs, .com, .scr, .pif, .js files
        and files starting with a dot. Enable for network-exposed deployments.
    
    - SKIP_SIGNATURE_VALIDATION (default: True)
        When False, validates file contents match extension (magic bytes).
        Disable for environments where encrypted/custom file formats are used.
    
    - ALLOW_ALL_EXTENSIONS (default: True)
        When False, only allows files with extensions in ALLOWED_EXTENSIONS.
        Useful for restricting uploads to specific document types.

    Base security (always enforced):
    - Path traversal prevention (../ sequences blocked)
    - Windows reserved names blocked (CON, PRN, NUL, COM1-9, LPT1-9)
    - Filename sanitization (dangerous filesystem characters removed)
"""

import asyncio
import hashlib
import logging
import mimetypes
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import BinaryIO, Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone

from local_first_todo.database.models import Blob, Attachment
from local_first_todo.database.manager import DatabaseManager

logger = logging.getLogger(__name__)

# Configuration constants
DEFAULT_MAX_ATTACHMENT_SIZE = 500 * 1024 * 1024  # 500 MB

# Set to False to enable extension whitelist filtering
ALLOW_ALL_EXTENSIONS = True

# Set to True to block executable files (for network-exposed services)
# For local/air-gapped use, this can be False
BLOCK_EXECUTABLES = False

# Set to True to skip file signature validation (magic bytes check)
# Useful for air-gapped/classified environments where files may be encrypted
SKIP_SIGNATURE_VALIDATION = True

# Extension whitelist (only enforced when ALLOW_ALL_EXTENSIONS = False)
ALLOWED_EXTENSIONS = {
    '.txt', '.md', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg',
    '.mp4', '.avi', '.mov', '.mkv', '.webm',
    '.mp3', '.wav', '.ogg', '.flac',
    '.zip', '.tar', '.gz', '.7z', '.rar',
    '.json', '.xml', '.csv', '.log',
    '.py', '.js', '.html', '.css', '.sql'
}

# Base forbidden patterns (always enforced - filesystem safety)
FORBIDDEN_PATTERNS_BASE = [
    r'\.\.[\\/]',  # Path traversal
    r'^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\.|$)',  # Windows reserved names
]

# Additional patterns when BLOCK_EXECUTABLES = True
FORBIDDEN_PATTERNS_EXECUTABLES = [
    r'^\..*',      # Hidden files starting with dot
    r'.*\.(exe|bat|cmd|com|scr|pif|vbs|js)$',  # Executable files
]


@dataclass
class AttachmentUploadResult:
    """Result of an attachment upload operation."""
    
    attachment: Attachment
    blob: Blob
    was_deduplicated: bool
    file_path: Path


@dataclass
class DiskQuotaInfo:
    """Information about disk space and quota."""
    
    total_space: int
    available_space: int
    used_by_attachments: int
    can_upload: bool
    max_upload_size: int


class AttachmentError(Exception):
    """Base exception for attachment operations."""
    pass


class SecurityValidationError(AttachmentError):
    """Raised when file fails security validation."""
    pass


class DiskQuotaExceededError(AttachmentError):
    """Raised when disk quota would be exceeded."""
    pass


class AttachmentNotFoundError(AttachmentError):
    """Raised when attachment is not found."""
    pass


class AttachmentService:
    """Service for managing file attachments with security and deduplication."""
    
    def __init__(
        self, 
        db_manager: DatabaseManager,
        attachments_dir: str = "attachments",
        max_attachment_size: int = DEFAULT_MAX_ATTACHMENT_SIZE
    ) -> None:
        """Initialize the attachment service.
        
        Args:
            db_manager: Database manager instance
            attachments_dir: Directory to store attachment files
            max_attachment_size: Maximum file size in bytes
        """
        self.db_manager = db_manager
        self.attachments_dir = Path(attachments_dir)
        self.max_attachment_size = max_attachment_size
        self._write_lock = asyncio.Lock()
        
        # Ensure attachments directory exists
        self.attachments_dir.mkdir(parents=True, exist_ok=True)
        
        # Set secure permissions on Unix-like systems
        if os.name == 'posix':
            self.attachments_dir.chmod(0o755)
    
    def validate_filename(self, filename: str) -> str:
        """Validate and sanitize a filename.
        
        Preserves Unicode characters (Korean, Chinese, Japanese, etc.) while
        removing potentially dangerous filesystem characters.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename (preserving Unicode letters)
            
        Raises:
            SecurityValidationError: If filename is invalid or dangerous
        """
        if not filename or not filename.strip():
            raise SecurityValidationError("Filename cannot be empty")
        
        # Check for forbidden patterns (base patterns always enforced)
        for pattern in FORBIDDEN_PATTERNS_BASE:
            if re.search(pattern, filename, re.IGNORECASE):
                raise SecurityValidationError(f"Forbidden filename pattern: {filename}")
        
        # Check executable patterns (only if BLOCK_EXECUTABLES is enabled)
        if BLOCK_EXECUTABLES:
            for pattern in FORBIDDEN_PATTERNS_EXECUTABLES:
                if re.search(pattern, filename, re.IGNORECASE):
                    raise SecurityValidationError(f"Forbidden filename pattern: {filename}")
        
        # Sanitize filename: preserve Unicode letters/digits, spaces, dots, hyphens, underscores
        # Remove only filesystem-dangerous characters: / \ : * ? " < > | and control characters
        # This preserves Korean (한글), Chinese (漢字), Japanese (日本語), etc.
        sanitized = re.sub(r'[/\\:*?"<>|\x00-\x1f]', '_', filename)
        
        # Normalize multiple consecutive underscores/spaces
        sanitized = re.sub(r'_+', '_', sanitized)
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        # Remove leading/trailing dots and spaces (Windows doesn't like them)
        sanitized = sanitized.strip('. ')
        
        # Ensure reasonable length (accounting for UTF-8 encoding)
        # Filesystems typically limit to 255 bytes, not characters
        if len(sanitized.encode('utf-8')) > 255:
            base, ext = os.path.splitext(sanitized)
            ext_bytes = len(ext.encode('utf-8'))
            # Truncate base to fit within 255 bytes with extension
            while len(base.encode('utf-8')) + ext_bytes > 255 and base:
                base = base[:-1]
            sanitized = base + ext
        
        # Fallback if filename becomes empty after sanitization
        if not sanitized:
            sanitized = "unnamed_file"
        
        # Check extension against whitelist (if filtering is enabled)
        if not ALLOW_ALL_EXTENSIONS:
            ext = Path(sanitized).suffix.lower()
            if ext and ext not in ALLOWED_EXTENSIONS:
                raise SecurityValidationError(f"File extension not allowed: {ext}")
        
        return sanitized
    
    def validate_mime_type(self, file_path: Path, original_filename: str) -> None:
        """Validate MIME type matches file extension.
        
        Args:
            file_path: Path to the uploaded file
            original_filename: Original filename for extension check
            
        Raises:
            SecurityValidationError: If MIME type doesn't match extension
        """
        # Skip signature validation if disabled (for air-gapped/classified environments)
        if SKIP_SIGNATURE_VALIDATION:
            return
        
        # Get expected MIME type from extension
        expected_mime, _ = mimetypes.guess_type(original_filename)
        
        if not expected_mime:
            return  # Skip validation for unknown extensions
        
        # For now, we'll use a simple heuristic approach since python-magic
        # is not included in our dependencies (per Additional Guidelines)
        # In a production environment, you would use python-magic here
        
        # Basic validation for common file types
        file_ext = Path(original_filename).suffix.lower()
        
        # Read first few bytes to check file signatures
        try:
            with open(file_path, 'rb') as f:
                header = f.read(16)
            
            # Check for common file signatures
            if file_ext in ['.pdf'] and not header.startswith(b'%PDF'):
                raise SecurityValidationError("PDF file signature mismatch")
            elif file_ext in ['.jpg', '.jpeg'] and not header.startswith(b'\xff\xd8\xff'):
                raise SecurityValidationError("JPEG file signature mismatch")
            elif file_ext in ['.png'] and not header.startswith(b'\x89PNG\r\n\x1a\n'):
                raise SecurityValidationError("PNG file signature mismatch")
            elif file_ext in ['.zip'] and not header.startswith(b'PK'):
                raise SecurityValidationError("ZIP file signature mismatch")
                
        except IOError:
            # If we can't read the file, let it pass for now
            pass
    
    async def compute_file_hash(self, file_path: Path) -> Tuple[str, int]:
        """Compute SHA-256 hash and size of a file using streaming.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Tuple of (hex digest, file size in bytes)
        """
        hasher = hashlib.sha256()
        size = 0
        
        # Use async file I/O for large files
        def _hash_file() -> Tuple[str, int]:
            nonlocal size
            with open(file_path, 'rb') as f:
                while chunk := f.read(8192):  # 8KB chunks
                    hasher.update(chunk)
                    size += len(chunk)
            return hasher.hexdigest(), size
        
        # Run in thread pool to avoid blocking
        return await asyncio.to_thread(_hash_file)
    
    async def check_disk_quota(self, upload_size: int) -> DiskQuotaInfo:
        """Check available disk space and quota constraints.
        
        Args:
            upload_size: Size of file to upload
            
        Returns:
            Disk quota information
        """
        # Get disk space information
        stat = shutil.disk_usage(self.attachments_dir)
        total_space = stat.total
        available_space = stat.free
        
        # Calculate space used by attachments
        used_by_attachments = sum(
            f.stat().st_size 
            for f in self.attachments_dir.rglob('*') 
            if f.is_file()
        )
        
        # Calculate remaining quota (max attachment size minus what's already used)
        remaining_quota = max(0, self.max_attachment_size - used_by_attachments)
        
        # Calculate max upload size (consistent logic)
        max_upload_size = min(
            self.max_attachment_size,  # Single file size limit
            available_space,            # Available disk space
            remaining_quota             # Remaining quota
        )
        
        # Check if upload would exceed quota (consistent with max_upload_size logic)
        # Note: 0-byte files are allowed (e.g., placeholder files)
        can_upload = (
            upload_size >= 0 and
            upload_size <= self.max_attachment_size and  # Single file size limit
            upload_size <= available_space and           # Disk space
            upload_size <= remaining_quota               # Total quota limit
        )
        
        return DiskQuotaInfo(
            total_space=total_space,
            available_space=available_space,
            used_by_attachments=used_by_attachments,
            can_upload=can_upload,
            max_upload_size=max(0, max_upload_size)
        )
    
    async def upload_attachment(
        self, 
        task_id: int, 
        file_data: BinaryIO, 
        original_filename: str
    ) -> AttachmentUploadResult:
        """Upload and process a file attachment.
        
        Args:
            task_id: ID of the task to attach file to
            file_data: File data stream
            original_filename: Original filename
            
        Returns:
            Attachment upload result
            
        Raises:
            SecurityValidationError: If file fails security validation
            DiskQuotaExceededError: If disk quota would be exceeded
            AttachmentError: If upload fails
        """
        async with self._write_lock:
            # Validate and sanitize filename
            sanitized_filename = self.validate_filename(original_filename)
            
            # Create temporary file for processing
            temp_file = self.attachments_dir / f"temp_{uuid.uuid4().hex}"
            
            try:
                # Write file data to temporary location
                with open(temp_file, 'wb') as f:
                    while chunk := file_data.read(8192):
                        f.write(chunk)
                
                # Check file size
                file_size = temp_file.stat().st_size
                
                quota_info = await self.check_disk_quota(file_size)
                if not quota_info.can_upload:
                    raise DiskQuotaExceededError(
                        f"Upload would exceed quota. File size: {file_size}, "
                        f"Available: {quota_info.available_space}"
                    )
                
                # Validate MIME type
                self.validate_mime_type(temp_file, sanitized_filename)
                
                # Compute file hash
                file_hash, actual_size = await self.compute_file_hash(temp_file)
                
                # Check if blob already exists (deduplication)
                existing_blob = await self._get_blob(file_hash)
                was_deduplicated = existing_blob is not None
                
                if not existing_blob:
                    # Create new blob record
                    blob = Blob(
                        sha256=file_hash,
                        size_bytes=actual_size
                    )
                    await self._create_blob(blob)
                    
                    # Move file to content-addressable location
                    final_path = self.attachments_dir / file_hash
                    temp_file.rename(final_path)
                    
                    # Set secure permissions
                    if os.name == 'posix':
                        final_path.chmod(0o644)
                else:
                    blob = existing_blob
                    final_path = self.attachments_dir / file_hash
                    # Remove temporary file since we're using existing blob
                    temp_file.unlink()
                
                # Create attachment record
                attachment = Attachment(
                    task_id=task_id,
                    blob_sha256=file_hash,
                    original_filename=sanitized_filename
                )
                
                attachment_id = await self._create_attachment(attachment)
                attachment.id = attachment_id
                
                logger.info(
                    f"Uploaded attachment {attachment_id} for task {task_id}: "
                    f"{sanitized_filename} ({actual_size} bytes, "
                    f"deduplicated: {was_deduplicated})"
                )
                
                return AttachmentUploadResult(
                    attachment=attachment,
                    blob=blob,
                    was_deduplicated=was_deduplicated,
                    file_path=final_path
                )
                
            except Exception:
                # Clean up temporary file on error
                if temp_file.exists():
                    temp_file.unlink()
                raise
    
    async def download_attachment(self, attachment_id: int) -> Tuple[Path, str]:
        """Get file path and filename for downloading an attachment.
        
        Args:
            attachment_id: Attachment ID
            
        Returns:
            Tuple of (file path, original filename)
            
        Raises:
            AttachmentNotFoundError: If attachment is not found
        """
        attachment = await self._get_attachment(attachment_id)
        if not attachment:
            raise AttachmentNotFoundError(f"Attachment {attachment_id} not found")
        
        file_path = self.attachments_dir / attachment.blob_sha256
        if not file_path.exists():
            raise AttachmentNotFoundError(f"Attachment file not found: {file_path}")
        
        return file_path, attachment.original_filename
    
    async def delete_attachment(self, attachment_id: int) -> None:
        """Delete an attachment and clean up blob if no longer referenced.
        
        Args:
            attachment_id: Attachment ID to delete
            
        Raises:
            AttachmentNotFoundError: If attachment does not exist
        """
        async with self._write_lock:
            attachment = await self._get_attachment(attachment_id)
            if not attachment:
                raise AttachmentNotFoundError(f"Attachment with ID {attachment_id} not found")
            
            blob_hash = attachment.blob_sha256
            
            # Delete attachment record
            await self._delete_attachment(attachment_id)
            
            # Check if blob is still referenced by other attachments
            other_attachments = await self._get_attachments_by_blob(blob_hash)
            
            if not other_attachments:
                # No other attachments reference this blob, delete it
                await self._delete_blob(blob_hash)
                
                # Delete physical file
                file_path = self.attachments_dir / blob_hash
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Deleted unreferenced blob file: {blob_hash}")
            
            logger.info(f"Deleted attachment {attachment_id}")
    
    async def get_task_attachments(self, task_id: int) -> List[Dict[str, Any]]:
        """Get all attachments for a task with metadata.
        
        Args:
            task_id: Task ID
            
        Returns:
            List of attachment dictionaries with metadata
        """
        rows = await self.db_manager.execute_read(
            """
            SELECT a.id, a.uuid, a.original_filename, a.created_at,
                   b.size_bytes, b.sha256
            FROM Attachment a
            JOIN Blob b ON a.blob_sha256 = b.sha256
            WHERE a.task_id = ?
            ORDER BY a.created_at
            """,
            (task_id,)
        )
        
        return [
            {
                "id": row["id"],
                "uuid": row["uuid"],
                "filename": row["original_filename"],
                "size_bytes": row["size_bytes"],
                "sha256": row["sha256"],
                "created_at": row["created_at"]
            }
            for row in rows
        ]
    
    async def get_attachment_stats(self) -> Dict[str, Any]:
        """Get statistics about attachments and storage usage.
        
        Returns:
            Dictionary with attachment statistics
        """
        # Get database statistics
        stats_rows = await self.db_manager.execute_read(
            """
            SELECT 
                COUNT(DISTINCT a.id) as attachment_count,
                COUNT(DISTINCT b.sha256) as blob_count,
                SUM(b.size_bytes) as total_size_bytes
            FROM Attachment a
            JOIN Blob b ON a.blob_sha256 = b.sha256
            """
        )
        
        db_stats = stats_rows[0] if stats_rows else {
            "attachment_count": 0, "blob_count": 0, "total_size_bytes": 0
        }
        
        # Get disk usage
        quota_info = await self.check_disk_quota(0)
        
        return {
            "attachment_count": db_stats["attachment_count"] or 0,
            "blob_count": db_stats["blob_count"] or 0,
            "total_size_bytes": db_stats["total_size_bytes"] or 0,
            "disk_usage": {
                "total_space": quota_info.total_space,
                "available_space": quota_info.available_space,
                "used_by_attachments": quota_info.used_by_attachments
            },
            "quota": {
                "max_attachment_size": self.max_attachment_size,
                "max_upload_size": quota_info.max_upload_size
            }
        }
    
    # Private helper methods for database operations
    
    async def _get_blob(self, sha256: str) -> Optional[Blob]:
        """Get blob by SHA-256 hash."""
        rows = await self.db_manager.execute_read(
            "SELECT * FROM Blob WHERE sha256 = ?", (sha256,)
        )
        
        if not rows:
            return None
        
        row = rows[0]
        return Blob(
            sha256=row["sha256"],
            size_bytes=row["size_bytes"],
            created_at=row["created_at"]
        )
    
    async def _create_blob(self, blob: Blob) -> None:
        """Create a new blob record."""
        await self.db_manager.execute_write(
            "INSERT INTO Blob (sha256, size_bytes, created_at) VALUES (?, ?, ?)",
            (blob.sha256, blob.size_bytes, blob.created_at)
        )
    
    async def _delete_blob(self, sha256: str) -> None:
        """Delete a blob record."""
        await self.db_manager.execute_write(
            "DELETE FROM Blob WHERE sha256 = ?", (sha256,)
        )
    
    async def _get_attachment(self, attachment_id: int) -> Optional[Attachment]:
        """Get attachment by ID."""
        rows = await self.db_manager.execute_read(
            "SELECT * FROM Attachment WHERE id = ?", (attachment_id,)
        )
        
        if not rows:
            return None
        
        row = rows[0]
        return Attachment(
            id=row["id"],
            uuid=row["uuid"],
            task_id=row["task_id"],
            blob_sha256=row["blob_sha256"],
            original_filename=row["original_filename"],
            created_at=row["created_at"]
        )
    
    async def _create_attachment(self, attachment: Attachment) -> int:
        """Create a new attachment record and return its ID."""
        cursor = await self.db_manager.execute_write(
            """
            INSERT INTO Attachment (uuid, task_id, blob_sha256, original_filename, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                attachment.uuid, attachment.task_id, attachment.blob_sha256,
                attachment.original_filename, attachment.created_at
            )
        )
        return cursor.lastrowid
    
    async def _delete_attachment(self, attachment_id: int) -> None:
        """Delete an attachment record."""
        await self.db_manager.execute_write(
            "DELETE FROM Attachment WHERE id = ?", (attachment_id,)
        )
    
    async def _get_attachments_by_blob(self, blob_sha256: str) -> List[Attachment]:
        """Get all attachments that reference a specific blob."""
        rows = await self.db_manager.execute_read(
            "SELECT * FROM Attachment WHERE blob_sha256 = ?", (blob_sha256,)
        )
        
        return [
            Attachment(
                id=row["id"],
                uuid=row["uuid"],
                task_id=row["task_id"],
                blob_sha256=row["blob_sha256"],
                original_filename=row["original_filename"],
                created_at=row["created_at"]
            )
            for row in rows
        ] 