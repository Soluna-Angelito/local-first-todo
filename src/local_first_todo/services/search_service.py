"""Search service for Local-First To-Do application.

This module provides comprehensive search functionality including:
- Full-text search using FTS5
- Advanced filtering by status, priority, due dates
- Dashboard queries for today's tasks and overdue items
- Sorting and result ranking
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from enum import Enum

from local_first_todo.database.manager import DatabaseManager
from local_first_todo.database.models import Task, TaskStatus

logger = logging.getLogger(__name__)


class SortBy(str, Enum):
    """Sort options for search results."""
    
    RELEVANCE = "relevance"
    CREATED_DATE = "created_date"
    UPDATED_DATE = "updated_date"
    DUE_DATE = "due_date"
    PRIORITY = "priority"
    TITLE = "title"


class SortOrder(str, Enum):
    """Sort order options."""
    
    ASC = "asc"
    DESC = "desc"


class SearchFilters:
    """Search filters for advanced queries."""
    
    def __init__(
        self,
        statuses: Optional[List[TaskStatus]] = None,
        min_priority: Optional[int] = None,
        max_priority: Optional[int] = None,
        due_date_from: Optional[str] = None,
        due_date_to: Optional[str] = None,
        created_from: Optional[str] = None,
        created_to: Optional[str] = None,
        has_due_date: Optional[bool] = None,
        overdue_only: bool = False,
        today_only: bool = False,
        upcoming_days: Optional[int] = None
    ):
        """Initialize search filters.
        
        Args:
            statuses: List of task statuses to include
            min_priority: Minimum priority (1-5)
            max_priority: Maximum priority (1-5)
            due_date_from: Earliest due date (ISO format)
            due_date_to: Latest due date (ISO format)
            created_from: Earliest creation date (ISO format)
            created_to: Latest creation date (ISO format)
            has_due_date: Filter by presence of due date
            overdue_only: Show only overdue tasks
            today_only: Show only tasks due today
            upcoming_days: Show tasks due in next N days
        """
        self.statuses = statuses or [TaskStatus.PENDING, TaskStatus.IN_PROGRESS]
        self.min_priority = min_priority
        self.max_priority = max_priority
        self.due_date_from = due_date_from
        self.due_date_to = due_date_to
        self.created_from = created_from
        self.created_to = created_to
        self.has_due_date = has_due_date
        self.overdue_only = overdue_only
        self.today_only = today_only
        self.upcoming_days = upcoming_days


def prepare_fts_query(query: str) -> str:
    """Prepare a raw user query for FTS5 search.
    
    Escapes FTS5 syntax characters and adds prefix matching for the last
    term so raw user input cannot produce FTS5 syntax errors.
    
    Args:
        query: Raw search query
        
    Returns:
        FTS5-formatted query string (empty if nothing searchable remains)
    """
    words = query.strip().split()
    if not words:
        return ""
    
    # Escape FTS5 special characters
    escaped_words = []
    for word in words:
        # Remove non-alphanumeric characters except hyphens and underscores
        clean_word = ''.join(c for c in word if c.isalnum() or c in '-_')
        if clean_word:
            escaped_words.append(f'"{clean_word}"')
    
    if not escaped_words:
        return ""
    
    # Add prefix matching for the last word to support autocomplete
    if len(escaped_words) == 1:
        # Single word - try both exact match and prefix
        word = escaped_words[0].strip('"')
        return f'{escaped_words[0]} OR {word}*'
    
    # Multiple words - exact match for all but last, prefix for last
    last_word = escaped_words[-1].strip('"')
    return f'{" AND ".join(escaped_words[:-1])} AND ({escaped_words[-1]} OR {last_word}*)'


class SearchService:
    """Service for search and filtering operations."""
    
    def __init__(self, db_manager: DatabaseManager):
        """Initialize the search service.
        
        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager
    
    async def search_tasks(
        self,
        query: Optional[str] = None,
        filters: Optional[SearchFilters] = None,
        sort_by: SortBy = SortBy.RELEVANCE,
        sort_order: SortOrder = SortOrder.DESC,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Task]:
        """Search tasks with full-text search and filtering.
        
        Args:
            query: Full-text search query
            filters: Search filters
            sort_by: Sort field
            sort_order: Sort direction
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List of matching tasks
        """
        if filters is None:
            filters = SearchFilters()
        
        # Build SQL query components
        select_clause = "SELECT t.*"
        from_clause = "FROM Task t"
        join_clauses = []
        where_conditions = []
        order_clause = ""
        params = []
        
        # Add FTS5 search if query provided
        if query and query.strip():
            # Join with FTS table
            join_clauses.append("JOIN TaskFTS fts ON t.id = fts.rowid")
            where_conditions.append("TaskFTS MATCH ?")
            params.append(self._prepare_fts_query(query.strip()))
            
            # Use relevance ranking for search queries
            if sort_by == SortBy.RELEVANCE:
                select_clause = "SELECT t.*, bm25(TaskFTS) as relevance_score"
                order_clause = "ORDER BY relevance_score"
                if sort_order == SortOrder.DESC:
                    order_clause += " DESC"
        
        # Apply filters
        where_conditions.extend(self._build_filter_conditions(filters, params))
        
        # Build ORDER BY clause for non-FTS queries
        if not order_clause:
            order_clause = self._build_order_clause(sort_by, sort_order)
        
        # Combine query components
        sql_parts = [select_clause, from_clause]
        if join_clauses:
            sql_parts.extend(join_clauses)
        
        if where_conditions:
            sql_parts.append("WHERE " + " AND ".join(where_conditions))
        
        sql_parts.append(order_clause)
        
        # Add LIMIT and OFFSET
        if limit is not None:
            sql_parts.append(f"LIMIT {limit}")
        if offset > 0:
            sql_parts.append(f"OFFSET {offset}")
        
        # Execute query
        sql = " ".join(sql_parts)
        logger.debug(f"Search query: {sql} with params: {params}")
        
        rows = await self.db_manager.execute_read(sql, tuple(params))
        return [self._row_to_task(row) for row in rows]
    
    async def get_dashboard_tasks(self) -> Dict[str, List[Task]]:
        """Get tasks for the dashboard view.
        
        Returns:
            Dictionary with categorized task lists
        """
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        tomorrow_end = today_end + timedelta(days=1)
        week_end = today_start + timedelta(days=7)
        
        # Format dates for SQLite
        today_str = today_start.strftime("%Y-%m-%dT%H:%M:%SZ")
        today_end_str = today_end.strftime("%Y-%m-%dT%H:%M:%SZ")
        tomorrow_end_str = tomorrow_end.strftime("%Y-%m-%dT%H:%M:%SZ")
        week_end_str = week_end.strftime("%Y-%m-%dT%H:%M:%SZ")
        now_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        dashboard_data = {}
        
        # Overdue tasks
        overdue_filters = SearchFilters(
            statuses=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS],
            due_date_to=now_str
        )
        dashboard_data["overdue"] = await self.search_tasks(
            filters=overdue_filters,
            sort_by=SortBy.DUE_DATE,
            sort_order=SortOrder.ASC,
            limit=10
        )
        
        # Today's tasks
        # Priority: 1=Urgent (highest), 2=High, 3=Medium, 4=Low (lowest)
        # Use ASC order so urgent tasks (priority 1) come first
        today_filters = SearchFilters(
            statuses=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS],
            due_date_from=today_str,
            due_date_to=today_end_str
        )
        dashboard_data["today"] = await self.search_tasks(
            filters=today_filters,
            sort_by=SortBy.PRIORITY,
            sort_order=SortOrder.ASC,  # ASC: priority 1 (Urgent) comes first
            limit=10
        )
        
        # Tomorrow's tasks
        tomorrow_filters = SearchFilters(
            statuses=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS],
            due_date_from=today_end_str,
            due_date_to=tomorrow_end_str
        )
        dashboard_data["tomorrow"] = await self.search_tasks(
            filters=tomorrow_filters,
            sort_by=SortBy.PRIORITY,
            sort_order=SortOrder.ASC,  # ASC: priority 1 (Urgent) comes first
            limit=5
        )
        
        # This week's tasks
        week_filters = SearchFilters(
            statuses=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS],
            due_date_from=tomorrow_end_str,
            due_date_to=week_end_str
        )
        dashboard_data["this_week"] = await self.search_tasks(
            filters=week_filters,
            sort_by=SortBy.DUE_DATE,
            sort_order=SortOrder.ASC,
            limit=5
        )
        
        # Recently completed tasks
        completed_filters = SearchFilters(
            statuses=[TaskStatus.COMPLETED]
        )
        dashboard_data["completed"] = await self.search_tasks(
            filters=completed_filters,
            sort_by=SortBy.UPDATED_DATE,
            sort_order=SortOrder.DESC,
            limit=5
        )
        
        # High priority tasks (no due date)
        # Priority: 1=Urgent, 2=High, 3=Medium, 4=Low (lower number = higher priority)
        # So we want tasks with priority 1 or 2 (max_priority=2 means priority <= 2)
        high_priority_filters = SearchFilters(
            statuses=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS],
            max_priority=2,  # Get tasks with priority 1 (Urgent) or 2 (High)
            has_due_date=False
        )
        dashboard_data["high_priority"] = await self.search_tasks(
            filters=high_priority_filters,
            sort_by=SortBy.PRIORITY,
            sort_order=SortOrder.ASC,  # ASC so priority 1 (Urgent) comes before priority 2 (High)
            limit=5
        )
        
        return dashboard_data
    
    async def get_search_suggestions(self, partial_query: str, limit: int = 5) -> List[str]:
        """Get search suggestions based on partial query.
        
        Args:
            partial_query: Partial search term
            limit: Maximum number of suggestions
            
        Returns:
            List of suggested search terms
        """
        if not partial_query or len(partial_query.strip()) < 2:
            return []
        
        # Search for tasks that contain the partial query
        # This is a simple implementation; could be enhanced with trigrams or other techniques
        query = f"{partial_query.strip()}*"
        
        try:
            # Get matching tasks and extract common terms
            rows = await self.db_manager.execute_read(
                """
                SELECT t.title, t.description FROM Task t
                JOIN TaskFTS fts ON t.id = fts.rowid
                WHERE TaskFTS MATCH ? AND t.deleted_at IS NULL
                LIMIT ?
                """,
                (query, limit * 2)
            )
            
            # Extract words that start with the partial query
            suggestions = set()
            partial_lower = partial_query.lower()
            
            for row in rows:
                # Extract words from title and description
                text = f"{row['title'] or ''} {row['description'] or ''}"
                words = text.lower().split()
                
                for word in words:
                    # Clean word and check if it starts with partial query
                    clean_word = ''.join(c for c in word if c.isalnum())
                    if len(clean_word) > len(partial_lower) and clean_word.startswith(partial_lower):
                        suggestions.add(clean_word)
                        if len(suggestions) >= limit:
                            break
                
                if len(suggestions) >= limit:
                    break
            
            return sorted(list(suggestions))[:limit]
            
        except Exception as e:
            logger.error(f"Error getting search suggestions: {e}")
            return []
    
    async def get_search_stats(self) -> Dict[str, Any]:
        """Get search-related statistics.
        
        Returns:
            Dictionary with search statistics
        """
        try:
            now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            
            # Single aggregation pass instead of one query per status/priority
            rows = await self.db_manager.execute_read(
                """
                SELECT
                    status,
                    priority,
                    COUNT(*) as count,
                    SUM(CASE WHEN next_due_utc IS NOT NULL THEN 1 ELSE 0 END) as with_due_date,
                    SUM(
                        CASE WHEN next_due_utc < ? AND status IN ('pending', 'in_progress')
                        THEN 1 ELSE 0 END
                    ) as overdue
                FROM Task
                WHERE deleted_at IS NULL
                GROUP BY status, priority
                """,
                (now_str,)
            )
            
            status_counts = {status.value: 0 for status in TaskStatus}
            priority_counts = {priority: 0 for priority in range(1, 6)}
            tasks_with_due_dates = 0
            overdue_tasks = 0
            
            for row in rows:
                if row["status"] in status_counts:
                    status_counts[row["status"]] += row["count"]
                if row["priority"] in priority_counts:
                    priority_counts[row["priority"]] += row["count"]
                tasks_with_due_dates += row["with_due_date"] or 0
                overdue_tasks += row["overdue"] or 0
            
            return {
                "total_tasks": sum(status_counts.values()),
                "status_counts": status_counts,
                "tasks_with_due_dates": tasks_with_due_dates,
                "overdue_tasks": overdue_tasks,
                "priority_counts": priority_counts
            }
            
        except Exception as e:
            logger.error(f"Error getting search statistics: {e}")
            return {}
    
    def _prepare_fts_query(self, query: str) -> str:
        """Prepare a query for FTS5 search.
        
        Args:
            query: Raw search query
            
        Returns:
            FTS5-formatted query string
        """
        return prepare_fts_query(query)
    
    def _build_filter_conditions(self, filters: SearchFilters, params: List[Any]) -> List[str]:
        """Build WHERE conditions for filters.
        
        Args:
            filters: Search filters
            params: Parameter list to append to
            
        Returns:
            List of WHERE condition strings
        """
        conditions = []
        
        # Always exclude soft-deleted tasks
        conditions.append("t.deleted_at IS NULL")
        
        # Status filter
        if filters.statuses:
            status_placeholders = ",".join("?" * len(filters.statuses))
            conditions.append(f"t.status IN ({status_placeholders})")
            params.extend([status.value for status in filters.statuses])
        
        # Priority filters
        if filters.min_priority is not None:
            conditions.append("t.priority >= ?")
            params.append(filters.min_priority)
        
        if filters.max_priority is not None:
            conditions.append("t.priority <= ?")
            params.append(filters.max_priority)
        
        # Due date filters
        if filters.overdue_only:
            now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            conditions.append("t.next_due_utc < ?")
            params.append(now_str)
        
        if filters.today_only:
            now = datetime.now(timezone.utc)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)
            conditions.append("t.next_due_utc >= ? AND t.next_due_utc < ?")
            params.extend([
                today_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                today_end.strftime("%Y-%m-%dT%H:%M:%SZ")
            ])
        
        if filters.upcoming_days is not None:
            now = datetime.now(timezone.utc)
            future_date = now + timedelta(days=filters.upcoming_days)
            conditions.append("t.next_due_utc >= ? AND t.next_due_utc <= ?")
            params.extend([
                now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                future_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            ])
        
        if filters.due_date_from:
            conditions.append("t.next_due_utc >= ?")
            params.append(filters.due_date_from)
        
        if filters.due_date_to:
            conditions.append("t.next_due_utc <= ?")
            params.append(filters.due_date_to)
        
        # Creation date filters
        if filters.created_from:
            conditions.append("t.created_at >= ?")
            params.append(filters.created_from)
        
        if filters.created_to:
            conditions.append("t.created_at <= ?")
            params.append(filters.created_to)
        
        # Due date presence filter
        if filters.has_due_date is not None:
            if filters.has_due_date:
                conditions.append("t.next_due_utc IS NOT NULL")
            else:
                conditions.append("t.next_due_utc IS NULL")
        
        return conditions
    
    def _build_order_clause(self, sort_by: SortBy, sort_order: SortOrder) -> str:
        """Build ORDER BY clause.
        
        Args:
            sort_by: Sort field
            sort_order: Sort direction
            
        Returns:
            ORDER BY clause string
        """
        direction = "DESC" if sort_order == SortOrder.DESC else "ASC"
        
        if sort_by == SortBy.CREATED_DATE:
            return f"ORDER BY t.created_at {direction}"
        elif sort_by == SortBy.UPDATED_DATE:
            return f"ORDER BY t.updated_at {direction}"
        elif sort_by == SortBy.DUE_DATE:
            # Handle NULL due dates - put them last
            if sort_order == SortOrder.ASC:
                return "ORDER BY t.next_due_utc IS NULL, t.next_due_utc ASC"
            else:
                return "ORDER BY t.next_due_utc IS NULL, t.next_due_utc DESC"
        elif sort_by == SortBy.PRIORITY:
            # Priority: 1=Urgent (highest), 2=High, 3=Medium, 4=Low (lowest)
            # NULL priorities should come last regardless of sort direction
            if sort_order == SortOrder.ASC:
                # ASC: 1 (Urgent) first, NULL last
                return "ORDER BY t.priority IS NULL, t.priority ASC, t.created_at DESC"
            else:
                # DESC: 4 (Low) first, NULL last - less common use case
                return "ORDER BY t.priority IS NULL, t.priority DESC, t.created_at DESC"
        elif sort_by == SortBy.TITLE:
            return f"ORDER BY t.title {direction}"
        else:
            # Default to creation date
            return f"ORDER BY t.created_at {direction}"
    
    def _row_to_task(self, row) -> Task:
        """Convert a database row to a Task object."""
        return Task(
            id=row["id"],
            uuid=row["uuid"],
            revision=row["revision"],
            title=row["title"],
            description=row["description"],
            recurrence_rrule=row["recurrence_rrule"],
            recurrence_start_utc=row["recurrence_start_utc"],
            next_due_utc=row["next_due_utc"],
            status=TaskStatus(row["status"]),
            priority=row["priority"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            deleted_at=row["deleted_at"]
        ) 