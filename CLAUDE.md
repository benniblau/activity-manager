# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Activity Manager is a Flask-based sports training and recovery journal application. It integrates with Strava to sync activities, enables training plan management, and tracks athlete recovery through pain/feeling annotations.

**Tech Stack**: Python 3.8+, Flask 3.0, SQLite (raw `sqlite3`, no ORM), Bootstrap 5, Font Awesome, Flask-Login

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

# Run a single test function
python -m pytest tests/test_file.py::test_function_name
```

### Database Operations

```bash
# Schema is defined in init_db() — no migration framework used
# To modify schema: update init_db(), create backup via backup_database(), apply manually

# Import archived Strava bulk export data
python scripts/import_archive.py

# One-time migration: single-user to multi-user
python scripts/migrate_to_multiuser.py
```

## Architecture

### Application Structure

**Flask Factory Pattern**: App created via `create_app()` in `app/__init__.py`. Initializes Flask-Login (`login_view = 'auth.user_login'`), registers blueprints, wires up `init_db()`, and injects `coach_athletes`/`viewing_athlete` into every template via context processor (for the coach nav dropdown).

**Blueprint Organization**:
- `auth_bp` (`/auth`) - Strava OAuth flow, user login/logout/register
- `activities_bp` (`/api/activities`) - Activity REST API (CRUD, sync, stats)
- `api_bp` (no prefix, routes use `/api/...`) - Plan CRUD (`/api/plan/`), Types API (`/api/types/`)
- `web_bp` (root `/`) - HTML views; also hosts AJAX sync endpoints (`/api/sync/...`)
- `admin_bp` (`/admin`) - Profile, password, extended types CRUD, coach/invitation management

### Data Layer Architecture

**Repository Pattern** (no ORM):
- `BaseRepository` (`app/repositories/base.py`) - Abstract base with common database operations
- Concrete repositories: `ActivityRepository`, `DayRepository`, `GearRepository`, `TypeRepository`, `PlannedActivityRepository`
- Raw SQL queries with `sqlite3.Row` for dict-like row access
- Utilities: `db_row_to_dict()`, `dict_to_db_values()` in `app/utils/database_helpers.py`

**Database Connection**:
- Per-request connection via Flask `g` object (`get_db()` in `app/database.py`)
- Connection closed via `teardown_appcontext` hook
- Schema initialized in `init_db()` — all `_migrate_*()` functions use `PRAGMA table_info` / `sqlite_master` checks to be **fully idempotent** on every startup

### Service Layer

**StravaService** (`app/services/strava_service.py`):
- OAuth token management and refresh
- Activity sync from Strava API; disables repo auto-commit for bulk sync, commits once at end
- `transform_strava_data()` uses `_extract_value()` to handle stravalib's pydantic `RootModel` objects, enums, and `root='Value'` string patterns
- Preserves local annotations (feeling notes, pain scales, extended types) during sync

**AccessControlService** (`app/services/access_control_service.py`):
- `get_viewing_user_id()` is the central access control point — athletes always see their own ID; coaches get whoever is set in `session['viewing_user_id']` (validated against `coach_athlete_relationships`)
- Coach invitation/accept/reject/remove operations

**InvitationService** (`app/services/invitation_service.py`):
- Creates `secrets.token_urlsafe(32)` tokens stored in `invitations` table
- Tokens expire after configurable days (`INVITATION_EXPIRY_DAYS`, default 30)

### Multi-User Architecture

The app evolved from single-user to multi-user. Key design points:

- **Two roles**: `athlete` (connects Strava, writes feelings) and `coach` (views athletes, writes coach comments, creates plans)
- **Invitation-only registration**: First user registers freely ("bootstrap mode" detected via `is_users_table_empty()`); subsequent users need a token
- **Coach-athlete relationships** (`coach_athlete_relationships` table): Statuses `pending`/`active`/`inactive`. Supports dual-key design — `coach_id` if the coach account exists, or `coach_email` if not yet registered. On coach registration, `UPDATE` replaces `coach_email` with the new `coach_id`
- **Auth decorators** (`app/auth/decorators.py`): `@login_required`, `@athlete_required`, `@coach_required`, `@anonymous_required`
- **`activities`, `days`, `planned_activities` tables all have `user_id`** (added via migration; queries in `web/routes.py` filter by `user_id`)

### Key Data Models

**Activities Table**:
- Stores full Strava activity data (50+ fields)
- Foreign key to `sport_type` (standard Strava types — unknown types are auto-created to maintain FK integrity)
- Optional `extended_type_id` for custom classifications (e.g., "Easy Run", "Tempo")
- JSON fields stored as text: `start_latlng`, `end_latlng`, `map`, `segment_efforts`, `splits_metric`, `laps`, `best_efforts`, `gear`

**Days Table**:
- Daily journal entries with overall pain/condition ratings (0-10 scale)
- Coach comments and notes; tracks rest days

**Extended Activity Types**:
- Custom workout classifications organized by base sport type
- 55+ predefined seed types (id > 100); color-coded badges for UI
- `EXTENDED_TYPES_BY_SPORT` is inlined as JSON in `plan.html` for frontend dropdowns

**Planned Activities**:
- Training calendar with target distance/duration/intensity
- Matching to actual Strava activities via `matched_activity_id`
- Validation prevents duplicate/cross-date matches

### Frontend Architecture

**Template Engine**: Jinja2 templates in `app/templates/`
- `base.html` - Navigation, Bootstrap 5 layout, shared `#alertModal` and `#confirmModal`
- `macros.html` - Reusable template components
- `components/` - Partial template components
- Template filter: `weekday` (converts date strings to weekday abbreviations)

**JavaScript Organization**:
- `app.js` - Global `showAlert()` and `showConfirm()` helpers (drive Bootstrap 5 modals; `confirmModal` uses `cloneNode` to avoid duplicate event listeners)
- `activities.js` - Two-step sequential AJAX sync flow with progress overlay; day row expand/collapse
- `plan.js` - IIFE module pattern; SortableJS drag-to-reorder with immediate `fetch('/api/plan/reorder')`; lazy-loads activities into match dropdowns on first focus
- `pain-scale.js` - Pain rating UI (click `.pain-scale-option`, updates hidden input by `data-input` ID)
- `activity-type-selector.js` - Extended type picker widget
- `admin-types.js` - Type management CRUD UI
- `day-detail.js` - Day detail page interactions

**Styling**: `style.css` (dark theme), Bootstrap 5, Font Awesome icons

## Important Implementation Details

### Database Schema Management

- **No migration framework** — Schema defined directly in `app/database.py:init_db()`
- All `_migrate_*()` helper functions are idempotent; safe to run on every startup
- Sport types use **foreign key constraints** — unknown types from Strava are auto-created to maintain integrity
- `strava_tokens` table has `CHECK (id = 1)` singleton constraint (legacy single-user design); multi-user tokens use `user_id` as the per-user key

### Strava Integration

- OAuth flow: `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET` in `.env`
- Redirect URI built from `HOST` config (use `https://` for production)
- Token refresh handled automatically in `auth/routes.py:ensure_valid_token()` with 5-minute expiry buffer
- `_clean_strava_value()` in `web/routes.py` is a recursive cleaner for stravalib pydantic artifacts — handles `root='Value'` patterns, slash-separated enum values (converts to PascalCase), datetime objects

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

Custom exception hierarchy in `app/utils/errors.py`:
- `AppError` — base with `message`, `code`, `status_code`, `to_dict()`
- `ActivityNotFoundError` / `TypeNotFoundError` — 404
- `ValidationError` — 400 (adds optional `field`)
- `StravaAPIError` — 502; `RateLimitError(StravaAPIError)` — 429 (adds `retry_after`)
- `DatabaseError` — 500; `DuplicateError` — 409

## Testing Strategy

**Pytest Configuration** (`tests/conftest.py`):
- Session-scoped `app` fixture with temporary test database (CSRF disabled, `TESTING=True`)
- Function-scoped `db` fixture — clears tables between tests but preserves extended type seed data (id > 100)
- Function-scoped `client` fixture for request testing
- `mock_strava_client` fixture for mocking Strava API

## Configuration

Environment variables (`.env`):
- `FLASK_ENV` - `development` or `production`
- `SECRET_KEY` - Flask secret (required in production)
- `HOST` - Full URL for OAuth callbacks (e.g., `https://activity.example.com`)
- `DATABASE_PATH` - Custom database location (default: `activities.db`)
- `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET` - Strava API credentials
- `FLASK_HOST`, `FLASK_PORT` - Override development server bind address
- `INVITATION_EXPIRY_DAYS` - Invitation token expiry (default: 30)
- `SESSION_LIFETIME` / `REMEMBER_ME_DURATION` - Session duration in hours/days (default: 24h / 30d)
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` - Email for invitations

Production deployment via `wsgi.py` (WSGI entry point for gunicorn). Systemd unit file at `activity-manager.service`.
