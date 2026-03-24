# tests/conftest.py
"""
Pytest configuration and shared fixtures for the Local-First To-Do test suite.

This module provides:
- Common test fixtures shared across different test modules
- Clean test reporting (verbose mode available via VERBOSE_TESTS=1)
- Test session statistics tracking
"""

import asyncio
import os
import tempfile
import shutil
import time
import sys
from pathlib import Path
from typing import Generator, AsyncGenerator, Dict, Any, List
from datetime import datetime

import pytest


# =============================================================================
# VERBOSITY CONTROL
# =============================================================================
# Set VERBOSE_TESTS=1 environment variable for detailed output
# Default: compact output showing test name + result

VERBOSE_MODE = os.environ.get("VERBOSE_TESTS", "0") == "1"


# =============================================================================
# TEST SESSION STATISTICS
# =============================================================================

class TestSessionStats:
    """Track statistics across the test session."""
    
    def __init__(self):
        self.total_tests = 0
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.total_duration = 0.0
        self.test_durations: Dict[str, float] = {}
        self.failed_tests: List[Dict[str, Any]] = []  # Store name + error details
        self.start_time = None
    
    def reset(self):
        """Reset all statistics."""
        self.__init__()


# Global stats instance
_session_stats = TestSessionStats()


# =============================================================================
# PYTEST HOOKS FOR REPORTING
# =============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "asyncio: mark test as async")
    config.addinivalue_line("markers", "slow: mark test as slow-running")
    config.addinivalue_line("markers", "perf: mark test as performance test")
    
    # Print header
    mode = "VERBOSE" if VERBOSE_MODE else "COMPACT"
    print(f"\n{'='*70}")
    print(f"  LOCAL-FIRST TO-DO - TEST SUITE [{mode} MODE]")
    print(f"{'='*70}")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Python:  {sys.version.split()[0]}")
    if not VERBOSE_MODE:
        print(f"  Tip: Set VERBOSE_TESTS=1 for detailed output")
    print(f"{'='*70}\n")


def pytest_sessionstart(session):
    """Called before the test session starts."""
    _session_stats.reset()
    _session_stats.start_time = time.time()


def pytest_runtest_setup(item):
    """Called before each test setup."""
    item._start_time = time.time()
    
    if VERBOSE_MODE:
        test_name = item.name
        test_class = item.parent.name if item.parent else "Module"
        docstring = ""
        if item.function.__doc__:
            docstring = item.function.__doc__.strip().split('\n')[0]
        
        print(f"\n{'─'*60}")
        print(f"▶ {test_class}::{test_name}")
        if docstring:
            print(f"  {docstring}")
        print(f"{'─'*60}")


def pytest_runtest_makereport(item, call):
    """Called after each test phase."""
    if call.when == "call":
        duration = time.time() - getattr(item, '_start_time', time.time())
        _session_stats.test_durations[item.nodeid] = duration


def pytest_runtest_logreport(report):
    """Called after each test report is generated."""
    if report.when == "call":
        _session_stats.total_tests += 1
        duration = _session_stats.test_durations.get(report.nodeid, 0)
        _session_stats.total_duration += duration
        
        # Extract test name (short form)
        test_path = report.nodeid
        if "::" in test_path:
            test_name = test_path.split("::")[-1]
            test_class = test_path.split("::")[-2] if test_path.count("::") >= 2 else ""
        else:
            test_name = test_path
            test_class = ""
        
        if report.passed:
            _session_stats.passed += 1
            # Compact: one line per passed test
            print(f"  ✓ {test_class}::{test_name} ({duration:.2f}s)")
            
        elif report.failed:
            _session_stats.failed += 1
            print(f"  ✗ {test_class}::{test_name} ({duration:.2f}s) FAILED")
            
            # Store failure details for summary
            error_info = {
                "name": f"{test_class}::{test_name}",
                "nodeid": report.nodeid,
                "duration": duration,
                "error": str(report.longrepr) if report.longrepr else "Unknown error"
            }
            _session_stats.failed_tests.append(error_info)
            
            # In verbose mode, show error immediately
            if VERBOSE_MODE and report.longrepr:
                print(f"\n  ERROR DETAILS:")
                error_lines = str(report.longrepr).split('\n')
                for line in error_lines[-10:]:  # Last 10 lines
                    if line.strip():
                        print(f"    {line}")
                print()
                
        elif report.skipped:
            _session_stats.skipped += 1
            print(f"  ⊘ {test_class}::{test_name} (skipped)")


def pytest_sessionfinish(session, exitstatus):
    """Called after the entire test session finishes."""
    total_time = time.time() - (_session_stats.start_time or time.time())
    
    print(f"\n{'='*70}")
    print(f"  TEST RESULTS SUMMARY")
    print(f"{'='*70}")
    
    # Results
    print(f"\n  Total: {_session_stats.total_tests}  |  "
          f"✓ Passed: {_session_stats.passed}  |  "
          f"✗ Failed: {_session_stats.failed}  |  "
          f"⊘ Skipped: {_session_stats.skipped}")
    print(f"  Duration: {total_time:.2f}s")
    
    # Failed test details (always show for AI debugging)
    if _session_stats.failed_tests:
        print(f"\n{'─'*70}")
        print(f"  FAILURE DETAILS (for debugging)")
        print(f"{'─'*70}")
        
        for i, failure in enumerate(_session_stats.failed_tests, 1):
            print(f"\n  [{i}] {failure['name']}")
            print(f"      Duration: {failure['duration']:.2f}s")
            print(f"      Location: {failure['nodeid']}")
            print(f"\n      Error:")
            # Show error with indentation
            error_lines = failure['error'].split('\n')
            # Show relevant error lines (skip pytest header noise)
            relevant_lines = []
            capture = False
            for line in error_lines:
                if 'assert' in line.lower() or 'error' in line.lower() or 'exception' in line.lower():
                    capture = True
                if capture or line.strip().startswith('>') or line.strip().startswith('E '):
                    relevant_lines.append(line)
            
            # If no relevant lines found, show last 15 lines
            if not relevant_lines:
                relevant_lines = error_lines[-15:]
            
            for line in relevant_lines[-15:]:  # Max 15 lines per failure
                if line.strip():
                    print(f"      {line}")
    
    # Final status
    print(f"\n{'='*70}")
    if _session_stats.failed == 0:
        print(f"  ✓ ALL {_session_stats.passed} TESTS PASSED")
    else:
        print(f"  ✗ {_session_stats.failed} TEST(S) FAILED")
    print(f"{'='*70}\n")


def pytest_collection_finish(session):
    """Called after test collection is finished."""
    print(f"  Collected {len(session.items)} tests\n")


# =============================================================================
# CORE FIXTURES
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_db_path() -> Generator[Path, None, None]:
    """Create a temporary database path for testing."""
    import tempfile
    import os
    
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    path = Path(path)
    
    yield path
    
    # Cleanup
    if path.exists():
        path.unlink()


@pytest.fixture
def temp_attachments_dir() -> Generator[Path, None, None]:
    """Create a temporary attachments directory."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    
    # Cleanup
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
async def db_manager(temp_db_path):
    """Create a database manager with a temporary database."""
    from local_first_todo.database.manager import DatabaseManager
    
    manager = DatabaseManager(str(temp_db_path))
    await manager.initialize()
    
    yield manager
    
    await manager.close()


@pytest.fixture
async def task_repository(db_manager):
    """Create a task repository with the test database."""
    from local_first_todo.database.crud import TaskRepository
    
    return TaskRepository(db_manager)


@pytest.fixture
async def undo_redo_service(db_manager):
    """Create an undo/redo service for testing."""
    from local_first_todo.services.undo_redo_service import UndoRedoService
    
    service = UndoRedoService(db_manager, max_undo_entries=100, max_undo_size_mb=10)
    await service.initialize()
    
    return service


@pytest.fixture
async def search_service(db_manager):
    """Create a search service for testing."""
    from local_first_todo.services.search_service import SearchService
    
    return SearchService(db_manager)


@pytest.fixture
async def attachment_service(db_manager, temp_attachments_dir):
    """Create an attachment service for testing."""
    from local_first_todo.services.attachment_service import AttachmentService
    
    return AttachmentService(
        db_manager=db_manager,
        attachments_dir=str(temp_attachments_dir),
        max_attachment_size=10 * 1024 * 1024  # 10MB for tests
    )


@pytest.fixture
def sample_task():
    """Create a sample task for testing."""
    from local_first_todo.database.models import Task, TaskStatus
    
    return Task(
        title="Test Task",
        description="This is a test task",
        status=TaskStatus.PENDING,
        priority=3
    )


# =============================================================================
# UTILITY FIXTURES
# =============================================================================

@pytest.fixture
def test_info(request):
    """
    Fixture providing detailed test information.
    
    Usage in tests:
        def test_something(test_info):
            test_info.log("Starting operation...")
            test_info.log("Value is: 42")
    """
    class TestInfo:
        def __init__(self, request):
            self.name = request.node.name
            self.class_name = request.node.parent.name if request.node.parent else None
            self.file = str(request.fspath) if hasattr(request, 'fspath') else None
            self.docstring = request.function.__doc__
        
        def log(self, message: str):
            """Log a message during test execution."""
            print(f"   ℹ️  {message}")
        
        def success(self, message: str):
            """Log a success message."""
            print(f"   ✅ {message}")
        
        def warning(self, message: str):
            """Log a warning message."""
            print(f"   ⚠️  {message}")
        
        def error(self, message: str):
            """Log an error message."""
            print(f"   ❌ {message}")
        
        def section(self, title: str):
            """Start a new section in the test output."""
            print(f"\n   📍 {title}")
            print(f"   {'─'*40}")
    
    return TestInfo(request)


# Configure asyncio mode
pytest_plugins = ('pytest_asyncio',)
