# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Activity Manager is a Flask-based sports training and recovery journal application. It integrates with Strava to sync activities, enables training plan management, and tracks athlete recovery through pain/feeling annotations.

**Tech Stack**: Python 3.8+, Flask 3.0, SQLite (raw `sqlite3`, no ORM), Bootstrap 5, Font Awesome

## Development Commands

### Running the Application

```bash
# Activate virtual environment
source venv/bin/activate

# Run development server (default: http://0.0.0.0:5001)
python run.py

# Run with custom host/port
FLASK_HOST=localhost FLASK_PORT=5000 python run.py

# Production server
gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
```

### Testing

```bash
# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run specific test file
python -m pytest tests/test_file.py
```

### Database Operations

```bash
# Database schema migrations (custom script in app/database.py)
# Schema is defined in init_db() function - no migration framework used

# Import archived data
python scripts/import_archive.py
```

## Architecture

### Application Structure

**Flask Factory Pattern**: App created via `create_app()` in `app/__init__.py`. Configuration managed through `config.py` with environment-specific classes (`DevelopmentConfig`, `ProductionConfig`).

**Blueprint Organization**:
- `auth_bp` (`/auth`) - Strava OAuth flow
- `activities_bp` (`/api/activities`) - Activity REST API
- `api_bp` (`/api`) - Extended activity types API
- `web_bp` (root `/`) - Web UI routes
- `admin_bp` (`/admin`) - Admin features (type management)

### Data Layer Architecture

**Repository Pattern** (no ORM):
- `BaseRepository` (`app/repositories/base.py`) - Abstract base with common database operations
- Concrete repositories: `ActivityRepository`, `DayRepository`, `GearRepository`, `TypeRepository`
- Raw SQL queries with `sqlite3.Row` for dict-like row access
- Utilities: `db_row_to_dict()`, `dict_to_db_values()` in `app/utils/database_helpers.py`

**Database Connection**:
- Per-request connection via Flask `g` object (`get_db()` in `app/database.py`)
- Connection closed via `teardown_appcontext` hook
- Schema initialized in `init_db()` - no separate migration files

### Service Layer

**StravaService** (`app/services/strava_service.py`):
- OAuth token management and refresh
- Activity sync from Strava API
- Preserves local annotations (feeling notes, pain scales, extended types) during sync
- Uses `stravalib` library for API calls

### Key Data Models

**Activities Table**:
- Stores full Strava activity data (50+ fields)
- Foreign key to `sport_type` (standard Strava types)
- Optional `extended_type_id` for custom classifications (e.g., "Easy Run", "Tempo")
- JSON fields for map data, latlng coordinates

**Days Table**:
- Daily journal entries with overall pain/condition ratings (0-10 scale)
- Coach comments and notes
- Tracks rest days

**Extended Activity Types**:
- Custom workout classifications organized by base sport type
- 55+ predefined types (HIIT variations, Crossfit, Yoga styles, etc.)
- Color-coded badges for UI

**Planned Activities**:
- Training calendar with target distance/duration/intensity
- Matching to actual Strava activities via `matched_activity_id`
- Validation prevents duplicate/cross-date matches

### Frontend Architecture

**Template Engine**: Jinja2 templates in `app/templates/`
- `base.html` - Navigation and layout
- `macros.html` - Reusable template components
- Template filter: `weekday` (converts date strings to weekday abbreviations)

**JavaScript Organization**:
- `app.js` - Core application logic
- `pain-scale.js` - Pain rating UI components
- `activities.js` - Activities view interactions
- `admin-types.js` - Type management UI
- `activity-type-selector.js` - Type selection widgets
- `day-detail.js` - Daily journal UI

**Styling**: `style.css` (dark theme), Bootstrap 5, Font Awesome icons

## Important Implementation Details

### Database Schema Management

- **No migration framework** - Schema defined directly in `app/database.py:init_db()`
- To modify schema: Update `init_db()`, create backup via `backup_database()`, apply changes manually
- Sport types use **foreign key constraints** - unknown types from Strava are auto-created to maintain integrity

### Strava Integration

- OAuth flow: `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET` in `.env`
- Redirect URI built from `HOST` config (use `https://` for production)
- Token refresh handled automatically by `StravaService`
- Activity sync preserves local annotations (never overwrites user-added data)

### Repository Pattern Usage

```python
# Repositories can use Flask g.db or accept explicit connection
repo = ActivityRepository()  # Uses Flask g.db
repo = ActivityRepository(db=custom_db)  # Explicit connection

# Auto-commit enabled by default
repo.set_auto_commit(False)  # Disable for batch operations
# ... perform multiple operations ...
repo.commit()  # Manual commit
```

### Error Handling

Custom exceptions in `app/utils/errors.py`:
- `DatabaseError` - Database operation failures
- Additional error types as needed

## Testing Strategy

**Pytest Configuration** (`tests/conftest.py`):
- Session-scoped `app` fixture with temporary test database
- Function-scoped `db` fixture - clears tables between tests
- Function-scoped `client` fixture for request testing
- `mock_strava_client` fixture for mocking Strava API

**Test Database**:
- Temporary file created per test session
- Cleaned up automatically after tests
- Extended type seed data (id > 100) preserved between tests

## Configuration

Environment variables (`.env`):
- `FLASK_ENV` - `development` or `production`
- `SECRET_KEY` - Flask secret (required in production)
- `HOST` - Full URL for OAuth callbacks (e.g., `https://activity.example.com`)
- `DATABASE_PATH` - Custom database location (default: `activities.db`)
- `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET` - Strava API credentials
- `FLASK_HOST`, `FLASK_PORT` - Override development server bind address

Production deployment via `wsgi.py` (WSGI entry point for gunicorn).
