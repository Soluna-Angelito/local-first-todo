#!/usr/bin/env python3
"""
Comprehensive Test Suite for Local-First To-Do Application.

This script performs thorough testing of all components:
1. Database operations and migrations
2. Task CRUD operations with hierarchy
3. Undo/Redo operations including hierarchy restoration
4. Attachment upload, download, and management
5. Search and filtering functionality
6. WebSocket real-time communication
7. API endpoint contracts
8. Edge cases and error handling

Usage:
    python scripts/run_comprehensive_tests.py

The test creates temporary databases and directories, runs all tests,
and provides a detailed summary report.
"""

import asyncio
import tempfile
import os
import sys
import logging
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from io import BytesIO
from copy import deepcopy

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Fix Windows console encoding for Unicode
import sys
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python < 3.7 fallback
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# Import testing modules
try:
    from fastapi.testclient import TestClient
    from local_first_todo.main import create_app
    from local_first_todo.database.manager import DatabaseManager
    from local_first_todo.database.crud import TaskRepository
    from local_first_todo.database.models import Task, TaskStatus, Blob, Attachment
    from local_first_todo.services.attachment_service import AttachmentService
    from local_first_todo.services.undo_redo_service import UndoRedoService
    from local_first_todo.services.search_service import SearchService, SearchFilters, SortBy, SortOrder
    from local_first_todo import dependencies
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    logger.error("Make sure you have installed the project with: pip install -e .")
    sys.exit(1)


class TestResult:
    """Simple test result tracker."""
    
    def __init__(self):
        self.results: Dict[str, List[Dict[str, Any]]] = {}
        self.total_passed = 0
        self.total_failed = 0
    
    def add(self, category: str, test_name: str, passed: bool, message: str = ""):
        """Add a test result."""
        if category not in self.results:
            self.results[category] = []
        
        self.results[category].append({
            "name": test_name,
            "passed": passed,
            "message": message
        })
        
        if passed:
            self.total_passed += 1
        else:
            self.total_failed += 1
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 80)
        print("COMPREHENSIVE TEST RESULTS")
        print("=" * 80)
        
        for category, tests in self.results.items():
            passed = sum(1 for t in tests if t["passed"])
            total = len(tests)
            status = "✓" if passed == total else "✗"
            print(f"\n{status} {category}: {passed}/{total} passed")
            
            for test in tests:
                icon = "  ✓" if test["passed"] else "  ✗"
                print(f"{icon} {test['name']}")
                if test["message"] and not test["passed"]:
                    print(f"      Error: {test['message']}")
        
        print("\n" + "=" * 80)
        print(f"TOTAL: {self.total_passed}/{self.total_passed + self.total_failed} tests passed")
        
        if self.total_failed == 0:
            print("🎉 ALL TESTS PASSED!")
        else:
            print(f"⚠️  {self.total_failed} tests failed")
        print("=" * 80)
        
        return self.total_failed == 0


class ComprehensiveTestRunner:
    """Comprehensive test runner for all components."""
    
    def __init__(self):
        self.results = TestResult()
        self.db_manager: Optional[DatabaseManager] = None
        self.task_repo: Optional[TaskRepository] = None
        self.undo_service: Optional[UndoRedoService] = None
        self.search_service: Optional[SearchService] = None
        self.attachment_service: Optional[AttachmentService] = None
        self.temp_db_path: Optional[str] = None
        self.temp_attachments_dir: Optional[str] = None
        self.client: Optional[TestClient] = None
    
    async def setup(self):
        """Set up test environment."""
        logger.info("Setting up test environment...")
        
        # Create temporary database
        fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        # Create temporary attachments directory
        self.temp_attachments_dir = tempfile.mkdtemp()
        
        # Initialize database manager
        self.db_manager = DatabaseManager(self.temp_db_path)
        await self.db_manager.initialize()
        
        # Initialize services
        self.task_repo = TaskRepository(self.db_manager)
        self.undo_service = UndoRedoService(self.db_manager, max_undo_entries=100, max_undo_size_mb=10)
        await self.undo_service.initialize()
        self.search_service = SearchService(self.db_manager)
        self.attachment_service = AttachmentService(
            self.db_manager,
            self.temp_attachments_dir,
            max_attachment_size=10 * 1024 * 1024  # 10 MB for tests
        )
        
        # Set up FastAPI dependencies
        dependencies.set_database_manager(self.db_manager)
        dependencies.set_task_repository(self.task_repo)
        dependencies.set_db_write_lock(asyncio.Lock())
        dependencies.set_undo_redo_service(self.undo_service)
        dependencies.set_search_service(self.search_service)
        dependencies.set_attachment_service(self.attachment_service)
        
        # Create test client
        app = create_app()
        self.client = TestClient(app)
        
        logger.info("✓ Test environment ready")
    
    async def cleanup(self):
        """Clean up test environment."""
        if self.client:
            self.client.close()
        if self.db_manager:
            await self.db_manager.close()
        if self.temp_db_path and os.path.exists(self.temp_db_path):
            os.unlink(self.temp_db_path)
        if self.temp_attachments_dir and os.path.exists(self.temp_attachments_dir):
            shutil.rmtree(self.temp_attachments_dir, ignore_errors=True)
        logger.info("✓ Test environment cleaned up")
    
    # =========================================================================
    # Database Tests
    # =========================================================================
    
    async def test_database_operations(self):
        """Test database CRUD operations."""
        logger.info("Testing Database Operations...")
        
        # Test task creation
        try:
            task = Task(
                title="Test Task",
                description="Test description",
                status=TaskStatus.PENDING,
                priority=3
            )
            task_id = await self.task_repo.create_task(task)
            assert task_id is not None, "Task ID should not be None"
            self.results.add("Database", "Create Task", True)
        except Exception as e:
            self.results.add("Database", "Create Task", False, str(e))
            return
        
        # Test task retrieval
        try:
            retrieved = await self.task_repo.get_task_by_id(task_id)
            assert retrieved is not None, "Retrieved task should not be None"
            assert retrieved.title == "Test Task", "Task title mismatch"
            self.results.add("Database", "Get Task by ID", True)
        except Exception as e:
            self.results.add("Database", "Get Task by ID", False, str(e))
        
        # Test task update
        try:
            retrieved.title = "Updated Title"
            retrieved.revision += 1
            retrieved.updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            await self.task_repo.update_task(retrieved)
            
            updated = await self.task_repo.get_task_by_id(task_id)
            assert updated.title == "Updated Title", "Task title not updated"
            self.results.add("Database", "Update Task", True)
        except Exception as e:
            self.results.add("Database", "Update Task", False, str(e))
        
        # Test soft delete
        try:
            await self.task_repo.soft_delete_task(task_id)
            deleted = await self.task_repo.get_task_by_id(task_id)
            assert deleted is None, "Soft deleted task should not be retrieved"
            self.results.add("Database", "Soft Delete Task", True)
        except Exception as e:
            self.results.add("Database", "Soft Delete Task", False, str(e))
        
        # Test task restore
        try:
            await self.task_repo.restore_task(task_id)
            restored = await self.task_repo.get_task_by_id(task_id)
            assert restored is not None, "Restored task should be retrievable"
            self.results.add("Database", "Restore Task", True)
        except Exception as e:
            self.results.add("Database", "Restore Task", False, str(e))
    
    # =========================================================================
    # Hierarchy Tests
    # =========================================================================
    
    async def test_hierarchy_operations(self):
        """Test hierarchical task operations."""
        logger.info("Testing Hierarchy Operations...")
        
        # Create parent task
        parent = Task(title="Parent Task", status=TaskStatus.PENDING)
        parent_id = await self.task_repo.create_task(parent)
        
        # Create child task
        try:
            child = Task(title="Child Task", status=TaskStatus.PENDING)
            child_id = await self.task_repo.create_task(child, parent_id=parent_id)
            
            # Verify child is under parent
            children = await self.task_repo.get_children(parent_id)
            assert len(children) == 1, "Parent should have 1 child"
            assert children[0].id == child_id, "Child ID mismatch"
            self.results.add("Hierarchy", "Create Child Task", True)
        except Exception as e:
            self.results.add("Hierarchy", "Create Child Task", False, str(e))
            return
        
        # Test ancestors
        try:
            ancestors = await self.task_repo.get_ancestors(child_id)
            assert len(ancestors) >= 1, "Child should have at least 1 ancestor"
            assert ancestors[0].id == parent_id, "First ancestor should be parent"
            self.results.add("Hierarchy", "Get Ancestors", True)
        except Exception as e:
            self.results.add("Hierarchy", "Get Ancestors", False, str(e))
        
        # Create another parent to test move
        parent2 = Task(title="Parent 2", status=TaskStatus.PENDING)
        parent2_id = await self.task_repo.create_task(parent2)
        
        # Test move task
        try:
            await self.task_repo.move_task(child_id, parent2_id)
            
            # Verify child moved to new parent
            old_children = await self.task_repo.get_children(parent_id)
            new_children = await self.task_repo.get_children(parent2_id)
            
            assert len(old_children) == 0, "Old parent should have no children"
            assert len(new_children) == 1, "New parent should have 1 child"
            self.results.add("Hierarchy", "Move Task to New Parent", True)
        except Exception as e:
            self.results.add("Hierarchy", "Move Task to New Parent", False, str(e))
        
        # Test move to root
        try:
            await self.task_repo.move_task(child_id, None)
            
            root_tasks = await self.task_repo.get_root_tasks()
            root_ids = [t.id for t in root_tasks]
            assert child_id in root_ids, "Moved task should be at root"
            self.results.add("Hierarchy", "Move Task to Root", True)
        except Exception as e:
            self.results.add("Hierarchy", "Move Task to Root", False, str(e))
        
        # Test prevent circular move
        try:
            # Create grandchild
            child2 = Task(title="Child Under Parent2", status=TaskStatus.PENDING)
            child2_id = await self.task_repo.create_task(child2, parent_id=parent2_id)
            
            # Try to move parent2 into its own child (should fail)
            try:
                await self.task_repo.move_task(parent2_id, child2_id)
                self.results.add("Hierarchy", "Prevent Circular Move", False, "Should have raised ValueError")
            except ValueError as e:
                assert "descendant" in str(e).lower(), "Error should mention descendant"
                self.results.add("Hierarchy", "Prevent Circular Move", True)
        except Exception as e:
            self.results.add("Hierarchy", "Prevent Circular Move", False, str(e))
    
    # =========================================================================
    # Undo/Redo Tests with Hierarchy
    # =========================================================================
    
    async def test_undo_redo_with_hierarchy(self):
        """Test undo/redo operations including hierarchy restoration."""
        logger.info("Testing Undo/Redo with Hierarchy...")
        
        # Create a task and record for undo
        task = Task(title="Undo Test Task", status=TaskStatus.PENDING, priority=2)
        task_id = await self.task_repo.create_task(task)
        created_task = await self.task_repo.get_task_by_id(task_id)
        
        # Get hierarchy info
        hierarchy_info = await self.task_repo.get_parent_info(task_id)
        
        # Record create operation
        try:
            await self.undo_service.record_task_operation(
                "create", None, created_task,
                hierarchy_info_after=hierarchy_info
            )
            
            status = await self.undo_service.get_undo_status()
            assert status["can_undo"], "Should be able to undo after create"
            self.results.add("Undo/Redo", "Record Create Operation", True)
        except Exception as e:
            self.results.add("Undo/Redo", "Record Create Operation", False, str(e))
            return
        
        # Undo create (should delete the task)
        try:
            result = await self.undo_service.undo()
            assert result["operation"] == "undo", "Should be undo operation"
            
            # Task should be deleted
            deleted_task = await self.task_repo.get_task_by_id(task_id)
            assert deleted_task is None, "Task should be deleted after undo create"
            
            status = await self.undo_service.get_undo_status()
            assert status["can_redo"], "Should be able to redo"
            self.results.add("Undo/Redo", "Undo Create Operation", True)
        except Exception as e:
            self.results.add("Undo/Redo", "Undo Create Operation", False, str(e))
            return
        
        # Redo create (should restore the task)
        try:
            result = await self.undo_service.redo()
            assert result["operation"] == "redo", "Should be redo operation"
            
            # Task should be restored
            restored_task = await self.task_repo.get_task_by_id(task_id)
            assert restored_task is not None, "Task should exist after redo"
            assert restored_task.title == "Undo Test Task", "Task title should be restored"
            self.results.add("Undo/Redo", "Redo Create Operation", True)
        except Exception as e:
            self.results.add("Undo/Redo", "Redo Create Operation", False, str(e))
        
        # Test undo with hierarchy (move operation)
        try:
            # Create parent and move task under it
            parent = Task(title="Undo Parent", status=TaskStatus.PENDING)
            parent_id = await self.task_repo.create_task(parent)
            
            # Get parent info before move
            parent_info_before = await self.task_repo.get_parent_info(task_id)
            
            # Move task under parent
            await self.task_repo.move_task(task_id, parent_id)
            
            # Get parent info after move
            parent_info_after = await self.task_repo.get_parent_info(task_id)
            
            # Record move operation
            await self.undo_service.record_move_operation(
                task_id,
                parent_info_before,
                parent_info_after
            )
            
            # Undo the move
            await self.undo_service.undo()
            
            # Task should be back at root
            current_parent_info = await self.task_repo.get_parent_info(task_id)
            assert current_parent_info["parent_id"] == parent_info_before["parent_id"], \
                "Task should be at original location after undo move"
            
            self.results.add("Undo/Redo", "Undo Move with Hierarchy", True)
        except Exception as e:
            self.results.add("Undo/Redo", "Undo Move with Hierarchy", False, str(e))
        
        # Test undo restore (should soft-delete, not hard delete)
        try:
            # Soft delete a task
            test_task = Task(title="Soft Delete Undo Test", status=TaskStatus.PENDING)
            test_task_id = await self.task_repo.create_task(test_task)
            created = await self.task_repo.get_task_by_id(test_task_id)
            
            await self.task_repo.soft_delete_task(test_task_id)
            
            # Get task in deleted state (directly from DB)
            rows = await self.db_manager.execute_read(
                "SELECT * FROM Task WHERE id = ?", (test_task_id,)
            )
            task_before_restore = self.task_repo._row_to_task(rows[0])
            hierarchy_info = await self.task_repo.get_parent_info(test_task_id)
            
            # Restore the task
            await self.task_repo.restore_task(test_task_id)
            restored = await self.task_repo.get_task_by_id(test_task_id)
            
            # Record restore operation
            await self.undo_service.record_task_operation(
                "restore", task_before_restore, restored,
                hierarchy_info_before=hierarchy_info,
                hierarchy_info_after=hierarchy_info
            )
            
            # Undo the restore (should soft-delete again, not hard delete)
            await self.undo_service.undo()
            
            # Task should still exist in DB but be deleted
            rows = await self.db_manager.execute_read(
                "SELECT deleted_at FROM Task WHERE id = ?", (test_task_id,)
            )
            assert len(rows) == 1, "Task should still exist in database"
            assert rows[0]["deleted_at"] is not None, "Task should be soft-deleted"
            
            self.results.add("Undo/Redo", "Undo Restore (Soft Delete)", True)
        except Exception as e:
            self.results.add("Undo/Redo", "Undo Restore (Soft Delete)", False, str(e))
    
    # =========================================================================
    # Attachment Tests
    # =========================================================================
    
    async def test_attachment_operations(self):
        """Test attachment upload, download, and management."""
        logger.info("Testing Attachment Operations...")
        
        # Create a task for attachments
        task = Task(title="Attachment Test Task", status=TaskStatus.PENDING)
        task_id = await self.task_repo.create_task(task)
        
        # Test file upload
        try:
            file_content = b"Test file content for attachment testing"
            file_stream = BytesIO(file_content)
            
            result = await self.attachment_service.upload_attachment(
                task_id=task_id,
                file_data=file_stream,
                original_filename="test_file.txt"
            )
            
            assert result.attachment is not None, "Attachment should be created"
            assert result.blob is not None, "Blob should be created"
            assert result.blob.size_bytes == len(file_content), "File size mismatch"
            attachment_id = result.attachment.id
            
            self.results.add("Attachments", "Upload Attachment", True)
        except Exception as e:
            self.results.add("Attachments", "Upload Attachment", False, str(e))
            return
        
        # Test download
        try:
            file_path, filename = await self.attachment_service.download_attachment(attachment_id)
            
            assert file_path.exists(), "Downloaded file should exist"
            with open(file_path, 'rb') as f:
                downloaded_content = f.read()
            assert downloaded_content == file_content, "Downloaded content should match uploaded"
            
            self.results.add("Attachments", "Download Attachment", True)
        except Exception as e:
            self.results.add("Attachments", "Download Attachment", False, str(e))
        
        # Test deduplication
        try:
            # Upload same content with different name
            file_stream = BytesIO(file_content)
            result2 = await self.attachment_service.upload_attachment(
                task_id=task_id,
                file_data=file_stream,
                original_filename="duplicate_file.txt"
            )
            
            assert result2.was_deduplicated, "Second upload should be deduplicated"
            assert result2.blob.sha256 == result.blob.sha256, "Hash should match"
            
            self.results.add("Attachments", "Deduplication", True)
        except Exception as e:
            self.results.add("Attachments", "Deduplication", False, str(e))
        
        # Test get task attachments
        try:
            attachments = await self.attachment_service.get_task_attachments(task_id)
            assert len(attachments) == 2, "Should have 2 attachments"
            
            filenames = [a["filename"] for a in attachments]
            assert "test_file.txt" in filenames, "First file should be listed"
            assert "duplicate_file.txt" in filenames, "Second file should be listed"
            
            self.results.add("Attachments", "Get Task Attachments", True)
        except Exception as e:
            self.results.add("Attachments", "Get Task Attachments", False, str(e))
        
        # Test delete attachment
        try:
            await self.attachment_service.delete_attachment(attachment_id)
            
            # Should not be downloadable
            try:
                await self.attachment_service.download_attachment(attachment_id)
                self.results.add("Attachments", "Delete Attachment", False, "Should have raised error")
            except Exception:
                self.results.add("Attachments", "Delete Attachment", True)
        except Exception as e:
            self.results.add("Attachments", "Delete Attachment", False, str(e))
        
        # Test security validation
        try:
            # Path traversal should be blocked
            file_stream = BytesIO(b"malicious content")
            try:
                await self.attachment_service.upload_attachment(
                    task_id=task_id,
                    file_data=file_stream,
                    original_filename="../../../etc/passwd"
                )
                self.results.add("Attachments", "Security: Path Traversal Block", False, "Should have blocked path traversal")
            except Exception as e:
                if "forbidden" in str(e).lower() or "security" in str(e).lower():
                    self.results.add("Attachments", "Security: Path Traversal Block", True)
                else:
                    self.results.add("Attachments", "Security: Path Traversal Block", False, str(e))
        except Exception as e:
            self.results.add("Attachments", "Security: Path Traversal Block", False, str(e))
    
    # =========================================================================
    # Search Tests
    # =========================================================================
    
    async def test_search_operations(self):
        """Test search and filtering functionality."""
        logger.info("Testing Search Operations...")
        
        # Create test tasks with various properties
        tasks_data = [
            {"title": "High Priority Meeting", "priority": 1, "status": TaskStatus.PENDING},
            {"title": "Low Priority Email", "priority": 4, "status": TaskStatus.PENDING},
            {"title": "Completed Report", "priority": 2, "status": TaskStatus.COMPLETED},
            {"title": "Overdue Task", "priority": 3, "status": TaskStatus.PENDING,
             "next_due_utc": (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")},
        ]
        
        for data in tasks_data:
            task = Task(
                title=data["title"],
                status=data["status"],
                priority=data.get("priority"),
                next_due_utc=data.get("next_due_utc")
            )
            await self.task_repo.create_task(task)
        
        # Test full-text search
        try:
            results = await self.search_service.search_tasks(query="Meeting")
            assert len(results) >= 1, "Should find at least 1 task"
            assert any(t.title == "High Priority Meeting" for t in results), "Should find Meeting task"
            self.results.add("Search", "Full-Text Search", True)
        except Exception as e:
            self.results.add("Search", "Full-Text Search", False, str(e))
        
        # Test status filter
        try:
            filters = SearchFilters(statuses=[TaskStatus.COMPLETED])
            results = await self.search_service.search_tasks(filters=filters)
            
            assert len(results) >= 1, "Should find completed tasks"
            assert all(t.status == TaskStatus.COMPLETED for t in results), "All should be completed"
            self.results.add("Search", "Filter by Status", True)
        except Exception as e:
            self.results.add("Search", "Filter by Status", False, str(e))
        
        # Test priority filter
        try:
            filters = SearchFilters(
                statuses=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED],
                max_priority=2  # High priority tasks (1 and 2)
            )
            results = await self.search_service.search_tasks(filters=filters)
            
            assert len(results) >= 1, "Should find high priority tasks"
            assert all(t.priority is not None and t.priority <= 2 for t in results if t.priority), \
                "All should be high priority"
            self.results.add("Search", "Filter by Priority", True)
        except Exception as e:
            self.results.add("Search", "Filter by Priority", False, str(e))
        
        # Test sorting
        try:
            results = await self.search_service.search_tasks(
                sort_by=SortBy.PRIORITY,
                sort_order=SortOrder.ASC  # Urgent (1) first
            )
            
            priorities = [t.priority for t in results if t.priority is not None]
            if len(priorities) > 1:
                assert priorities == sorted(priorities), "Should be sorted by priority ascending"
            self.results.add("Search", "Sort by Priority", True)
        except Exception as e:
            self.results.add("Search", "Sort by Priority", False, str(e))
        
        # Test dashboard
        try:
            dashboard = await self.search_service.get_dashboard_tasks()
            
            assert "overdue" in dashboard, "Dashboard should have overdue section"
            assert "today" in dashboard, "Dashboard should have today section"
            assert "high_priority" in dashboard, "Dashboard should have high_priority section"
            
            self.results.add("Search", "Dashboard Data", True)
        except Exception as e:
            self.results.add("Search", "Dashboard Data", False, str(e))
    
    # =========================================================================
    # API Tests
    # =========================================================================
    
    async def test_api_endpoints(self):
        """Test REST API endpoints."""
        logger.info("Testing API Endpoints...")
        
        # Health check
        try:
            response = self.client.get("/health")
            assert response.status_code == 200, f"Health check failed: {response.status_code}"
            self.results.add("API", "Health Check", True)
        except Exception as e:
            self.results.add("API", "Health Check", False, str(e))
        
        # Create task via API
        try:
            task_data = {
                "title": "API Test Task",
                "description": "Created via API",
                "status": "pending",
                "priority": 3
            }
            response = self.client.post("/api/v1/tasks/", json=task_data)
            assert response.status_code == 201, f"Create task failed: {response.status_code}"
            
            created = response.json()
            task_id = created["id"]
            assert created["title"] == task_data["title"], "Title mismatch"
            self.results.add("API", "POST Create Task", True)
        except Exception as e:
            self.results.add("API", "POST Create Task", False, str(e))
            return
        
        # Get task via API
        try:
            response = self.client.get(f"/api/v1/tasks/{task_id}")
            assert response.status_code == 200, f"Get task failed: {response.status_code}"
            self.results.add("API", "GET Task by ID", True)
        except Exception as e:
            self.results.add("API", "GET Task by ID", False, str(e))
        
        # Update task via API
        try:
            update_data = {"title": "Updated API Task", "priority": 1}
            response = self.client.put(f"/api/v1/tasks/{task_id}", json=update_data)
            assert response.status_code == 200, f"Update task failed: {response.status_code}"
            
            updated = response.json()
            assert updated["title"] == update_data["title"], "Title not updated"
            self.results.add("API", "PUT Update Task", True)
        except Exception as e:
            self.results.add("API", "PUT Update Task", False, str(e))
        
        # Get task tree via API
        try:
            response = self.client.get("/api/v1/tasks/tree?order_by=custom")
            if response.status_code != 200:
                logger.warning(f"Get tree response: {response.text}")
            assert response.status_code == 200, f"Get tree failed: {response.status_code}"
            
            tree = response.json()
            assert "tasks" in tree, "Tree should have tasks"
            assert "total_count" in tree, "Tree should have total_count"
            self.results.add("API", "GET Task Tree (Batch)", True)
        except Exception as e:
            self.results.add("API", "GET Task Tree (Batch)", False, str(e))
        
        # Test hierarchical API
        try:
            # Create parent
            parent_resp = self.client.post("/api/v1/tasks/", json={"title": "API Parent"})
            parent_id = parent_resp.json()["id"]
            
            # Create child
            child_resp = self.client.post("/api/v1/tasks/", json={"title": "API Child", "parent_id": parent_id})
            child_id = child_resp.json()["id"]
            
            # Get children
            children_resp = self.client.get(f"/api/v1/tasks/{parent_id}/children")
            assert children_resp.status_code == 200, "Get children failed"
            children = children_resp.json()
            assert any(c["id"] == child_id for c in children), "Child not found"
            
            # Move task
            move_resp = self.client.put(f"/api/v1/tasks/{child_id}/move", json={"new_parent_id": None})
            assert move_resp.status_code == 200, f"Move failed: {move_resp.status_code}"
            
            self.results.add("API", "Hierarchical Operations", True)
        except Exception as e:
            self.results.add("API", "Hierarchical Operations", False, str(e))
        
        # Test undo/redo API
        try:
            status_resp = self.client.get("/api/v1/undo-redo/status")
            assert status_resp.status_code == 200, "Get undo status failed"
            
            status = status_resp.json()
            assert "can_undo" in status, "Status missing can_undo"
            assert "can_redo" in status, "Status missing can_redo"
            
            self.results.add("API", "Undo/Redo Status", True)
        except Exception as e:
            self.results.add("API", "Undo/Redo Status", False, str(e))
        
        # Test search API
        try:
            search_data = {"query": "API", "limit": 10}
            response = self.client.post("/api/v1/search/", json=search_data)
            assert response.status_code == 200, f"Search failed: {response.status_code}"
            
            self.results.add("API", "POST Search", True)
        except Exception as e:
            self.results.add("API", "POST Search", False, str(e))
        
        # Test dashboard API
        try:
            response = self.client.get("/api/v1/search/dashboard")
            assert response.status_code == 200, f"Dashboard failed: {response.status_code}"
            
            dashboard = response.json()
            expected_keys = ["overdue", "today", "tomorrow", "this_week", "completed", "high_priority"]
            for key in expected_keys:
                assert key in dashboard, f"Dashboard missing {key}"
            
            self.results.add("API", "GET Dashboard", True)
        except Exception as e:
            self.results.add("API", "GET Dashboard", False, str(e))
        
        # Test attachments API
        try:
            # Create task for attachment
            task_resp = self.client.post("/api/v1/tasks/", json={"title": "Attachment API Test"})
            att_task_id = task_resp.json()["id"]
            
            # Upload file
            files = {"file": ("api_test.txt", BytesIO(b"API test file content"), "text/plain")}
            upload_resp = self.client.post(f"/api/v1/attachments/upload/{att_task_id}", files=files)
            assert upload_resp.status_code == 200, f"Upload failed: {upload_resp.status_code}"
            
            upload_data = upload_resp.json()
            assert upload_data["success"], "Upload should be successful"
            
            # Get stats
            stats_resp = self.client.get("/api/v1/attachments/stats")
            assert stats_resp.status_code == 200, "Get stats failed"
            
            self.results.add("API", "Attachments API", True)
        except Exception as e:
            self.results.add("API", "Attachments API", False, str(e))
        
        # Test data management API
        try:
            # Integrity check (should be implemented)
            integrity_resp = self.client.get("/api/v1/data/integrity")
            assert integrity_resp.status_code == 200, f"Integrity check failed: {integrity_resp.status_code}"
            
            integrity = integrity_resp.json()
            assert "is_healthy" in integrity, "Missing is_healthy"
            
            # Export (returns 501 Not Implemented)
            export_resp = self.client.post("/api/v1/data/export")
            assert export_resp.status_code == 501, "Export should return 501 Not Implemented"
            
            self.results.add("API", "Data Management API", True)
        except Exception as e:
            self.results.add("API", "Data Management API", False, str(e))
        
        # Test WebSocket
        try:
            with self.client.websocket_connect("/api/v1/ws") as websocket:
                # Should receive welcome message
                data = websocket.receive_text()
                message = json.loads(data)
                assert message["type"] == "connected", "Should receive connected message"
                
                # Test heartbeat
                websocket.send_text(json.dumps({"type": "heartbeat"}))
                data = websocket.receive_text()
                message = json.loads(data)
                assert message["type"] == "heartbeat_ack", "Should receive heartbeat ack"
            
            self.results.add("API", "WebSocket Connection", True)
        except Exception as e:
            self.results.add("API", "WebSocket Connection", False, str(e))
        
        # Test soft delete via API
        try:
            response = self.client.delete(f"/api/v1/tasks/{task_id}")
            assert response.status_code == 204, f"Soft delete failed: {response.status_code}"
            
            # Task should not be retrievable
            get_resp = self.client.get(f"/api/v1/tasks/{task_id}")
            assert get_resp.status_code == 404, "Deleted task should return 404"
            
            self.results.add("API", "DELETE Task (Soft)", True)
        except Exception as e:
            self.results.add("API", "DELETE Task (Soft)", False, str(e))
        
        # Test restore via API
        try:
            response = self.client.post(f"/api/v1/tasks/{task_id}/restore")
            assert response.status_code == 200, f"Restore failed: {response.status_code}"
            
            self.results.add("API", "POST Restore Task", True)
        except Exception as e:
            self.results.add("API", "POST Restore Task", False, str(e))
    
    # =========================================================================
    # Main Test Runner
    # =========================================================================
    
    async def run_all_tests(self):
        """Run all tests."""
        try:
            await self.setup()
            
            # Run test suites
            await self.test_database_operations()
            await self.test_hierarchy_operations()
            await self.test_undo_redo_with_hierarchy()
            await self.test_attachment_operations()
            await self.test_search_operations()
            await self.test_api_endpoints()
            
            # Print summary
            return self.results.print_summary()
            
        finally:
            await self.cleanup()


async def main():
    """Main entry point."""
    print("=" * 80)
    print("LOCAL-FIRST TO-DO COMPREHENSIVE TEST SUITE")
    print("=" * 80)
    print()
    print("This script tests all components of the application:")
    print("  - Database operations and migrations")
    print("  - Task hierarchy (parent/child relationships)")
    print("  - Undo/Redo with hierarchy preservation")
    print("  - Attachment management with security")
    print("  - Search and filtering")
    print("  - REST API endpoints")
    print("  - WebSocket real-time communication")
    print()
    
    runner = ComprehensiveTestRunner()
    success = await runner.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
