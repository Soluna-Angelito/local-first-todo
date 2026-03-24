"""Main entry point for the Local-First To-Do application."""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from local_first_todo import __version__
from local_first_todo.database.manager import DatabaseManager
from local_first_todo.database.crud import TaskRepository
from local_first_todo.services.undo_redo_service import UndoRedoService
from local_first_todo.services.search_service import SearchService
from local_first_todo.services.attachment_service import AttachmentService
from local_first_todo import dependencies

logger = logging.getLogger(__name__)

# Global database manager and repository
db_manager: DatabaseManager
task_repository: TaskRepository
undo_redo_service: UndoRedoService
search_service: SearchService
attachment_service: AttachmentService
websocket_connections: set[WebSocket] = set()

# Database write lock for concurrency control
db_write_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan context manager for startup and shutdown."""
    global db_manager, task_repository, undo_redo_service, search_service, attachment_service
    
    logger.info(f"Starting Local-First To-Do v{__version__}")
    
    # Initialize database
    db_path = Path.cwd() / "app.db"
    logger.info(f"Using database: {db_path}")
    
    db_manager = DatabaseManager(str(db_path))
    await db_manager.initialize()
    
    task_repository = TaskRepository(db_manager)
    
    # Initialize undo/redo service
    undo_redo_service = UndoRedoService(db_manager)
    await undo_redo_service.initialize()

    # Initialize search service
    search_service = SearchService(db_manager)

    # Initialize attachment service
    attachments_dir = Path.cwd() / "attachments"
    attachment_service = AttachmentService(db_manager, attachments_dir)

    # Set dependencies for dependency injection
    dependencies.set_database_manager(db_manager)
    dependencies.set_task_repository(task_repository)
    dependencies.set_db_write_lock(db_write_lock)
    dependencies.set_undo_redo_service(undo_redo_service)
    dependencies.set_search_service(search_service)
    dependencies.set_attachment_service(attachment_service)
    
    # Start WebSocket health check background task
    from local_first_todo.api.websocket import websocket_health_check
    ws_health_task = asyncio.create_task(websocket_health_check())
    
    logger.info("Application startup complete")
    
    yield
    
    # Cleanup
    logger.info("Shutting down application")
    
    # Cancel WebSocket health check task
    ws_health_task.cancel()
    try:
        await ws_health_task
    except asyncio.CancelledError:
        pass
    
    await db_manager.close()
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    # OpenAPI tags metadata for organizing endpoints
    tags_metadata = [
        {
            "name": "tasks",
            "description": "Task management operations including CRUD, hierarchy, reordering, and bulk operations.",
        },
        {
            "name": "attachments",
            "description": "File attachment operations including upload, download, and quota management.",
        },
        {
            "name": "undo-redo",
            "description": "Undo and redo operations for reversible task modifications.",
        },
        {
            "name": "search",
            "description": "Advanced search, filtering, and dashboard queries for tasks.",
        },
        {
            "name": "data-management",
            "description": "Data import/export, synchronization, and database integrity operations.",
        },
        {
            "name": "default",
            "description": "Application health and status endpoints.",
        },
    ]
    
    app = FastAPI(
        title="Local-First To-Do",
        description="""
## Overview

A **local-first task management application** with hierarchical task organization, 
file attachments, and full undo/redo support.

## Features

- **Hierarchical Tasks**: Organize tasks in unlimited nested hierarchies with drag-and-drop reordering
- **File Attachments**: Attach files to tasks with content-addressed deduplication
- **Full-Text Search**: Fast search across task titles and descriptions using FTS5
- **Undo/Redo**: Complete undo/redo history for all task operations
- **Real-time Updates**: WebSocket support for live synchronization
- **Local-First**: All data stored locally in SQLite with WAL mode for performance

## API Versioning

All API endpoints are prefixed with `/api/v1/`. The current version is **v1**.

## Error Handling

Errors follow [RFC 7807](https://tools.ietf.org/html/rfc7807) Problem Details format:

```json
{
  "type": "error_type",
  "title": "Human-readable title",
  "status": 400,
  "detail": "Detailed error description"
}
```
        """,
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_tags=tags_metadata,
        license_info={
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT",
        },
        contact={
            "name": "Local-First To-Do",
            "url": "https://github.com/Soluna-Angelito/local-first-todo",
        },
    )
    
    # CORS middleware for local development
    # Note: For a local-first app, we use allow_origin_regex to match any localhost port
    # This is safe because the app only runs locally and isn't exposed to the internet
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Security headers middleware (simplified to avoid blocking external resources)
    @app.middleware("http")
    async def add_security_headers(request, call_next):
        response = await call_next(request)
        response.headers["Permissions-Policy"] = "interest-cohort=()"
        return response
    
    # Include API routes
    from local_first_todo.api import tasks, websocket, attachments, undo_redo, search, data
    app.include_router(tasks.router, prefix="/api/v1")
    app.include_router(attachments.router, prefix="/api/v1")
    app.include_router(undo_redo.router, prefix="/api/v1")
    app.include_router(search.router, prefix="/api/v1")
    app.include_router(data.router, prefix="/api/v1")
    app.include_router(websocket.router, prefix="/api/v1")
    
    # Static files
    app.mount("/static", StaticFiles(directory="static"), name="static")
    
    @app.get("/")
    async def root():
        """Serve the main application."""
        return FileResponse("static/index.html")
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        # Get database manager from dependencies to support test context
        try:
            db_mgr = dependencies.get_database_manager()
            db_status = "connected" if db_mgr else "not_connected"
        except Exception:
            db_status = "not_connected"
        
        return {
            "status": "healthy",
            "version": __version__,
            "database": db_status
        }
    
    return app


def main() -> None:
    """Main entry point for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    app = create_app()
    
    # Run the server
    uvicorn.run(
        app,
        # host="127.0.0.1",
        host="0.0.0.0",
        port=8765,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    main()
