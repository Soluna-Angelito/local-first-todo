# Comprehensive Test Suite

This document describes the `test_comprehensive.py` test suite for the Local-First To-Do Service.

## Overview

`test_comprehensive.py` is a consolidated test file containing **194 tests** (158 active, 36 skipped) organized into **28 parts** covering:

- API Endpoints (Tasks, Attachments, Undo/Redo, WebSocket, Data)
- Database Operations (CRUD, Migrations, Hierarchies)
- Services (Search, Attachment, Undo/Redo)
- Critical issues identified in REVIEW.md

**Note:** UI/E2E tests for server-side rendered views are skipped because the application uses a Single Page Application (SPA) architecture with client-side rendering.

## Folder Structure

```
tests/
  __init__.py           # Package marker
  conftest.py           # Shared pytest fixtures
  README.md             # This file
  test_comprehensive.py # All tests consolidated
```

## Running Tests

### Using Batch Files (Windows)

| Batch File | Description |
|------------|-------------|
| `6 run_comprehensive_tests.bat` | Run all tests |
| `6 run_comprehensive_tests.bat --verbose` | Run with detailed output |
| `6a run_fast_tests.bat` | Skip slow tests |
| `6b run_single_test.bat [name]` | Run specific test class or method |
| `6c run_tests_with_coverage.bat` | Run with coverage report |

### Using pytest directly

```bash
# Run all tests
python -m pytest tests/test_comprehensive.py -s --tb=no -q

# Run with verbose output
VERBOSE_TESTS=1 python -m pytest tests/test_comprehensive.py -s --tb=no -q

# Run specific test class
python -m pytest tests/test_comprehensive.py -k "TestTaskAPI" -s

# Run specific test method
python -m pytest tests/test_comprehensive.py -k "test_create_task_basic" -s

# Skip slow tests
python -m pytest tests/test_comprehensive.py -m "not slow" -s

# Run with coverage
python -m pytest tests/test_comprehensive.py --cov=src/local_first_todo --cov-report=html
```

## Output Modes

### Compact Mode (Default)

Shows one line per test with pass/fail status:

```
  ✓ TestTaskAPI::test_health_check (0.02s)
  ✓ TestTaskAPI::test_create_task_basic (0.05s)
  ✗ TestTaskAPI::test_failing_test (0.01s) FAILED
```

Failure details are always shown at the end for debugging.

### Verbose Mode

Set `VERBOSE_TESTS=1` environment variable or use `--verbose` flag for detailed output during each test.

## Test Structure (28 Parts)

### API Tests

| Part | Class | Description |
|------|-------|-------------|
| 1 | `TestTaskAPI` | Task CRUD operations, hierarchy, search, bulk operations |
| 5 | `TestAttachmentAPI` | File upload, download, deduplication, security |
| 6 | `TestUndoRedoAPI` | Undo/redo status, operations, error handling |
| 7 | `TestWebSocketAPI` | WebSocket connection, heartbeat, messages |
| 22 | `TestAttachmentAPIComplete` | Additional attachment tests |
| 23 | `TestUndoRedoAPIComplete` | Additional undo/redo tests |

### REVIEW.md Issue Tests

| Part | Class | Description |
|------|-------|-------------|
| 2 | `TestReviewMdCriticalIssues` | Undo hierarchy, move-to-descendant, delete behavior |
| 3 | `TestReviewMdMediumIssues` | Large file upload, quota, priority, export/import |
| 4 | `TestReviewMdLowIssues` | Undo log truncation, WebSocket health, CORS |

### Database Tests

| Part | Class | Description |
|------|-------|-------------|
| 8 | `TestDatabaseOperations` | Initialization, pragmas, transactions, closure table |
| 17 | `TestDatabaseMigrations` | Schema version, FTS, indexes, constraints |
| 20 | `TestDatabaseCRUDComplete` | Additional CRUD and manager tests |
| 20 | `TestDatabaseManagerComplete` | Database manager advanced tests |

### Service Tests

| Part | Class | Description |
|------|-------|-------------|
| 9 | `TestSearchService` | Full-text search, filters, dashboard |
| 11 | `TestAttachmentServiceUnit` | Filename validation, security |
| 12 | `TestUndoRedoServiceUnit` | Operation recording, journal truncation |
| 19 | `TestAttachmentServiceComplete` | Additional attachment service tests |
| 19 | `TestSearchServiceComplete` | Additional search service tests |
| 19 | `TestUndoRedoServiceComplete` | Additional undo/redo service tests |
| 28 | `TestUndoRedoProperties` | Idempotency, consistency tests |

### UI Tests

| Part | Class | Description |
|------|-------|-------------|
| 10 | `TestUIEndpoints` | Main page, static files, API docs |
| 16 | `TestUINavigationComplete` | Navigation tests (some skipped - SPA architecture) |

### Skipped Tests (SPA Architecture)

The following test classes are skipped because they test server-side rendered views that don't exist in the current SPA architecture:

| Part | Class | Reason Skipped |
|------|-------|----------------|
| 14 | `TestTreeFunctionality` | Server-side /tree/ endpoints not implemented |
| 15 | `TestTreePerformance` | Server-side /tree/ endpoints not implemented |
| 26 | `TestTreeFunctionalityAdvanced` | Server-side /tree/ endpoints not implemented |
| 27 | `TestTreePerformanceAdvanced` | Server-side /tree/ endpoints not implemented |

### CI/Setup Tests

| Part | Class | Description |
|------|-------|-------------|
| 24 | `TestCISetup` | Python version, package version, project structure |

### WebSocket Tests

| Part | Class | Description |
|------|-------|-------------|
| 18 | `TestWebSocketComplete` | Additional WebSocket tests |
| 25 | `TestWebSocketAdvanced` | Ping/pong, sync request, multiple connections |

### Performance Tests

| Part | Class | Description |
|------|-------|-------------|
| 13 | `TestPerformance` | Bulk creation, hierarchy queries |

## Test Markers

Tests can be filtered using pytest markers:

| Marker | Description |
|--------|-------------|
| `@pytest.mark.slow` | Long-running tests (skip with `-m "not slow"`) |
| `@pytest.mark.perf` | Performance benchmark tests |
| `@pytest.mark.asyncio` | Async tests (auto-applied) |
| `@pytest.mark.skip` | Skipped tests (outdated UI tests) |

## Fixtures

Key fixtures defined in `conftest.py`:

| Fixture | Scope | Description |
|---------|-------|-------------|
| `temp_db_path` | function | Temporary SQLite database path |
| `temp_attachments_dir` | function | Temporary directory for attachments |
| `db_manager` | function | Initialized DatabaseManager |
| `task_repository` | function | TaskRepository instance |
| `undo_redo_service` | function | UndoRedoService instance |
| `search_service` | function | SearchService instance |
| `attachment_service` | function | AttachmentService instance |
| `sample_task` | function | Sample Task object |
| `app` | function | FastAPI application (in test_comprehensive.py) |
| `client` | function | AsyncClient for API testing |

## Helper Functions

The test file includes helper functions for verbose output:

```python
_log_test_start(test_name)    # Log test header (verbose only)
_log_test_detail(message)     # Log step details (verbose only)
_log_test_success(message)    # Log success (verbose only)
_log_test_warning(message)    # Log warning (verbose only)
_log_test_error(message)      # Log error (always shown)
```

## Coverage

To generate a coverage report:

```bash
# Terminal report
python -m pytest tests/test_comprehensive.py --cov=src/local_first_todo --cov-report=term-missing

# HTML report (opens htmlcov/index.html)
python -m pytest tests/test_comprehensive.py --cov=src/local_first_todo --cov-report=html
```

## Test Output Example

### Summary (always shown)

```
======================================================================
  TEST RESULTS SUMMARY
======================================================================

  Total: 158  |  ✓ Passed: 158  |  ✗ Failed: 0  |  ⊘ Skipped: 0
  Duration: 10.40s

======================================================================
  ✓ ALL 158 TESTS PASSED
======================================================================
```

## Adding New Tests

1. Identify the appropriate Part/Class for your test
2. Add the test method following the naming convention `test_*`
3. Use fixtures from `conftest.py` or define local fixtures
4. Add docstrings describing the test purpose
5. Use `_log_*` helpers for verbose output if needed

Example:

```python
class TestTaskAPI:
    async def test_new_feature(self, client: AsyncClient):
        """Test the new feature works correctly."""
        _log_test_start("New Feature Test")
        
        # Arrange
        _log_test_detail("Creating test data...")
        
        # Act
        response = await client.post("/api/v1/tasks/", json={"title": "Test"})
        
        # Assert
        assert response.status_code == 201
        _log_test_success("Feature works as expected")
```

## Troubleshooting

### Tests fail to import

Ensure `PYTHONPATH` includes the `src` directory:

```bash
set PYTHONPATH=%CD%\src;%PYTHONPATH%
```

### Async tests hang

Check that `pytest-asyncio` is installed and `asyncio_mode = "auto"` is set in `pyproject.toml`.

### Database lock errors

Tests use temporary databases. If you see lock errors, ensure no other process is accessing the test database.

### WebSocket tests fail

WebSocket tests may fail in certain test environments. These failures are typically caught and logged rather than causing test failures.
