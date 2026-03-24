<div align="center">

# Soy Lunita

### Local-First Hierarchical Task Manager

A single-user, offline-first task management application with infinite hierarchical trees,\
full-text search, file attachments, and persistent undo/redo — all running locally on your machine.

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/SQLite-FTS5%20%7C%20WAL-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.0.0--dev-blue)](#)
[![Status](https://img.shields.io/badge/status-Alpha-orange)](#)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://docs.astral.sh/ruff/)
[![Type checked: mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](https://mypy-lang.org/)
[![Testing: pytest](https://img.shields.io/badge/testing-pytest-0A9EDC.svg?logo=pytest&logoColor=white)](https://pytest.org/)

</div>

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Development](#development)
- [Configuration](#configuration)
- [Security](#security)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---

## Overview

**Soy Lunita** is a local-first task management application designed for users who prioritize data sovereignty and offline capability. Unlike cloud-based alternatives, all data stays on your machine in a single SQLite database — no accounts, no telemetry, no internet required.

### Who is this for?

| Use Case | Why Soy Lunita |
|----------|----------------|
| **Air-gapped environments** | Zero network dependencies; works fully offline |
| **Privacy-conscious users** | Complete data sovereignty with local-only storage |
| **Security-sensitive workflows** | No data exfiltration surface; ideal for classified contexts |
| **Power users** | Keyboard-first design, infinite nesting, Markdown descriptions |

The application features an aurora-inspired dark UI with parallax star backgrounds, Markdown rendering with LaTeX math and syntax highlighting, and real-time multi-tab synchronization via WebSockets.

---

## Features

### Task Management

- **Infinite Hierarchical Tree** — Unlimited nested subtasks via a closure-table model
- **5 Task Statuses** — Pending, In Progress, Completed, Deferred, Deleted (soft)
- **4 Priority Levels** — Urgent, High, Medium, Low (plus unset)
- **Due Dates & Recurrence** — ISO 8601 dates with RFC 5545 recurrence rules
- **Bulk Operations** — Complete/uncomplete entire subtrees in a single action
- **Soft & Hard Delete** — Recoverable soft delete by default; permanent hard delete when needed
- **Move & Reorder** — Reparent tasks and reorder children within any level

### Search & Navigation

- **Full-Text Search** — Powered by SQLite FTS5 with trigger-synced index
- **Dashboard** — Aggregated task statistics and search analytics
- **Search Suggestions** — Auto-complete suggestions as you type

### File Attachments

- **Content-Addressable Storage** — SHA-256 hashed blobs with automatic deduplication
- **Configurable Quota** — Default 500 MB per-instance; adjustable
- **Security Validation** — Filename sanitization, path traversal prevention, optional executable blocking

### Undo / Redo

- **Persistent History** — JSON-Patch based operation log stored in SQLite
- **Crash-Safe** — Two-phase commit with PENDING/APPLIED status tracking
- **Full Reversibility** — Undo/redo spans create, update, delete, move, and bulk operations

### Real-Time Updates

- **WebSocket Sync** — Live updates across multiple browser tabs
- **Connection Health Check** — Background heartbeat with auto-reconnect
- **Status Indicator** — Visual connection state in the UI

### User Interface

- **Aurora Dark Theme** — Gradient accents with animated parallax star field
- **Markdown Rendering** — Full Markdown via Marked.js in task descriptions
- **LaTeX Math** — KaTeX for inline and display math expressions
- **Syntax Highlighting** — Highlight.js with Atom One Dark theme for code blocks
- **Keyboard-First** — Comprehensive shortcuts for all common operations
- **Toast Notifications** — Non-intrusive feedback for user actions
- **Responsive Layout** — Adapts to various screen sizes

---

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│  Frontend (SPA)                                                │
│  Vanilla JS (ES6+) · HTML5 · CSS3 (Aurora Theme)              │
│  Lucide Icons · Marked.js · KaTeX · Highlight.js              │
└──────────────────────────┬─────────────────────────────────────┘
                           │  REST API + WebSocket
┌──────────────────────────▼─────────────────────────────────────┐
│  Backend — FastAPI + Uvicorn (ASGI)                            │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐ ┌───────────────┐  │
│  │  Tasks   │ │  Search  │ │ Attachments │ │  Undo / Redo  │  │
│  └──────────┘ └──────────┘ └─────────────┘ └───────────────┘  │
│  ┌──────────┐ ┌───────────────────┐ ┌───────────────────────┐  │
│  │WebSocket │ │  Data Management  │ │  Dependency Injection │  │
│  └──────────┘ └───────────────────┘ └───────────────────────┘  │
└──────────────────────────┬─────────────────────────────────────┘
                           │  aiosqlite (async)
┌──────────────────────────▼─────────────────────────────────────┐
│  SQLite Database (WAL mode)                                    │
│  Task · TaskClosure · TaskFTS · Blob · Attachment · UndoLog    │
│  FTS5 triggers · Foreign keys · Schema migrations (v3)         │
└────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology |
|-------|-----------|
| **Language** | Python 3.10+ |
| **Web Framework** | FastAPI 0.104+ |
| **ASGI Server** | Uvicorn 0.24+ |
| **Validation** | Pydantic v2 |
| **Database** | SQLite via aiosqlite (async) |
| **Search** | SQLite FTS5 (full-text) |
| **Hierarchy** | Closure-table pattern |
| **Frontend** | Vanilla JavaScript (ES6+), HTML5, CSS3 |
| **Rendering** | Marked.js, KaTeX, Highlight.js |
| **Icons** | Lucide |
| **Fonts** | Bricolage Grotesque, Plus Jakarta Sans, IBM Plex Mono |

### Database Schema

The database uses a closure-table model for infinite hierarchy, FTS5 for search, and content-addressable blob storage for attachments:

| Table | Purpose |
|-------|---------|
| `Task` | Core task data (title, description, status, priority, dates) |
| `TaskClosure` | Ancestor-descendant pairs with depth and sort order |
| `TaskFTS` | FTS5 virtual table synced via triggers |
| `Blob` | SHA-256 keyed deduplicated file content metadata |
| `Attachment` | Links blobs to tasks with original filenames |
| `UndoLog` | JSON-Patch operation history for undo/redo |

Schema versioning is managed through `SCHEMA_VERSION` with incremental migrations.

---

## Requirements

| Requirement | Minimum |
|-------------|---------|
| **OS** | Windows 10/11, macOS, Linux |
| **Python** | 3.10 or higher |
| **Disk** | ~100 MB (app + dependencies) |
| **RAM** | 256 MB (512 MB recommended) |

### Runtime Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| FastAPI | >= 0.104.0 | Async web framework |
| Uvicorn | >= 0.24.0 | ASGI server |
| Pydantic | >= 2.5.0 | Data validation and serialization |
| aiosqlite | >= 0.19.0 | Async SQLite driver |
| python-multipart | >= 0.0.6 | Multipart form / file upload handling |
| python-dateutil | >= 2.8.0 | Flexible date parsing |

---

## Installation

### Clone the Repository

```bash
git clone https://github.com/your-username/local-first-todo.git
cd local-first-todo
```

### Windows

Run the included setup script to create a virtual environment and install all dependencies:

```
"0 setup_venv.bat"
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Offline / Air-Gapped Installation

On an internet-connected machine, pre-download packages:

```bash
pip download -r requirements.txt -d ./offline_packages
```

Transfer the entire project directory to the target machine, then run:

```
"0 setup_venv_offline.bat"
```

### Development Installation

```bash
pip install -r requirements-dev.txt
```

Or via `pyproject.toml` extras:

```bash
pip install -e ".[dev]"
```

---

## Quick Start

**Windows:**

```batch
"0 setup_venv.bat"
"1 run_server.bat"
```

**Linux / macOS:**

```bash
source .venv/bin/activate
export PYTHONPATH="$(pwd)/src:$PYTHONPATH"
python -m local_first_todo.main
```

Then open **http://127.0.0.1:8765** in your browser.

---

## Usage

### Server Management (Windows)

| Script | Description |
|--------|-------------|
| `1 run_server.bat` | Start server with console output |
| `1 run_server - without console.bat` | Start server minimized |
| `1 run_server - without console.vbs` | Start server hidden (background) |
| `2 stop_server.bat` | Stop the running server |

### Keyboard Shortcuts

Press <kbd>?</kbd> at any time to view the shortcuts modal.

#### Navigation

| Key | Action |
|-----|--------|
| <kbd>/</kbd> | Focus search |
| <kbd>↑</kbd> <kbd>↓</kbd> | Navigate task list |
| <kbd>←</kbd> <kbd>→</kbd> | Collapse / Expand node |
| <kbd>Enter</kbd> | Open task detail |
| <kbd>Esc</kbd> | Close / Cancel |

#### Actions

| Key | Action |
|-----|--------|
| <kbd>N</kbd> | Create new task |
| <kbd>+</kbd> | Add subtask to selected |
| <kbd>Space</kbd> | Toggle completion |
| <kbd>Delete</kbd> | Delete task |
| <kbd>E</kbd> | Expand all |
| <kbd>C</kbd> | Collapse all |

#### Edit

| Key | Action |
|-----|--------|
| <kbd>Ctrl</kbd>+<kbd>Z</kbd> | Undo |
| <kbd>Ctrl</kbd>+<kbd>Y</kbd> | Redo |

---

## API Reference

All endpoints are versioned under `/api/v1/`. Interactive API documentation is available at:

- **Swagger UI** — `http://127.0.0.1:8765/api/docs`
- **ReDoc** — `http://127.0.0.1:8765/api/redoc`

### Tasks — `/api/v1/tasks`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | List all tasks |
| `GET` | `/root` | List root-level tasks |
| `GET` | `/tree` | Full task tree (single optimized request) |
| `GET` | `/{id}` | Get task by ID |
| `GET` | `/uuid/{uuid}` | Get task by UUID |
| `GET` | `/status/{status}` | Filter tasks by status |
| `POST` | `/` | Create a new task |
| `PUT` | `/{id}` | Update a task |
| `DELETE` | `/{id}` | Soft delete (or hard delete with `?hard_delete=true`) |
| `POST` | `/{id}/restore` | Restore a soft-deleted task |
| `GET` | `/{id}/children` | Direct children |
| `GET` | `/{id}/descendants` | All descendants |
| `GET` | `/{id}/ancestors` | All ancestors |
| `PUT` | `/{id}/move` | Move task to a new parent |
| `POST` | `/{parent_id}/reorder` | Reorder children |
| `POST` | `/{id}/complete-tree` | Complete task and all descendants |
| `POST` | `/bulk` | Bulk operations |

### Attachments — `/api/v1/attachments`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/upload/{task_id}` | Upload a file attachment |
| `GET` | `/download/{attachment_id}` | Download a file |
| `GET` | `/task/{task_id}` | List attachments for a task |
| `DELETE` | `/{attachment_id}` | Delete an attachment |
| `GET` | `/stats` | Attachment storage statistics |
| `GET` | `/quota` | Current quota usage |

### Search — `/api/v1/search`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/` | Full-text search |
| `GET` | `/dashboard` | Dashboard aggregations |
| `GET` | `/suggestions` | Search auto-complete |
| `GET` | `/stats` | Search statistics |

### Undo / Redo — `/api/v1/undo-redo`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/undo` | Undo the last operation |
| `POST` | `/redo` | Redo the last undone operation |
| `GET` | `/status` | Current undo/redo stack status |

### Data Management — `/api/v1/data`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/sync` | Get delta changes since a given revision |
| `GET` | `/integrity` | Run database integrity check |
| `POST` | `/export` | Export data archive *(planned)* |
| `POST` | `/import` | Import data archive *(planned)* |

### WebSocket — `/api/v1/ws`

Real-time event stream for multi-tab synchronization. Events are broadcast on task create, update, delete, move, and reorder.

### Other Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Serve the SPA |
| `GET` | `/health` | Health check (returns version and DB status) |

---

## Development

### Project Structure

```
local-first-todo/
├── src/local_first_todo/        # Application package
│   ├── main.py                  # FastAPI app factory & entry point
│   ├── dependencies.py          # Dependency injection container
│   ├── api/                     # Route handlers
│   │   ├── tasks.py             # Task CRUD & hierarchy endpoints
│   │   ├── attachments.py       # File attachment endpoints
│   │   ├── search.py            # FTS5 search & dashboard endpoints
│   │   ├── undo_redo.py         # Undo/redo endpoints
│   │   ├── data.py              # Export, import, sync, integrity
│   │   └── websocket.py         # WebSocket handler & health check
│   ├── database/                # Data layer
│   │   ├── manager.py           # Connection pool & initialization
│   │   ├── schema.py            # DDL, migrations, pragmas, FTS triggers
│   │   ├── models.py            # Dataclass models & enums
│   │   └── crud.py              # Repository pattern CRUD operations
│   └── services/                # Business logic
│       ├── attachment_service.py # CAS storage, dedup, security, quota
│       ├── search_service.py    # FTS5 query building & dashboard
│       └── undo_redo_service.py # JSON-Patch based undo/redo engine
├── static/                      # Frontend SPA assets
│   ├── index.html               # Single-page application shell
│   ├── css/app.css              # Aurora dark theme styles
│   ├── js/app.js                # Client-side application logic
│   ├── js/vendor/               # Vendored libraries (offline-ready)
│   └── fonts/                   # Self-hosted web fonts
├── tests/                       # Test suite
│   ├── conftest.py              # Fixtures & custom test reporting
│   └── test_comprehensive.py    # Consolidated test suite
├── scripts/                     # Utility scripts
│   ├── clean_db.py              # Database cleanup utility
│   ├── run_all_tests.py         # Test runner helpers
│   └── run_comprehensive_tests.py
├── pyproject.toml               # Package metadata, tool configs
├── requirements.txt             # Runtime dependencies
├── requirements-dev.txt         # Development dependencies
├── noxfile.py                   # Nox automation sessions
├── LICENSE                      # MIT License
└── *.bat / *.vbs                # Windows convenience scripts
```

### Running Tests

```bash
# Activate virtual environment
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate.bat       # Windows

# Run full test suite
python -m pytest

# Run with coverage report
python -m pytest --cov=local_first_todo --cov-report=html

# Skip slow tests
python -m pytest -m "not slow"

# Performance tests only
python -m pytest -m perf
```

#### Nox Sessions

```bash
nox -s lint         # Ruff + mypy
nox -s test         # Full suite with coverage (85% threshold)
nox -s test_fast    # Fast tests only (no slow/perf/fuzz/browser)
nox -s test_perf    # Performance benchmarks
nox -s safety       # Dependency vulnerability audit
nox -s clean        # Remove build artifacts and caches
```

#### Windows Batch Scripts

| Script | Description |
|--------|-------------|
| `3 run_tests.bat` | Run pytest |
| `3 run_phase_tests.bat` | Run phase integration tests |
| `6 run_comprehensive_tests.bat` | Full comprehensive test suite |
| `6a run_fast_tests.bat` | Fast tests only |
| `6b run_single_test.bat` | Run a single test by name |
| `6c run_tests_with_coverage.bat` | Tests with HTML coverage report |

### Code Quality

| Tool | Purpose | Config |
|------|---------|--------|
| [Ruff](https://docs.astral.sh/ruff/) | Linting & formatting | `pyproject.toml` — `[tool.ruff]` |
| [mypy](https://mypy-lang.org/) | Static type checking (strict mode) | `pyproject.toml` — `[tool.mypy]` |
| [pytest](https://pytest.org/) | Testing framework (async mode) | `pyproject.toml` — `[tool.pytest]` |
| [Coverage.py](https://coverage.readthedocs.io/) | Code coverage (85% threshold) | `pyproject.toml` — `[tool.coverage]` |
| [Nox](https://nox.thea.codes/) | Session automation | `noxfile.py` |

Ruff rules enforced: `E`, `W`, `F`, `I`, `B`, `C4`, `UP`, `SIM` — covering pycodestyle, pyflakes, isort, bugbear, comprehensions, pyupgrade, and simplify.

---

## Configuration

### Server Defaults

| Parameter | Default | Description |
|-----------|---------|-------------|
| Host | `0.0.0.0` | Listen address |
| Port | `8765` | Listen port |
| Database | `./app.db` | SQLite database file (CWD-relative) |
| Attachments | `./attachments/` | Blob storage directory |

### Attachment Security

Defaults are optimized for local-first / air-gapped environments:

| Setting | Default | Description |
|---------|---------|-------------|
| `DEFAULT_MAX_ATTACHMENT_SIZE` | 500 MB | Maximum single file size |
| `ALLOW_ALL_EXTENSIONS` | `True` | Accept any file extension |
| `BLOCK_EXECUTABLES` | `False` | Block `.exe`, `.bat`, `.vbs`, etc. |
| `SKIP_SIGNATURE_VALIDATION` | `True` | Skip magic-byte validation |

These can be adjusted in `src/local_first_todo/services/attachment_service.py`.

### Database Pragmas

Applied on every connection for performance and safety:

```
PRAGMA foreign_keys = ON
PRAGMA journal_mode = WAL
PRAGMA synchronous = NORMAL
PRAGMA temp_store = MEMORY
PRAGMA cache_size = -64000        -- 64 MB
```

---

## Security

### Design Principles

1. **Local-only by design** — No outbound network calls; CORS restricted to `localhost`
2. **Data sovereignty** — All data in a single SQLite file under user control
3. **Content-addressable storage** — Attachments stored by SHA-256 hash
4. **Crash safety** — WAL journaling, two-phase undo log, foreign key constraints

### File Upload Hardening

- Path traversal prevention (`../` sequences blocked)
- Windows reserved name blocking (`CON`, `PRN`, `NUL`, `COM1`–`9`, `LPT1`–`9`)
- Dangerous character sanitization in filenames
- Configurable executable blocking and extension whitelisting
- Optional MIME-type / magic-byte signature validation

### Database Security

- Foreign key constraints enforced at the connection level
- Parameterized queries throughout (SQL injection prevention)
- ISO 8601 UTC timestamp validation via `CHECK` constraints
- Optimistic concurrency control via `revision` column

---

## Contributing

Contributions are welcome. Please follow this workflow:

1. **Fork** the repository
2. **Create** a feature branch — `git checkout -b feature/your-feature`
3. **Implement** your changes with type hints and tests
4. **Validate** — `python -m pytest && ruff check . --fix`
5. **Commit** — `git commit -m "Add your feature"`
6. **Push** — `git push origin feature/your-feature`
7. **Open** a Pull Request

### Guidelines

- Follow [PEP 8](https://peps.python.org/pep-0008/) conventions (enforced by Ruff)
- Add type annotations to all public functions
- Write tests for new features and bug fixes
- Keep commits atomic and descriptive
- Update documentation for user-facing changes

---

## License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) — High-performance async web framework
- [SQLite](https://www.sqlite.org/) — The most deployed database engine in the world
- [Lucide](https://lucide.dev/) — Beautiful open-source icon library
- [Marked.js](https://marked.js.org/) — Markdown parser and renderer
- [KaTeX](https://katex.org/) — Fast LaTeX math rendering
- [Highlight.js](https://highlightjs.org/) — Syntax highlighting for code blocks
- [Bricolage Grotesque](https://fonts.google.com/specimen/Bricolage+Grotesque), [Plus Jakarta Sans](https://fonts.google.com/specimen/Plus+Jakarta+Sans), [IBM Plex Mono](https://fonts.google.com/specimen/IBM+Plex+Mono) — Typography

---

<div align="center">

Made with care for privacy, performance, and beautiful software.

</div>
