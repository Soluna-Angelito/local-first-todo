"""Search API endpoints for Local-First To-Do application.

This module provides REST API endpoints for advanced search functionality including:
- Advanced search with filters and sorting
- Dashboard queries for categorized tasks
- Search suggestions and autocomplete
- Search statistics
"""

import logging
from typing import List, Optional, Dict

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from local_first_todo.database.models import TaskStatus
from local_first_todo.dependencies import get_search_service
from local_first_todo.services.search_service import SearchService, SearchFilters, SortBy, SortOrder
from local_first_todo.api.tasks import TaskResponse, task_to_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


# Pydantic models for API requests/responses
class AdvancedSearchRequest(BaseModel):
    """Request model for advanced search with multiple filter options."""
    
    query: Optional[str] = Field(
        None, 
        description="Full-text search query (searches title and description)",
        json_schema_extra={"example": "project documentation"}
    )
    statuses: Optional[List[TaskStatus]] = Field(
        None, 
        description="Filter by task statuses (multiple allowed)",
        json_schema_extra={"example": ["pending", "in_progress"]}
    )
    min_priority: Optional[int] = Field(
        None, 
        ge=1, 
        le=5, 
        description="Minimum priority (1=Urgent is highest)",
        json_schema_extra={"example": 1}
    )
    max_priority: Optional[int] = Field(
        None, 
        ge=1, 
        le=5, 
        description="Maximum priority (4=Low is lowest)",
        json_schema_extra={"example": 2}
    )
    due_date_from: Optional[str] = Field(
        None, 
        description="Earliest due date filter (ISO 8601 UTC)",
        json_schema_extra={"example": "2026-02-01T00:00:00Z"}
    )
    due_date_to: Optional[str] = Field(
        None, 
        description="Latest due date filter (ISO 8601 UTC)",
        json_schema_extra={"example": "2026-02-28T23:59:59Z"}
    )
    created_from: Optional[str] = Field(
        None, 
        description="Earliest creation date filter (ISO 8601 UTC)",
        json_schema_extra={"example": "2026-01-01T00:00:00Z"}
    )
    created_to: Optional[str] = Field(
        None, 
        description="Latest creation date filter (ISO 8601 UTC)",
        json_schema_extra={"example": "2026-02-06T23:59:59Z"}
    )
    has_due_date: Optional[bool] = Field(
        None, 
        description="Filter by presence of due date (true=has due date, false=no due date)",
        json_schema_extra={"example": True}
    )
    overdue_only: bool = Field(
        False, 
        description="Show only tasks past their due date",
        json_schema_extra={"example": False}
    )
    today_only: bool = Field(
        False, 
        description="Show only tasks due today",
        json_schema_extra={"example": False}
    )
    upcoming_days: Optional[int] = Field(
        None, 
        ge=1, 
        description="Show tasks due within N days from now",
        json_schema_extra={"example": 7}
    )
    sort_by: SortBy = Field(
        SortBy.RELEVANCE, 
        description="Sort field: relevance, created_at, updated_at, due_date, priority"
    )
    sort_order: SortOrder = Field(
        SortOrder.DESC, 
        description="Sort direction: asc or desc"
    )
    limit: Optional[int] = Field(
        None, 
        ge=1, 
        le=100, 
        description="Maximum results to return (default: no limit)",
        json_schema_extra={"example": 20}
    )
    offset: int = Field(
        0, 
        ge=0, 
        description="Number of results to skip for pagination",
        json_schema_extra={"example": 0}
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "project",
                    "statuses": ["pending", "in_progress"],
                    "min_priority": 1,
                    "max_priority": 2,
                    "sort_by": "priority",
                    "sort_order": "asc",
                    "limit": 20
                },
                {
                    "overdue_only": True,
                    "sort_by": "due_date",
                    "sort_order": "asc"
                }
            ]
        }
    }


class DashboardResponse(BaseModel):
    """Response model for dashboard with categorized task lists."""
    
    overdue: List[TaskResponse] = Field(description="Tasks past their due date")
    today: List[TaskResponse] = Field(description="Tasks due today")
    tomorrow: List[TaskResponse] = Field(description="Tasks due tomorrow")
    this_week: List[TaskResponse] = Field(description="Tasks due within this week (excluding today/tomorrow)")
    completed: List[TaskResponse] = Field(description="Recently completed tasks")
    high_priority: List[TaskResponse] = Field(description="High priority tasks (1-2) without due dates")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "overdue": [],
                    "today": [{"id": 1, "title": "Review PR", "status": "pending"}],
                    "tomorrow": [],
                    "this_week": [{"id": 2, "title": "Write tests", "status": "pending"}],
                    "completed": [{"id": 3, "title": "Setup CI", "status": "completed"}],
                    "high_priority": [{"id": 4, "title": "Fix critical bug", "status": "in_progress"}]
                }
            ]
        }
    }


class SearchSuggestionsResponse(BaseModel):
    """Response model for autocomplete search suggestions."""
    
    suggestions: List[str] = Field(
        description="Suggested search terms based on existing task content",
        json_schema_extra={"example": ["project documentation", "project setup", "project review"]}
    )
    query: str = Field(
        description="The partial query that was searched",
        json_schema_extra={"example": "proj"}
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "suggestions": ["project documentation", "project setup", "project review"],
                    "query": "proj"
                }
            ]
        }
    }


class SearchStatsResponse(BaseModel):
    """Response model for task database statistics."""
    
    total_tasks: int = Field(description="Total number of active tasks", json_schema_extra={"example": 150})
    status_counts: Dict[str, int] = Field(
        description="Count of tasks grouped by status",
        json_schema_extra={"example": {"pending": 80, "in_progress": 25, "completed": 45}}
    )
    tasks_with_due_dates: int = Field(description="Tasks that have a due date set", json_schema_extra={"example": 95})
    overdue_tasks: int = Field(description="Tasks past their due date", json_schema_extra={"example": 5})
    priority_counts: Dict[int, int] = Field(
        description="Count of tasks grouped by priority level",
        json_schema_extra={"example": {"1": 10, "2": 30, "3": 50, "4": 20}}
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "total_tasks": 150,
                    "status_counts": {"pending": 80, "in_progress": 25, "completed": 45},
                    "tasks_with_due_dates": 95,
                    "overdue_tasks": 5,
                    "priority_counts": {"1": 10, "2": 30, "3": 50, "4": 20}
                }
            ]
        }
    }


@router.post(
    "/", 
    response_model=List[TaskResponse],
    summary="Advanced Search",
    response_description="Tasks matching the search criteria"
)
async def advanced_search(
    search_request: AdvancedSearchRequest,
    search_service: SearchService = Depends(get_search_service)
) -> List[TaskResponse]:
    """Perform advanced search with multiple filters and sorting options.
    
    Combine any of the following:
    - **Full-text search** on title and description
    - **Status filter** (multiple statuses allowed)
    - **Priority range** filter
    - **Date filters** (due date, creation date)
    - **Smart filters** (overdue, today, upcoming)
    
    Results can be sorted by relevance, date, or priority.
    """
    try:
        # Create search filters from request
        filters = SearchFilters(
            statuses=search_request.statuses,
            min_priority=search_request.min_priority,
            max_priority=search_request.max_priority,
            due_date_from=search_request.due_date_from,
            due_date_to=search_request.due_date_to,
            created_from=search_request.created_from,
            created_to=search_request.created_to,
            has_due_date=search_request.has_due_date,
            overdue_only=search_request.overdue_only,
            today_only=search_request.today_only,
            upcoming_days=search_request.upcoming_days
        )
        
        # Perform search
        tasks = await search_service.search_tasks(
            query=search_request.query,
            filters=filters,
            sort_by=search_request.sort_by,
            sort_order=search_request.sort_order,
            limit=search_request.limit,
            offset=search_request.offset
        )
        
        return [task_to_response(task) for task in tasks]
        
    except Exception as e:
        logger.error(f"Advanced search failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to perform search"
        )


@router.get(
    "/dashboard", 
    response_model=DashboardResponse,
    summary="Get Dashboard",
    response_description="Categorized task lists for dashboard display"
)
async def get_dashboard(
    search_service: SearchService = Depends(get_search_service)
) -> DashboardResponse:
    """Get pre-categorized task lists optimized for dashboard display.
    
    Returns tasks grouped by:
    - **Overdue**: Past due date
    - **Today**: Due today
    - **Tomorrow**: Due tomorrow  
    - **This week**: Due within 7 days (excluding today/tomorrow)
    - **Completed**: Recently completed tasks
    - **High priority**: Priority 1-2 tasks without due dates
    """
    try:
        dashboard_data = await search_service.get_dashboard_tasks()
        
        return DashboardResponse(
            overdue=[task_to_response(task) for task in dashboard_data["overdue"]],
            today=[task_to_response(task) for task in dashboard_data["today"]],
            tomorrow=[task_to_response(task) for task in dashboard_data["tomorrow"]],
            this_week=[task_to_response(task) for task in dashboard_data["this_week"]],
            completed=[task_to_response(task) for task in dashboard_data["completed"]],
            high_priority=[task_to_response(task) for task in dashboard_data["high_priority"]]
        )
        
    except Exception as e:
        logger.error(f"Dashboard query failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve dashboard data"
        )


@router.get(
    "/suggestions", 
    response_model=SearchSuggestionsResponse,
    summary="Get Search Suggestions",
    response_description="Autocomplete suggestions based on existing tasks"
)
async def get_search_suggestions(
    q: str = Query(..., min_length=2, description="Partial search query (min 2 characters)"),
    limit: int = Query(5, ge=1, le=10, description="Maximum suggestions to return"),
    search_service: SearchService = Depends(get_search_service)
) -> SearchSuggestionsResponse:
    """Get autocomplete suggestions for a partial search query.
    
    Suggestions are based on existing task titles and descriptions.
    Useful for search-as-you-type interfaces.
    """
    try:
        suggestions = await search_service.get_search_suggestions(q, limit)
        
        return SearchSuggestionsResponse(
            suggestions=suggestions,
            query=q
        )
        
    except Exception as e:
        logger.error(f"Search suggestions failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get search suggestions"
        )


@router.get(
    "/stats", 
    response_model=SearchStatsResponse,
    summary="Get Search Stats",
    response_description="Task database statistics and counts"
)
async def get_search_stats(
    search_service: SearchService = Depends(get_search_service)
) -> SearchStatsResponse:
    """Get aggregated statistics about the task database.
    
    Useful for:
    - Dashboard summary widgets
    - Progress tracking
    - Identifying overdue task count
    """
    try:
        stats = await search_service.get_search_stats()
        
        return SearchStatsResponse(
            total_tasks=stats["total_tasks"],
            status_counts=stats["status_counts"],
            tasks_with_due_dates=stats["tasks_with_due_dates"],
            overdue_tasks=stats["overdue_tasks"],
            priority_counts=stats["priority_counts"]
        )
        
    except Exception as e:
        logger.error(f"Search stats failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get search statistics"
        ) 