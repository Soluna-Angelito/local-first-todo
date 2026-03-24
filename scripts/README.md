# Database Management Scripts

This directory contains utility scripts for managing the Local-First To-Do database.

## clean_db.py

A comprehensive database cleanup and maintenance script.

### Features

- **Show Statistics**: Display detailed database information
- **Remove All Data**: Clean slate - removes all tasks and data
- **Remove Soft-Deleted Tasks**: Permanently delete tasks marked as deleted
- **Clean Orphaned Attachments**: Remove unused attachment files and database entries
- **Vacuum Database**: Reclaim disk space and optimize database
- **Reset Database**: Return to initial empty state with schema intact
- **Clean Undo Log**: Remove old undo/redo entries

### Usage

```bash
# Show database statistics
python scripts/clean_db.py --stats

# Remove soft-deleted tasks
python scripts/clean_db.py --soft-deleted

# Clean orphaned attachments
python scripts/clean_db.py --orphaned

# Vacuum database to reclaim space
python scripts/clean_db.py --vacuum

# Clean undo log (keep only 500 entries)
python scripts/clean_db.py --undo-log 500

# Remove ALL data (requires confirmation)
python scripts/clean_db.py --all

# Reset database to initial state (requires confirmation)
python scripts/clean_db.py --reset

# Use custom database file
python scripts/clean_db.py --db custom.db --stats

# Verbose output
python scripts/clean_db.py --stats --verbose
```

### Examples

**Development Cleanup:**
```bash
# Clean up development database
python scripts/clean_db.py --soft-deleted --orphaned --vacuum
```

**Fresh Start:**
```bash
# Reset everything for testing
python scripts/clean_db.py --reset
```

**Maintenance:**
```bash
# Regular maintenance
python scripts/clean_db.py --undo-log 1000 --vacuum
```

### Safety Features

- Confirmation prompts for destructive operations (`--all`, `--reset`)
- Shows before/after statistics
- Graceful error handling
- Verbose mode for debugging

### Database Statistics

The script shows comprehensive statistics including:

- Task counts by status (pending, completed, etc.)
- Total and soft-deleted tasks
- Attachment and blob counts
- Undo log entries
- Database file size
- Attachments directory size

### Requirements

- Python 3.10+
- All project dependencies installed
- Database file accessible (or `--reset` to create new one) 