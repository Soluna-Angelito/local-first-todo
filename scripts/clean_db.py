#!/usr/bin/env python3
"""Database cleanup script for Local-First To-Do application.

This script provides various options for cleaning and maintaining the database:
- Remove all tasks and data
- Remove soft-deleted tasks
- Clean up orphaned attachments
- Reset database to initial state
- Compact database (vacuum)
- Show database statistics
- Fix sort_order gaps and inconsistencies

Usage:
    python scripts/clean_db.py --help
    python scripts/clean_db.py --all
    python scripts/clean_db.py --soft-deleted
    python scripts/clean_db.py --orphaned-attachments
    python scripts/clean_db.py --vacuum
    python scripts/clean_db.py --stats
    python scripts/clean_db.py --fix-sort-order
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from local_first_todo.database.manager import DatabaseManager
from local_first_todo.database.crud import TaskRepository
from local_first_todo.database.models import TaskStatus


class DatabaseCleaner:
    """Database cleanup utility."""
    
    def __init__(self, db_path: str = "app.db"):
        self.db_path = Path(db_path)
        self.attachments_path = Path("attachments")
        self.db_manager = None
        self.task_repository = None
    
    async def initialize(self):
        """Initialize database connections."""
        self.db_manager = DatabaseManager(str(self.db_path))
        await self.db_manager.initialize()
        self.task_repository = TaskRepository(self.db_manager)
        print(f"🔗 Connected to database: {self.db_path}")
    
    async def cleanup(self):
        """Cleanup database connections."""
        if self.db_manager:
            await self.db_manager.close()
            print("🔒 Database connection closed")
    
    async def show_stats(self) -> Dict[str, Any]:
        """Show database statistics."""
        stats = {}
        
        # Task counts by status
        for status in TaskStatus:
            count = len(await self.task_repository.get_tasks_by_status(status))
            stats[f"tasks_{status.value}"] = count
        
        # Total tasks
        all_tasks = await self.task_repository.get_all_tasks()
        stats["tasks_total"] = len(all_tasks)
        
        # Soft-deleted tasks
        soft_deleted = await self.db_manager.execute_read(
            "SELECT COUNT(*) as count FROM Task WHERE deleted_at IS NOT NULL"
        )
        stats["tasks_soft_deleted"] = soft_deleted[0]["count"]
        
        # Attachments count
        attachments = await self.db_manager.execute_read("SELECT COUNT(*) as count FROM Attachment")
        stats["attachments"] = attachments[0]["count"]
        
        # Blobs count
        blobs = await self.db_manager.execute_read("SELECT COUNT(*) as count FROM Blob")
        stats["blobs"] = blobs[0]["count"]
        
        # Undo log entries
        undo_entries = await self.db_manager.execute_read("SELECT COUNT(*) as count FROM UndoLog")
        stats["undo_log_entries"] = undo_entries[0]["count"]
        
        # Task closure entries
        closure_entries = await self.db_manager.execute_read("SELECT COUNT(*) as count FROM TaskClosure")
        stats["task_closure_entries"] = closure_entries[0]["count"]
        
        # Database file size
        if self.db_path.exists():
            stats["db_file_size_mb"] = round(self.db_path.stat().st_size / (1024 * 1024), 2)
        
        # Attachments directory size
        if self.attachments_path.exists():
            total_size = sum(f.stat().st_size for f in self.attachments_path.rglob('*') if f.is_file())
            stats["attachments_size_mb"] = round(total_size / (1024 * 1024), 2)
            stats["attachment_files"] = len(list(self.attachments_path.rglob('*')))
        else:
            stats["attachments_size_mb"] = 0
            stats["attachment_files"] = 0
        
        return stats
    
    async def remove_all_data(self):
        """Remove all tasks and related data."""
        print("🗑️  Removing all tasks and data...")
        
        operations = [
            "DELETE FROM TaskFTS",
            "DELETE FROM UndoLog", 
            "DELETE FROM Attachment",
            "DELETE FROM Blob",
            "DELETE FROM TaskClosure",
            "DELETE FROM Task",
        ]
        
        await self.db_manager.execute_transaction([(op, ()) for op in operations])
        print("✅ All data removed")
    
    async def remove_soft_deleted(self):
        """Remove soft-deleted tasks permanently."""
        print("🗑️  Removing soft-deleted tasks...")
        
        # Get soft-deleted task IDs
        soft_deleted = await self.db_manager.execute_read(
            "SELECT id FROM Task WHERE deleted_at IS NOT NULL"
        )
        
        if not soft_deleted:
            print("ℹ️  No soft-deleted tasks found")
            return
        
        task_ids = [row["id"] for row in soft_deleted]
        placeholders = ",".join("?" * len(task_ids))
        
        operations = [
            (f"DELETE FROM TaskFTS WHERE rowid IN (SELECT id FROM Task WHERE id IN ({placeholders}))", task_ids),
            (f"DELETE FROM UndoLog WHERE command_payload LIKE '%\"task_id\":%' AND json_extract(command_payload, '$.task_id') IN ({placeholders})", task_ids),
            (f"DELETE FROM Attachment WHERE task_id IN ({placeholders})", task_ids),
            (f"DELETE FROM TaskClosure WHERE ancestor_id IN ({placeholders}) OR descendant_id IN ({placeholders})", task_ids + task_ids),
            (f"DELETE FROM Task WHERE id IN ({placeholders})", task_ids),
        ]
        
        await self.db_manager.execute_transaction(operations)
        print(f"✅ Removed {len(task_ids)} soft-deleted tasks")
    
    async def clean_orphaned_attachments(self):
        """Remove orphaned attachments and blobs."""
        print("🧹 Cleaning orphaned attachments...")
        
        # Find orphaned blobs (not referenced by any attachment)
        orphaned_blobs = await self.db_manager.execute_read("""
            SELECT b.sha256 FROM Blob b 
            LEFT JOIN Attachment a ON b.sha256 = a.blob_sha256 
            WHERE a.blob_sha256 IS NULL
        """)
        
        if orphaned_blobs:
            blob_hashes = [row["sha256"] for row in orphaned_blobs]
            placeholders = ",".join("?" * len(blob_hashes))
            
            await self.db_manager.execute_write(
                f"DELETE FROM Blob WHERE sha256 IN ({placeholders})", 
                blob_hashes
            )
            
            # Remove orphaned files from attachments directory
            removed_files = 0
            if self.attachments_path.exists():
                for blob_hash in blob_hashes:
                    file_path = self.attachments_path / blob_hash
                    if file_path.exists():
                        file_path.unlink()
                        removed_files += 1
            
            print(f"✅ Removed {len(blob_hashes)} orphaned blobs and {removed_files} files")
        else:
            print("ℹ️  No orphaned attachments found")
        
        # Find orphaned attachment files (files without database entries)
        if self.attachments_path.exists():
            db_hashes = await self.db_manager.execute_read("SELECT sha256 FROM Blob")
            db_hash_set = {row["sha256"] for row in db_hashes}
            
            orphaned_files = []
            for file_path in self.attachments_path.rglob('*'):
                if file_path.is_file() and file_path.name not in db_hash_set:
                    orphaned_files.append(file_path)
            
            if orphaned_files:
                for file_path in orphaned_files:
                    file_path.unlink()
                print(f"✅ Removed {len(orphaned_files)} orphaned attachment files")
            else:
                print("ℹ️  No orphaned attachment files found")
    
    async def vacuum_database(self):
        """Vacuum the database to reclaim space."""
        print("🗜️  Vacuuming database...")
        
        # Get size before vacuum
        size_before = self.db_path.stat().st_size if self.db_path.exists() else 0
        
        await self.db_manager.execute_write("VACUUM", ())
        
        # Get size after vacuum
        size_after = self.db_path.stat().st_size if self.db_path.exists() else 0
        
        space_saved = size_before - size_after
        print(f"✅ Database vacuumed. Space saved: {space_saved / 1024 / 1024:.2f} MB")
    
    async def reset_database(self):
        """Reset database to initial state (empty but with schema)."""
        from local_first_todo.database.schema import SCHEMA_VERSION
        
        print("🔄 Resetting database to initial state...")
        
        # Remove all data
        await self.remove_all_data()
        
        # Reset schema version user_version to current version
        await self.db_manager.execute_write(f"PRAGMA user_version = {SCHEMA_VERSION}", ())
        
        # Vacuum to reclaim space
        await self.vacuum_database()
        
        print("✅ Database reset to initial state")
    
    async def clean_undo_log(self, keep_entries: int = 1000):
        """Clean old undo log entries, keeping only the most recent ones."""
        print(f"🧹 Cleaning undo log (keeping {keep_entries} entries)...")
        
        total_entries = await self.db_manager.execute_read("SELECT COUNT(*) as count FROM UndoLog")
        total_count = total_entries[0]["count"]
        
        if total_count <= keep_entries:
            print(f"ℹ️  Only {total_count} entries found, no cleanup needed")
            return
        
        # Delete old entries
        await self.db_manager.execute_write(f"""
            DELETE FROM UndoLog 
            WHERE id NOT IN (
                SELECT id FROM UndoLog 
                ORDER BY applied_at DESC 
                LIMIT {keep_entries}
            )
        """, ())
        
        entries_removed = total_count - keep_entries
        print(f"✅ Removed {entries_removed} old undo log entries")
    
    async def fix_sort_order(self):
        """Fix sort_order gaps and inconsistencies in TaskClosure table.
        
        This function:
        1. Removes orphaned TaskClosure entries (referencing deleted tasks)
        2. Adds missing self-references (depth=0) for tasks
        3. Normalizes sort_order to be consecutive (1, 2, 3, ...) for each parent
        """
        print("🔧 Fixing sort_order inconsistencies...")
        
        total_fixed = 0
        
        # Step 1: Remove orphaned TaskClosure entries
        print("  → Checking for orphaned TaskClosure entries...")
        orphaned = await self.db_manager.execute_read("""
            SELECT tc.ancestor_id, tc.descendant_id, tc.depth
            FROM TaskClosure tc
            LEFT JOIN Task t1 ON tc.ancestor_id = t1.id
            LEFT JOIN Task t2 ON tc.descendant_id = t2.id
            WHERE t1.id IS NULL OR t2.id IS NULL
        """)
        
        if orphaned:
            await self.db_manager.execute_write("""
                DELETE FROM TaskClosure 
                WHERE ancestor_id NOT IN (SELECT id FROM Task)
                   OR descendant_id NOT IN (SELECT id FROM Task)
            """, ())
            print(f"    ✅ Removed {len(orphaned)} orphaned TaskClosure entries")
            total_fixed += len(orphaned)
        else:
            print("    ✅ No orphaned entries found")
        
        # Step 2: Add missing self-references (depth=0) for all tasks
        print("  → Checking for missing self-references...")
        missing_self_refs = await self.db_manager.execute_read("""
            SELECT t.id FROM Task t
            WHERE t.deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM TaskClosure tc 
                  WHERE tc.ancestor_id = t.id AND tc.descendant_id = t.id AND tc.depth = 0
              )
        """)
        
        if missing_self_refs:
            operations = []
            for row in missing_self_refs:
                task_id = row["id"]
                operations.append((
                    "INSERT INTO TaskClosure (ancestor_id, descendant_id, depth, sort_order) VALUES (?, ?, 0, 0)",
                    (task_id, task_id)
                ))
            await self.db_manager.execute_transaction(operations)
            print(f"    ✅ Added {len(missing_self_refs)} missing self-references")
            total_fixed += len(missing_self_refs)
        else:
            print("    ✅ All self-references present")
        
        # Step 3: Normalize sort_order for root-level tasks (depth=0)
        print("  → Normalizing root-level task sort_order...")
        root_tasks = await self.db_manager.execute_read("""
            SELECT tc.descendant_id, tc.sort_order
            FROM TaskClosure tc
            JOIN Task t ON tc.descendant_id = t.id
            WHERE tc.depth = 0 
              AND tc.ancestor_id = tc.descendant_id
              AND t.deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM TaskClosure tc2 
                  WHERE tc2.descendant_id = tc.descendant_id AND tc2.depth = 1
              )
            ORDER BY tc.sort_order, t.created_at
        """)
        
        if root_tasks:
            operations = []
            root_fixed = 0
            for index, row in enumerate(root_tasks):
                new_sort_order = index + 1
                if row["sort_order"] != new_sort_order:
                    operations.append((
                        "UPDATE TaskClosure SET sort_order = ? WHERE ancestor_id = ? AND descendant_id = ? AND depth = 0",
                        (new_sort_order, row["descendant_id"], row["descendant_id"])
                    ))
                    root_fixed += 1
            
            if operations:
                await self.db_manager.execute_transaction(operations)
                print(f"    ✅ Fixed {root_fixed} root-level sort_order values")
                total_fixed += root_fixed
            else:
                print("    ✅ Root-level sort_order already normalized")
        
        # Step 4: Normalize sort_order for each parent's children (depth=1)
        print("  → Normalizing child task sort_order for each parent...")
        
        # Get all unique parents
        parents = await self.db_manager.execute_read("""
            SELECT DISTINCT tc.ancestor_id 
            FROM TaskClosure tc
            JOIN Task t ON tc.ancestor_id = t.id
            WHERE tc.depth = 1 AND t.deleted_at IS NULL
        """)
        
        child_fixed = 0
        for parent_row in parents:
            parent_id = parent_row["ancestor_id"]
            
            # Get children of this parent ordered by current sort_order
            children = await self.db_manager.execute_read("""
                SELECT tc.descendant_id, tc.sort_order
                FROM TaskClosure tc
                JOIN Task t ON tc.descendant_id = t.id
                WHERE tc.ancestor_id = ? AND tc.depth = 1 AND t.deleted_at IS NULL
                ORDER BY tc.sort_order, t.created_at
            """, (parent_id,))
            
            operations = []
            for index, child_row in enumerate(children):
                new_sort_order = index + 1
                if child_row["sort_order"] != new_sort_order:
                    operations.append((
                        "UPDATE TaskClosure SET sort_order = ? WHERE ancestor_id = ? AND descendant_id = ? AND depth = 1",
                        (new_sort_order, parent_id, child_row["descendant_id"])
                    ))
                    child_fixed += 1
            
            if operations:
                await self.db_manager.execute_transaction(operations)
        
        if child_fixed > 0:
            print(f"    ✅ Fixed {child_fixed} child sort_order values")
            total_fixed += child_fixed
        else:
            print("    ✅ Child sort_order already normalized")
        
        # Step 5: Show sort_order statistics
        print("  → Generating sort_order statistics...")
        stats = await self._get_sort_order_stats()
        print(f"    📊 Root tasks: {stats['root_tasks']}")
        print(f"    📊 Total parent-child relationships: {stats['parent_child_relations']}")
        print(f"    📊 Max root sort_order: {stats['max_root_sort']}")
        print(f"    📊 Max child sort_order: {stats['max_child_sort']}")
        
        print(f"✅ Sort order fix completed. Total fixes: {total_fixed}")
        return total_fixed
    
    async def _get_sort_order_stats(self) -> Dict[str, Any]:
        """Get statistics about sort_order in TaskClosure."""
        stats = {}
        
        # Count root tasks
        root_count = await self.db_manager.execute_read("""
            SELECT COUNT(*) as count FROM TaskClosure tc
            JOIN Task t ON tc.descendant_id = t.id
            WHERE tc.depth = 0 AND tc.ancestor_id = tc.descendant_id
              AND t.deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM TaskClosure tc2 
                  WHERE tc2.descendant_id = tc.descendant_id AND tc2.depth = 1
              )
        """)
        stats['root_tasks'] = root_count[0]['count'] if root_count else 0
        
        # Count parent-child relationships
        child_count = await self.db_manager.execute_read("""
            SELECT COUNT(*) as count FROM TaskClosure tc
            JOIN Task t ON tc.descendant_id = t.id
            WHERE tc.depth = 1 AND t.deleted_at IS NULL
        """)
        stats['parent_child_relations'] = child_count[0]['count'] if child_count else 0
        
        # Max sort_order for root tasks
        max_root = await self.db_manager.execute_read("""
            SELECT MAX(tc.sort_order) as max_sort FROM TaskClosure tc
            JOIN Task t ON tc.descendant_id = t.id
            WHERE tc.depth = 0 AND tc.ancestor_id = tc.descendant_id
              AND t.deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM TaskClosure tc2 
                  WHERE tc2.descendant_id = tc.descendant_id AND tc2.depth = 1
              )
        """)
        stats['max_root_sort'] = max_root[0]['max_sort'] if max_root and max_root[0]['max_sort'] else 0
        
        # Max sort_order for children
        max_child = await self.db_manager.execute_read("""
            SELECT MAX(sort_order) as max_sort FROM TaskClosure WHERE depth = 1
        """)
        stats['max_child_sort'] = max_child[0]['max_sort'] if max_child and max_child[0]['max_sort'] else 0
        
        return stats


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Database cleanup utility for Local-First To-Do application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/clean_db.py --stats              # Show database statistics
    python scripts/clean_db.py --soft-deleted       # Remove soft-deleted tasks
    python scripts/clean_db.py --orphaned           # Clean orphaned attachments
    python scripts/clean_db.py --vacuum             # Vacuum database
    python scripts/clean_db.py --all                # Remove all data
    python scripts/clean_db.py --reset              # Reset to initial state
    python scripts/clean_db.py --undo-log 500       # Keep only 500 undo entries
    python scripts/clean_db.py --fix-sort-order     # Fix sort_order gaps/inconsistencies
    
    python scripts/clean_db.py --db custom.db --stats  # Use custom database file
        """
    )
    
    parser.add_argument("--db", default="app.db", help="Database file path (default: app.db)")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    parser.add_argument("--all", action="store_true", help="Remove all tasks and data")
    parser.add_argument("--soft-deleted", action="store_true", help="Remove soft-deleted tasks")
    parser.add_argument("--orphaned", action="store_true", help="Clean orphaned attachments")
    parser.add_argument("--vacuum", action="store_true", help="Vacuum database to reclaim space")
    parser.add_argument("--reset", action="store_true", help="Reset database to initial state")
    parser.add_argument("--undo-log", type=int, metavar="N", help="Clean undo log, keeping N entries (default: 1000)")
    parser.add_argument("--fix-sort-order", action="store_true", help="Fix sort_order gaps and inconsistencies")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Set up logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s - %(levelname)s - %(message)s")
    
    # Check if database exists
    db_path = Path(args.db)
    if not db_path.exists() and not args.reset:
        print(f"❌ Database file not found: {db_path}")
        print("Use --reset to create a new database")
        return 1
    
    cleaner = DatabaseCleaner(args.db)
    
    try:
        await cleaner.initialize()
        
        # Show initial stats if requested or if verbose
        if args.stats or args.verbose:
            print("\n📊 Database Statistics:")
            stats = await cleaner.show_stats()
            for key, value in stats.items():
                print(f"  {key}: {value}")
            print()
        
        # Perform cleanup operations
        if args.all:
            if input("⚠️  This will remove ALL data. Are you sure? (yes/no): ").lower() == "yes":
                await cleaner.remove_all_data()
            else:
                print("❌ Operation cancelled")
                
        elif args.reset:
            if input("⚠️  This will reset the database to initial state. Are you sure? (yes/no): ").lower() == "yes":
                await cleaner.reset_database()
            else:
                print("❌ Operation cancelled")
                
        elif args.soft_deleted:
            await cleaner.remove_soft_deleted()
            
        elif args.orphaned:
            await cleaner.clean_orphaned_attachments()
            
        elif args.vacuum:
            await cleaner.vacuum_database()
            
        elif args.undo_log is not None:
            await cleaner.clean_undo_log(args.undo_log)
        
        elif args.fix_sort_order:
            await cleaner.fix_sort_order()
            
        elif not args.stats:
            print("ℹ️  No operation specified. Use --help for options.")
            return 1
        
        # Show final stats if any operation was performed
        if any([args.all, args.reset, args.soft_deleted, args.orphaned, args.vacuum, args.undo_log is not None, args.fix_sort_order]):
            print("\n📊 Final Statistics:")
            final_stats = await cleaner.show_stats()
            for key, value in final_stats.items():
                print(f"  {key}: {value}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
        
    finally:
        await cleaner.cleanup()
    
    print("✅ Database cleanup completed")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 