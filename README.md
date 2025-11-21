# Activity Manager

A **lean** Python Flask application for managing sport activities with Strava integration. The data model is fully compliant with Strava's API, allowing you to track all activity metrics including performance, location, and social engagement data.

## Features

- **Bootstrap 5 Dark Theme Web UI** - Beautiful, responsive interface for viewing activities
- **Strava Integration** - One-click OAuth connection and sync via stravalib
- Full Strava API data model with 50+ activity attributes
- Complete CRUD operations for activities
- Activity filtering by sport type and date range
- Activities grouped by day with pagination
- Statistics and summaries
- Lightweight: Uses Python's built-in `sqlite3` module (no SQLAlchemy!)
- Only 3 dependencies: Flask, stravalib, python-dotenv
- RESTful API design with blueprints

## Prerequisites

- Python 3.13+ (or 3.8+)
- Strava API credentials (Client ID and Client Secret)

## Installation

1. Clone the repository or navigate to the project directory:
```bash
cd activity-manager
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your Strava API credentials
```

5. Initialize the database:
```bash
python run.py
# The database will be created automatically on first run
```

## Configuration

Edit the `.env` file with your Strava credentials:

```env
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=your-secret-key-here

STRAVA_CLIENT_ID=your-client-id-here
STRAVA_CLIENT_SECRET=your-client-secret-here
STRAVA_ACCESS_TOKEN=your-access-token-here
STRAVA_REFRESH_TOKEN=your-refresh-token-here
```

## Running the Application

Start the Flask development server:

```bash
python run.py
```

The application will be available at `http://localhost:5000`

## API Endpoints

### Root
- `GET /` - API information

### Authentication
- `GET /auth/login` - Initiate Strava OAuth flow
- `GET /auth/callback` - OAuth callback endpoint
- `GET /auth/status` - Check authentication status
- `GET /auth/logout` - Clear session

### Activities

#### List Activities
```bash
GET /activities/
```
Query parameters:
- `sport_type` - Filter by sport type (e.g., 'Run', 'Ride')
- `start_date` - Filter activities after date (ISO format)
- `end_date` - Filter activities before date (ISO format)
- `limit` - Maximum results to return
- `offset` - Number of results to skip

#### Get Single Activity
```bash
GET /activities/<activity_id>
```

#### Create Activity
```bash
POST /activities/
Content-Type: application/json

{
  "name": "Morning Run",
  "sport_type": "Run",
  "start_date_local": "2024-01-15T08:00:00",
  "elapsed_time": 3600,
  "distance": 10000,
  "description": "Great run!"
}
```

Required fields:
- `name` - Activity name
- `sport_type` - Type of sport
- `start_date_local` - Start time (ISO format)
- `elapsed_time` - Duration in seconds

#### Update Activity
```bash
PUT /activities/<activity_id>
Content-Type: application/json

{
  "name": "Updated Activity Name",
  "description": "New description"
}
```

#### Delete Activity
```bash
DELETE /activities/<activity_id>
```

#### Sync from Strava
```bash
POST /activities/sync
```
Query parameters:
- `limit` - Number of activities to fetch (default: 30, max: 200)
- `after` - Fetch activities after timestamp (Unix epoch)
- `before` - Fetch activities before timestamp (Unix epoch)

#### Get Statistics
```bash
GET /activities/stats
```
Query parameters:
- `sport_type` - Filter by sport type
- `start_date` - Start of date range
- `end_date` - End of date range

## Data Model

The Activity model includes all Strava API fields:

### Core Fields
- Identification: id, resource_state, external_id, upload_id
- Temporal: start_date, start_date_local, timezone, elapsed_time, moving_time
- Descriptive: name, description, type, sport_type
- Performance: distance, speed, cadence, power, heart rate
- Location: start/end coordinates, city, state, country
- Social: kudos_count, comment_count, achievement_count

### Activity Types Supported
- Running: Run, TrailRun
- Cycling: Ride, MountainBikeRide, GravelRide, EBikeRide
- Water: Swim, Kayaking, Rowing
- Winter: AlpineSki, BackcountrySki, NordicSki, Snowboard
- Other: Hike, Walk, Workout, and more

## Project Structure

```
activity-manager/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── database.py          # Database layer (sqlite3)
│   ├── auth/
│   │   ├── __init__.py
│   │   └── routes.py        # OAuth routes
│   └── activities/
│       ├── __init__.py
│       └── routes.py        # CRUD endpoints
├── activities.db            # SQLite database (auto-created)
├── config.py                # Configuration
├── requirements.txt         # Dependencies (only 3!)
├── run.py                   # Application entry point
├── .env                     # Environment variables (not in repo)
├── .env.example             # Environment template
└── .gitignore               # Git ignore rules
```

## Development

### Database Schema

The database is automatically initialized on first run. The schema is defined in [app/database.py](app/database.py).

To reset the database, simply delete `activities.db` and restart the application.

### Adding New Features

The application uses Flask blueprints for modular organization. To add new functionality:

1. Create a new blueprint in `app/`
2. Register it in [app/__init__.py](app/__init__.py)
3. Add routes to the blueprint

### Architecture

- **No ORM**: Uses Python's built-in `sqlite3` module for maximum simplicity
- **Minimal dependencies**: Only Flask, stravalib, and python-dotenv
- **Blueprint-based**: Modular organization with `auth` and `activities` blueprints
- **Database layer**: Simple helper functions in [app/database.py](app/database.py)

## License

This project is for personal use.

## Strava API Reference

Full Strava API documentation: https://developers.strava.com/docs/reference/
