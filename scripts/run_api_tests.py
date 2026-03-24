#!/usr/bin/env python3
"""
Comprehensive API Test Suite for Local-First To-Do Application.

This script tests ALL API endpoints exhaustively including:
- Task CRUD operations with hierarchy
- Task tree batch endpoint (N+1 optimization)
- Task reordering (root and nested)
- Complete-tree cascade operations
- Search API endpoints
- Data Management API endpoints
- Attachment API endpoints
- Undo/Redo API endpoints
- WebSocket functionality
- Edge cases and error handling

Usage:
    python scripts/run_api_tests.py

Requirements:
    - pip install httpx pytest-asyncio
"""

import asyncio
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from io import BytesIO
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# Configure console for Unicode
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

from fastapi.testclient import TestClient

# Import application modules
try:
    from local_first_todo.main import create_app
    from local_first_todo.database.manager import DatabaseManager
    from local_first_todo.database.crud import TaskRepository
    from local_first_todo.database.models import Task, TaskStatus
    from local_first_todo.services.undo_redo_service import UndoRedoService
    from local_first_todo.services.search_service import SearchService
    from local_first_todo.services.attachment_service import AttachmentService
    from local_first_todo import dependencies
except ImportError as e:
    print(f"ERROR: Failed to import required modules: {e}")
    print("Make sure you have installed the project with: pip install -e .")
    sys.exit(1)


class TestResult:
    """Test result tracker with detailed reporting."""
    
    def __init__(self):
        self.results: Dict[str, List[Dict[str, Any]]] = {}
        self.total_passed = 0
        self.total_failed = 0
        self.total_skipped = 0
    
    def add(self, category: str, test_name: str, passed: bool, message: str = "", skipped: bool = False):
        """Add a test result."""
        if category not in self.results:
            self.results[category] = []
        
        self.results[category].append({
            "name": test_name,
            "passed": passed,
            "skipped": skipped,
            "message": message
        })
        
        if skipped:
            self.total_skipped += 1
        elif passed:
            self.total_passed += 1
        else:
            self.total_failed += 1
    
    def print_summary(self) -> bool:
        """Print detailed test summary."""
        print("\n" + "=" * 80)
        print("COMPREHENSIVE API TEST RESULTS")
        print("=" * 80)
        
        for category, tests in self.results.items():
            passed = sum(1 for t in tests if t["passed"] and not t["skipped"])
            skipped = sum(1 for t in tests if t["skipped"])
            total = len(tests) - skipped
            status = "[PASS]" if passed == total else "[FAIL]"
            print(f"\n{status} {category}: {passed}/{total} passed" + (f" ({skipped} skipped)" if skipped else ""))
            
            for test in tests:
                if test["skipped"]:
                    icon = "  [SKIP]"
                elif test["passed"]:
                    icon = "  [PASS]"
                else:
                    icon = "  [FAIL]"
                print(f"{icon} {test['name']}")
                if test["message"] and not test["passed"]:
                    print(f"         Error: {test['message'][:100]}")
        
        print("\n" + "=" * 80)
        print(f"TOTAL: {self.total_passed}/{self.total_passed + self.total_failed} tests passed" +
              (f" ({self.total_skipped} skipped)" if self.total_skipped else ""))
        
        if self.total_failed == 0:
            print("[SUCCESS] ALL TESTS PASSED!")
        else:
            print(f"[WARNING] {self.total_failed} tests failed")
        print("=" * 80)
        
        return self.total_failed == 0


class APITestRunner:
    """Comprehensive API test runner."""
    
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
        print("Setting up test environment...")
        
        # Create temporary database
        fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        # Create temporary attachments directory
        self.temp_attachments_dir = tempfile.mkdtemp()
        
        # Initialize database
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
            max_attachment_size=10 * 1024 * 1024
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
        
        print("[OK] Test environment ready\n")
    
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
        print("\n[OK] Test environment cleaned up")
    
    # =========================================================================
    # Core Task CRUD Tests
    # =========================================================================
    
    def test_health_check(self):
        """Test health endpoint."""
        try:
            response = self.client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "version" in data
            self.results.add("Core API", "Health Check", True)
        except Exception as e:
            self.results.add("Core API", "Health Check", False, str(e))
    
    def test_create_task(self) -> Optional[int]:
        """Test task creation."""
        try:
            task_data = {
                "title": "Test Task",
                "description": "Test description",
                "status": "pending",
                "priority": 3
            }
            response = self.client.post("/api/v1/tasks/", json=task_data)
            assert response.status_code == 201
            data = response.json()
            assert data["title"] == task_data["title"]
            assert "id" in data
            assert "uuid" in data
            self.results.add("Core API", "Create Task", True)
            return data["id"]
        except Exception as e:
            self.results.add("Core API", "Create Task", False, str(e))
            return None
    
    def test_get_task(self, task_id: int):
        """Test getting a task by ID."""
        try:
            response = self.client.get(f"/api/v1/tasks/{task_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == task_id
            self.results.add("Core API", "Get Task by ID", True)
        except Exception as e:
            self.results.add("Core API", "Get Task by ID", False, str(e))
    
    def test_update_task(self, task_id: int):
        """Test updating a task."""
        try:
            update_data = {"title": "Updated Title", "priority": 5}
            response = self.client.put(f"/api/v1/tasks/{task_id}", json=update_data)
            assert response.status_code == 200
            data = response.json()
            assert data["title"] == "Updated Title"
            assert data["revision"] >= 1
            self.results.add("Core API", "Update Task", True)
        except Exception as e:
            self.results.add("Core API", "Update Task", False, str(e))
    
    def test_list_tasks(self):
        """Test listing all tasks."""
        try:
            response = self.client.get("/api/v1/tasks/")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            self.results.add("Core API", "List Tasks", True)
        except Exception as e:
            self.results.add("Core API", "List Tasks", False, str(e))
    
    def test_soft_delete_and_restore(self, task_id: int):
        """Test soft delete and restore."""
        try:
            # Soft delete
            response = self.client.delete(f"/api/v1/tasks/{task_id}")
            assert response.status_code == 204
            
            # Should not be findable
            get_response = self.client.get(f"/api/v1/tasks/{task_id}")
            assert get_response.status_code == 404
            
            # Restore
            restore_response = self.client.post(f"/api/v1/tasks/{task_id}/restore")
            assert restore_response.status_code == 200
            
            # Should be findable again
            get_response = self.client.get(f"/api/v1/tasks/{task_id}")
            assert get_response.status_code == 200
            
            self.results.add("Core API", "Soft Delete and Restore", True)
        except Exception as e:
            self.results.add("Core API", "Soft Delete and Restore", False, str(e))
    
    # =========================================================================
    # Hierarchy Tests
    # =========================================================================
    
    def test_create_hierarchical_tasks(self) -> tuple:
        """Test creating parent-child task relationships."""
        try:
            # Create parent
            parent_response = self.client.post("/api/v1/tasks/", json={"title": "Parent Task"})
            assert parent_response.status_code == 201
            parent_id = parent_response.json()["id"]
            
            # Create child
            child_response = self.client.post("/api/v1/tasks/", json={
                "title": "Child Task",
                "parent_id": parent_id
            })
            assert child_response.status_code == 201
            child_id = child_response.json()["id"]
            
            # Create grandchild
            grandchild_response = self.client.post("/api/v1/tasks/", json={
                "title": "Grandchild Task",
                "parent_id": child_id
            })
            assert grandchild_response.status_code == 201
            grandchild_id = grandchild_response.json()["id"]
            
            # Verify children
            children_response = self.client.get(f"/api/v1/tasks/{parent_id}/children")
            assert children_response.status_code == 200
            children = children_response.json()
            assert any(c["id"] == child_id for c in children)
            
            # Verify descendants
            descendants_response = self.client.get(f"/api/v1/tasks/{parent_id}/descendants")
            assert descendants_response.status_code == 200
            descendants = descendants_response.json()
            assert len(descendants) == 2
            
            # Verify ancestors
            ancestors_response = self.client.get(f"/api/v1/tasks/{grandchild_id}/ancestors")
            assert ancestors_response.status_code == 200
            ancestors = ancestors_response.json()
            assert len(ancestors) == 2
            
            self.results.add("Hierarchy", "Create Hierarchical Tasks", True)
            return parent_id, child_id, grandchild_id
        except Exception as e:
            self.results.add("Hierarchy", "Create Hierarchical Tasks", False, str(e))
            return None, None, None
    
    def test_move_task(self, child_id: int):
        """Test moving a task to a new parent."""
        try:
            # Create new parent
            new_parent_response = self.client.post("/api/v1/tasks/", json={"title": "New Parent"})
            new_parent_id = new_parent_response.json()["id"]
            
            # Move task
            move_response = self.client.put(f"/api/v1/tasks/{child_id}/move", json={
                "new_parent_id": new_parent_id,
                "position": 0
            })
            assert move_response.status_code == 200
            
            # Verify move
            children_response = self.client.get(f"/api/v1/tasks/{new_parent_id}/children")
            children = children_response.json()
            assert any(c["id"] == child_id for c in children)
            
            self.results.add("Hierarchy", "Move Task to New Parent", True)
            return new_parent_id
        except Exception as e:
            self.results.add("Hierarchy", "Move Task to New Parent", False, str(e))
            return None
    
    def test_move_to_root(self, task_id: int):
        """Test moving a task to root level."""
        try:
            response = self.client.put(f"/api/v1/tasks/{task_id}/move", json={
                "new_parent_id": None
            })
            assert response.status_code == 200
            
            # Verify at root
            root_response = self.client.get("/api/v1/tasks/root")
            root_tasks = root_response.json()
            assert any(t["id"] == task_id for t in root_tasks)
            
            self.results.add("Hierarchy", "Move Task to Root", True)
        except Exception as e:
            self.results.add("Hierarchy", "Move Task to Root", False, str(e))
    
    def test_prevent_circular_move(self):
        """Test that moving into own descendant is prevented."""
        try:
            # Create hierarchy
            parent_response = self.client.post("/api/v1/tasks/", json={"title": "Circular Parent"})
            parent_id = parent_response.json()["id"]
            
            child_response = self.client.post("/api/v1/tasks/", json={
                "title": "Circular Child",
                "parent_id": parent_id
            })
            child_id = child_response.json()["id"]
            
            # Try to move parent into child (should fail)
            move_response = self.client.put(f"/api/v1/tasks/{parent_id}/move", json={
                "new_parent_id": child_id
            })
            assert move_response.status_code == 400
            assert "descendant" in move_response.json()["detail"].lower()
            
            self.results.add("Hierarchy", "Prevent Circular Move", True)
        except Exception as e:
            self.results.add("Hierarchy", "Prevent Circular Move", False, str(e))
    
    # =========================================================================
    # Task Tree Batch Endpoint Tests
    # =========================================================================
    
    def test_get_task_tree(self):
        """Test the batch task tree endpoint (N+1 optimization)."""
        try:
            response = self.client.get("/api/v1/tasks/tree?order_by=custom")
            assert response.status_code == 200
            data = response.json()
            
            assert "tasks" in data
            assert "total_count" in data
            assert isinstance(data["tasks"], list)
            assert isinstance(data["total_count"], int)
            
            # Verify tree structure (tasks have children arrays)
            for task in data["tasks"]:
                assert "children" in task
                assert isinstance(task["children"], list)
            
            self.results.add("Task Tree", "Get Task Tree (Batch)", True)
        except Exception as e:
            self.results.add("Task Tree", "Get Task Tree (Batch)", False, str(e))
    
    def test_task_tree_ordering(self):
        """Test task tree with different ordering options."""
        try:
            # Test with custom ordering
            custom_response = self.client.get("/api/v1/tasks/tree?order_by=custom")
            assert custom_response.status_code == 200
            
            # Test with created_at ordering
            created_response = self.client.get("/api/v1/tasks/tree?order_by=created_at")
            assert created_response.status_code == 200
            
            self.results.add("Task Tree", "Task Tree Ordering Options", True)
        except Exception as e:
            self.results.add("Task Tree", "Task Tree Ordering Options", False, str(e))
    
    # =========================================================================
    # Reorder Tests
    # =========================================================================
    
    def test_reorder_root_tasks(self):
        """Test reordering root-level tasks."""
        try:
            # Create multiple root tasks with unique names
            task_ids = []
            for i in range(3):
                response = self.client.post("/api/v1/tasks/", json={"title": f"Reorder Root Unique {i} {id(self)}"})
                assert response.status_code == 201, f"Failed to create task: {response.text}"
                task_ids.append(response.json()["id"])
            
            # Get current root tasks to verify these are root tasks
            root_response = self.client.get("/api/v1/tasks/root")
            root_ids = [t["id"] for t in root_response.json()]
            
            # Filter to only our created tasks that are actually at root
            root_task_ids = [tid for tid in task_ids if tid in root_ids]
            
            if len(root_task_ids) >= 2:
                # Reverse the order
                reversed_ids = list(reversed(root_task_ids))
                reorder_response = self.client.post("/api/v1/tasks/root/reorder", json={
                    "task_ids": reversed_ids
                })
                assert reorder_response.status_code == 200, f"Reorder failed: {reorder_response.text}"
                data = reorder_response.json()
                assert data["success"] is True
                assert data["updated_count"] == len(reversed_ids)
            
            self.results.add("Reorder", "Reorder Root Tasks", True)
        except Exception as e:
            self.results.add("Reorder", "Reorder Root Tasks", False, str(e))
    
    def test_reorder_child_tasks(self):
        """Test reordering child tasks under a parent."""
        try:
            # Create parent
            parent_response = self.client.post("/api/v1/tasks/", json={"title": "Reorder Parent"})
            parent_id = parent_response.json()["id"]
            
            # Create children
            child_ids = []
            for i in range(3):
                response = self.client.post("/api/v1/tasks/", json={
                    "title": f"Reorder Child {i}",
                    "parent_id": parent_id
                })
                child_ids.append(response.json()["id"])
            
            # Reverse the order
            reversed_ids = list(reversed(child_ids))
            reorder_response = self.client.post(f"/api/v1/tasks/{parent_id}/reorder", json={
                "task_ids": reversed_ids
            })
            assert reorder_response.status_code == 200
            data = reorder_response.json()
            assert data["success"] is True
            assert data["updated_count"] == 3
            
            self.results.add("Reorder", "Reorder Child Tasks", True)
        except Exception as e:
            self.results.add("Reorder", "Reorder Child Tasks", False, str(e))
    
    # =========================================================================
    # Complete-Tree Cascade Tests
    # =========================================================================
    
    def test_complete_tree_cascade(self):
        """Test completing/uncompleting a task tree."""
        try:
            # Create hierarchy
            parent_response = self.client.post("/api/v1/tasks/", json={"title": "Complete Parent"})
            parent_id = parent_response.json()["id"]
            
            child_response = self.client.post("/api/v1/tasks/", json={
                "title": "Complete Child",
                "parent_id": parent_id
            })
            child_id = child_response.json()["id"]
            
            # Complete the tree
            complete_response = self.client.post(f"/api/v1/tasks/{parent_id}/complete-tree?complete=true")
            assert complete_response.status_code == 200
            data = complete_response.json()
            assert data["success"] is True
            assert data["updated_count"] == 2
            assert data["status"] == "completed"
            
            # Verify both are completed
            parent_data = self.client.get(f"/api/v1/tasks/{parent_id}").json()
            child_data = self.client.get(f"/api/v1/tasks/{child_id}").json()
            assert parent_data["status"] == "completed"
            assert child_data["status"] == "completed"
            
            # Uncomplete the tree
            uncomplete_response = self.client.post(f"/api/v1/tasks/{parent_id}/complete-tree?complete=false")
            assert uncomplete_response.status_code == 200
            
            self.results.add("Complete Tree", "Complete/Uncomplete Tree Cascade", True)
        except Exception as e:
            self.results.add("Complete Tree", "Complete/Uncomplete Tree Cascade", False, str(e))
    
    # =========================================================================
    # Soft Delete with Descendants Tests
    # =========================================================================
    
    def test_soft_delete_with_descendants(self):
        """Test soft deleting a task with all its descendants."""
        try:
            # Create hierarchy
            parent_response = self.client.post("/api/v1/tasks/", json={"title": "Delete Parent"})
            parent_id = parent_response.json()["id"]
            
            child_response = self.client.post("/api/v1/tasks/", json={
                "title": "Delete Child",
                "parent_id": parent_id
            })
            child_id = child_response.json()["id"]
            
            grandchild_response = self.client.post("/api/v1/tasks/", json={
                "title": "Delete Grandchild",
                "parent_id": child_id
            })
            grandchild_id = grandchild_response.json()["id"]
            
            # Soft delete parent (should delete all descendants)
            delete_response = self.client.delete(f"/api/v1/tasks/{parent_id}")
            assert delete_response.status_code == 204
            
            # All should be deleted
            assert self.client.get(f"/api/v1/tasks/{parent_id}").status_code == 404
            assert self.client.get(f"/api/v1/tasks/{child_id}").status_code == 404
            assert self.client.get(f"/api/v1/tasks/{grandchild_id}").status_code == 404
            
            self.results.add("Delete", "Soft Delete with Descendants", True)
        except Exception as e:
            self.results.add("Delete", "Soft Delete with Descendants", False, str(e))
    
    def test_hard_delete_with_descendants(self):
        """Test hard deleting a task with all its descendants."""
        try:
            # Create hierarchy
            parent_response = self.client.post("/api/v1/tasks/", json={"title": "Hard Delete Parent"})
            parent_id = parent_response.json()["id"]
            
            child_response = self.client.post("/api/v1/tasks/", json={
                "title": "Hard Delete Child",
                "parent_id": parent_id
            })
            child_id = child_response.json()["id"]
            
            # Hard delete parent
            delete_response = self.client.delete(f"/api/v1/tasks/{parent_id}?hard_delete=true")
            assert delete_response.status_code == 204
            
            # All should be gone (even from DB)
            assert self.client.get(f"/api/v1/tasks/{parent_id}").status_code == 404
            assert self.client.get(f"/api/v1/tasks/{child_id}").status_code == 404
            
            # Cannot restore (hard deleted)
            restore_response = self.client.post(f"/api/v1/tasks/{parent_id}/restore")
            assert restore_response.status_code == 404
            
            self.results.add("Delete", "Hard Delete with Descendants", True)
        except Exception as e:
            self.results.add("Delete", "Hard Delete with Descendants", False, str(e))
    
    # =========================================================================
    # Search API Tests
    # =========================================================================
    
    def test_search_api_basic(self):
        """Test basic search API."""
        try:
            # Create searchable tasks
            self.client.post("/api/v1/tasks/", json={
                "title": "Search Test Meeting",
                "description": "Important meeting discussion"
            })
            self.client.post("/api/v1/tasks/", json={
                "title": "Search Test Report",
                "description": "Quarterly report preparation"
            })
            
            # Search - API returns list directly
            search_response = self.client.post("/api/v1/search/", json={
                "query": "meeting",
                "limit": 10
            })
            assert search_response.status_code == 200
            data = search_response.json()
            assert isinstance(data, list)
            assert any("meeting" in r["title"].lower() for r in data)
            
            self.results.add("Search API", "Basic Search", True)
        except Exception as e:
            self.results.add("Search API", "Basic Search", False, str(e))
    
    def test_search_api_with_filters(self):
        """Test search API with filters."""
        try:
            search_response = self.client.post("/api/v1/search/", json={
                "statuses": ["pending"],
                "min_priority": 3,
                "limit": 10
            })
            assert search_response.status_code == 200
            data = search_response.json()
            assert isinstance(data, list)
            
            # Verify filters applied
            for result in data:
                assert result["status"] == "pending"
            
            self.results.add("Search API", "Search with Filters", True)
        except Exception as e:
            self.results.add("Search API", "Search with Filters", False, str(e))
    
    def test_search_dashboard(self):
        """Test dashboard endpoint."""
        try:
            # Create tasks with various due dates
            now = datetime.now(timezone.utc)
            
            # Overdue task
            self.client.post("/api/v1/tasks/", json={
                "title": "Dashboard Overdue",
                "next_due_utc": (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "priority": 4
            })
            
            # Today's task
            self.client.post("/api/v1/tasks/", json={
                "title": "Dashboard Today",
                "next_due_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "priority": 5
            })
            
            # High priority without due date
            self.client.post("/api/v1/tasks/", json={
                "title": "Dashboard High Priority",
                "priority": 5
            })
            
            response = self.client.get("/api/v1/search/dashboard")
            assert response.status_code == 200
            data = response.json()
            
            expected_keys = ["overdue", "today", "tomorrow", "this_week", "completed", "high_priority"]
            for key in expected_keys:
                assert key in data, f"Missing dashboard key: {key}"
            
            self.results.add("Search API", "Dashboard Endpoint", True)
        except Exception as e:
            self.results.add("Search API", "Dashboard Endpoint", False, str(e))
    
    def test_search_suggestions(self):
        """Test search suggestions endpoint."""
        try:
            # API uses 'q' parameter with min_length=2
            response = self.client.get("/api/v1/search/suggestions?q=meet&limit=5")
            assert response.status_code == 200
            data = response.json()
            assert "suggestions" in data
            assert isinstance(data["suggestions"], list)
            assert "query" in data
            
            self.results.add("Search API", "Search Suggestions", True)
        except Exception as e:
            self.results.add("Search API", "Search Suggestions", False, str(e))
    
    def test_search_stats(self):
        """Test search statistics endpoint."""
        try:
            response = self.client.get("/api/v1/search/stats")
            assert response.status_code == 200
            data = response.json()
            
            assert "total_tasks" in data
            assert "status_counts" in data
            assert "priority_counts" in data
            
            self.results.add("Search API", "Search Statistics", True)
        except Exception as e:
            self.results.add("Search API", "Search Statistics", False, str(e))
    
    # =========================================================================
    # Data Management API Tests
    # =========================================================================
    
    def test_data_integrity_check(self):
        """Test database integrity check endpoint."""
        try:
            response = self.client.get("/api/v1/data/integrity")
            assert response.status_code == 200
            data = response.json()
            
            assert "is_healthy" in data
            assert "integrity_check" in data
            assert "schema_version" in data
            assert "tables_present" in data
            assert data["is_healthy"] is True
            
            self.results.add("Data API", "Integrity Check", True)
        except Exception as e:
            self.results.add("Data API", "Integrity Check", False, str(e))
    
    def test_data_export_not_implemented(self):
        """Test export endpoint returns 501."""
        try:
            response = self.client.post("/api/v1/data/export")
            assert response.status_code == 501
            data = response.json()
            assert "not_implemented" in data["detail"]["type"]
            
            self.results.add("Data API", "Export (501 Not Implemented)", True)
        except Exception as e:
            self.results.add("Data API", "Export (501 Not Implemented)", False, str(e))
    
    def test_data_import_not_implemented(self):
        """Test import endpoint returns 501."""
        try:
            files = {"file": ("test.tar.gz", BytesIO(b"test"), "application/gzip")}
            response = self.client.post("/api/v1/data/import", files=files)
            assert response.status_code == 501
            
            self.results.add("Data API", "Import (501 Not Implemented)", True)
        except Exception as e:
            self.results.add("Data API", "Import (501 Not Implemented)", False, str(e))
    
    def test_data_sync(self):
        """Test sync delta endpoint."""
        try:
            response = self.client.get("/api/v1/data/sync?since_revision=0")
            assert response.status_code == 200
            data = response.json()
            
            assert "since_revision" in data
            assert "current_revision" in data
            assert "changes" in data
            assert "has_more" in data
            
            self.results.add("Data API", "Sync Delta", True)
        except Exception as e:
            self.results.add("Data API", "Sync Delta", False, str(e))
    
    # =========================================================================
    # Undo/Redo API Tests
    # =========================================================================
    
    def test_undo_redo_status(self):
        """Test undo/redo status endpoint."""
        try:
            response = self.client.get("/api/v1/undo-redo/status")
            assert response.status_code == 200
            data = response.json()
            
            assert "can_undo" in data
            assert "can_redo" in data
            assert "total_entries" in data
            
            self.results.add("Undo/Redo API", "Status Endpoint", True)
        except Exception as e:
            self.results.add("Undo/Redo API", "Status Endpoint", False, str(e))
    
    def test_undo_redo_flow(self):
        """Test complete undo/redo flow."""
        try:
            # Create a task (recorded for undo)
            create_response = self.client.post("/api/v1/tasks/", json={"title": "Undo Test"})
            task_id = create_response.json()["id"]
            
            # Check can undo
            status = self.client.get("/api/v1/undo-redo/status").json()
            assert status["can_undo"] is True
            
            # Undo
            undo_response = self.client.post("/api/v1/undo-redo/undo")
            assert undo_response.status_code == 200
            assert undo_response.json()["operation"] == "undo"
            
            # Task should be deleted
            get_response = self.client.get(f"/api/v1/tasks/{task_id}")
            assert get_response.status_code == 404
            
            # Check can redo
            status = self.client.get("/api/v1/undo-redo/status").json()
            assert status["can_redo"] is True
            
            # Redo
            redo_response = self.client.post("/api/v1/undo-redo/redo")
            assert redo_response.status_code == 200
            assert redo_response.json()["operation"] == "redo"
            
            # Task should be restored
            get_response = self.client.get(f"/api/v1/tasks/{task_id}")
            assert get_response.status_code == 200
            
            self.results.add("Undo/Redo API", "Undo/Redo Flow", True)
        except Exception as e:
            self.results.add("Undo/Redo API", "Undo/Redo Flow", False, str(e))
    
    def test_undo_empty_stack(self):
        """Test undo with empty stack returns 409."""
        try:
            # Clear any existing operations by creating fresh state
            # Undo all available operations first
            while True:
                status = self.client.get("/api/v1/undo-redo/status").json()
                if not status["can_undo"]:
                    break
                self.client.post("/api/v1/undo-redo/undo")
            
            # Clear redo stack
            while True:
                status = self.client.get("/api/v1/undo-redo/status").json()
                if not status["can_redo"]:
                    break
                self.client.post("/api/v1/undo-redo/redo")
            
            # Undo all again
            while True:
                status = self.client.get("/api/v1/undo-redo/status").json()
                if not status["can_undo"]:
                    break
                self.client.post("/api/v1/undo-redo/undo")
            
            # Now try undo on empty stack
            response = self.client.post("/api/v1/undo-redo/undo")
            assert response.status_code == 409
            
            self.results.add("Undo/Redo API", "Undo Empty Stack (409)", True)
        except Exception as e:
            self.results.add("Undo/Redo API", "Undo Empty Stack (409)", False, str(e))
    
    # =========================================================================
    # Attachment API Tests
    # =========================================================================
    
    def test_attachment_upload(self) -> Optional[tuple]:
        """Test attachment upload."""
        try:
            # Create task for attachment
            task_response = self.client.post("/api/v1/tasks/", json={"title": "Attachment Task"})
            task_id = task_response.json()["id"]
            
            # Upload file
            file_content = b"Test file content for attachment"
            files = {"file": ("test.txt", BytesIO(file_content), "text/plain")}
            upload_response = self.client.post(f"/api/v1/attachments/upload/{task_id}", files=files)
            
            assert upload_response.status_code == 200
            data = upload_response.json()
            assert data["success"] is True
            assert data["attachment"]["filename"] == "test.txt"
            
            self.results.add("Attachment API", "Upload Attachment", True)
            return task_id, data["attachment"]["id"]
        except Exception as e:
            self.results.add("Attachment API", "Upload Attachment", False, str(e))
            return None
    
    def test_attachment_download(self, attachment_id: int):
        """Test attachment download."""
        try:
            response = self.client.get(f"/api/v1/attachments/download/{attachment_id}")
            assert response.status_code == 200
            assert len(response.content) > 0
            
            self.results.add("Attachment API", "Download Attachment", True)
        except Exception as e:
            self.results.add("Attachment API", "Download Attachment", False, str(e))
    
    def test_attachment_list_for_task(self, task_id: int):
        """Test listing attachments for a task."""
        try:
            response = self.client.get(f"/api/v1/attachments/task/{task_id}")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) >= 1
            
            self.results.add("Attachment API", "List Task Attachments", True)
        except Exception as e:
            self.results.add("Attachment API", "List Task Attachments", False, str(e))
    
    def test_attachment_stats(self):
        """Test attachment statistics."""
        try:
            response = self.client.get("/api/v1/attachments/stats")
            assert response.status_code == 200
            data = response.json()
            
            assert "attachment_count" in data
            assert "blob_count" in data
            assert "total_size_bytes" in data
            
            self.results.add("Attachment API", "Attachment Statistics", True)
        except Exception as e:
            self.results.add("Attachment API", "Attachment Statistics", False, str(e))
    
    def test_attachment_quota(self):
        """Test attachment quota endpoint."""
        try:
            response = self.client.get("/api/v1/attachments/quota")
            assert response.status_code == 200
            data = response.json()
            
            assert "total_space" in data
            assert "available_space" in data
            assert "can_upload" in data
            
            self.results.add("Attachment API", "Quota Information", True)
        except Exception as e:
            self.results.add("Attachment API", "Quota Information", False, str(e))
    
    def test_attachment_security_path_traversal(self):
        """Test path traversal is blocked."""
        try:
            task_response = self.client.post("/api/v1/tasks/", json={"title": "Security Test"})
            task_id = task_response.json()["id"]
            
            files = {"file": ("../../../etc/passwd", BytesIO(b"malicious"), "text/plain")}
            response = self.client.post(f"/api/v1/attachments/upload/{task_id}", files=files)
            
            assert response.status_code == 400
            assert response.json()["detail"]["type"] == "security_validation_error"
            
            self.results.add("Attachment API", "Path Traversal Blocked", True)
        except Exception as e:
            self.results.add("Attachment API", "Path Traversal Blocked", False, str(e))
    
    def test_attachment_delete(self, attachment_id: int):
        """Test attachment deletion."""
        try:
            response = self.client.delete(f"/api/v1/attachments/{attachment_id}")
            assert response.status_code == 200
            
            # Should not be downloadable
            download_response = self.client.get(f"/api/v1/attachments/download/{attachment_id}")
            assert download_response.status_code == 404
            
            self.results.add("Attachment API", "Delete Attachment", True)
        except Exception as e:
            self.results.add("Attachment API", "Delete Attachment", False, str(e))
    
    # =========================================================================
    # WebSocket Tests
    # =========================================================================
    
    def test_websocket_connection(self):
        """Test WebSocket connection establishment."""
        try:
            with self.client.websocket_connect("/api/v1/ws") as websocket:
                # Should receive welcome message
                data = websocket.receive_text()
                message = json.loads(data)
                assert message["type"] == "connected"
                
                # Test heartbeat
                websocket.send_text(json.dumps({"type": "heartbeat"}))
                data = websocket.receive_text()
                message = json.loads(data)
                assert message["type"] == "heartbeat_ack"
            
            self.results.add("WebSocket", "Connection and Heartbeat", True)
        except Exception as e:
            self.results.add("WebSocket", "Connection and Heartbeat", False, str(e))
    
    def test_websocket_invalid_json(self):
        """Test WebSocket error handling for invalid JSON."""
        try:
            with self.client.websocket_connect("/api/v1/ws") as websocket:
                websocket.receive_text()  # Welcome message
                
                # Send invalid JSON
                websocket.send_text("not valid json")
                data = websocket.receive_text()
                message = json.loads(data)
                assert message["type"] == "error"
            
            self.results.add("WebSocket", "Invalid JSON Handling", True)
        except Exception as e:
            self.results.add("WebSocket", "Invalid JSON Handling", False, str(e))
    
    # =========================================================================
    # Error Handling Tests
    # =========================================================================
    
    def test_task_not_found(self):
        """Test 404 for non-existent task."""
        try:
            response = self.client.get("/api/v1/tasks/999999")
            assert response.status_code == 404
            
            self.results.add("Error Handling", "Task Not Found (404)", True)
        except Exception as e:
            self.results.add("Error Handling", "Task Not Found (404)", False, str(e))
    
    def test_validation_errors(self):
        """Test validation error responses."""
        try:
            # Empty title
            response = self.client.post("/api/v1/tasks/", json={"title": ""})
            assert response.status_code == 422
            
            # Invalid priority
            response = self.client.post("/api/v1/tasks/", json={"title": "Test", "priority": 10})
            assert response.status_code == 422
            
            # Invalid status
            response = self.client.post("/api/v1/tasks/", json={"title": "Test", "status": "invalid"})
            assert response.status_code == 422
            
            self.results.add("Error Handling", "Validation Errors (422)", True)
        except Exception as e:
            self.results.add("Error Handling", "Validation Errors (422)", False, str(e))
    
    # =========================================================================
    # Bulk Operations Tests
    # =========================================================================
    
    def test_bulk_operations(self):
        """Test bulk operations endpoint."""
        try:
            bulk_request = {
                "operations": [
                    {"type": "create", "data": {"title": "Bulk Task 1"}},
                    {"type": "create", "data": {"title": "Bulk Task 2"}},
                    {"type": "create", "data": {"title": "Bulk Task 3"}}
                ]
            }
            
            response = self.client.post("/api/v1/tasks/bulk", json=bulk_request)
            assert response.status_code == 200
            data = response.json()
            
            assert "results" in data
            assert len(data["results"]) == 3
            assert all(r["success"] for r in data["results"])
            
            self.results.add("Bulk Operations", "Bulk Create Tasks", True)
        except Exception as e:
            self.results.add("Bulk Operations", "Bulk Create Tasks", False, str(e))
    
    # =========================================================================
    # Main Test Runner
    # =========================================================================
    
    async def run_all_tests(self):
        """Run all API tests."""
        try:
            await self.setup()
            
            print("Running Core API Tests...")
            self.test_health_check()
            task_id = self.test_create_task()
            if task_id:
                self.test_get_task(task_id)
                self.test_update_task(task_id)
            self.test_list_tasks()
            if task_id:
                self.test_soft_delete_and_restore(task_id)
            
            print("Running Hierarchy Tests...")
            parent_id, child_id, grandchild_id = self.test_create_hierarchical_tasks()
            if child_id:
                new_parent_id = self.test_move_task(child_id)
                if new_parent_id:
                    self.test_move_to_root(child_id)
            self.test_prevent_circular_move()
            
            print("Running Task Tree Tests...")
            self.test_get_task_tree()
            self.test_task_tree_ordering()
            
            print("Running Reorder Tests...")
            self.test_reorder_root_tasks()
            self.test_reorder_child_tasks()
            
            print("Running Complete Tree Tests...")
            self.test_complete_tree_cascade()
            
            print("Running Delete Tests...")
            self.test_soft_delete_with_descendants()
            self.test_hard_delete_with_descendants()
            
            print("Running Search API Tests...")
            self.test_search_api_basic()
            self.test_search_api_with_filters()
            self.test_search_dashboard()
            self.test_search_suggestions()
            self.test_search_stats()
            
            print("Running Data API Tests...")
            self.test_data_integrity_check()
            self.test_data_export_not_implemented()
            self.test_data_import_not_implemented()
            self.test_data_sync()
            
            print("Running Undo/Redo API Tests...")
            self.test_undo_redo_status()
            self.test_undo_redo_flow()
            self.test_undo_empty_stack()
            
            print("Running Attachment API Tests...")
            attachment_result = self.test_attachment_upload()
            if attachment_result:
                att_task_id, attachment_id = attachment_result
                self.test_attachment_download(attachment_id)
                self.test_attachment_list_for_task(att_task_id)
            self.test_attachment_stats()
            self.test_attachment_quota()
            self.test_attachment_security_path_traversal()
            if attachment_result:
                # Create new attachment to delete
                new_upload = self.test_attachment_upload()
                if new_upload:
                    self.test_attachment_delete(new_upload[1])
            
            print("Running WebSocket Tests...")
            self.test_websocket_connection()
            self.test_websocket_invalid_json()
            
            print("Running Error Handling Tests...")
            self.test_task_not_found()
            self.test_validation_errors()
            
            print("Running Bulk Operations Tests...")
            self.test_bulk_operations()
            
            return self.results.print_summary()
            
        finally:
            await self.cleanup()


async def main():
    """Main entry point."""
    print("=" * 80)
    print("LOCAL-FIRST TO-DO COMPREHENSIVE API TEST SUITE")
    print("=" * 80)
    print()
    
    runner = APITestRunner()
    success = await runner.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
