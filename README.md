# Activity Manager

A **sports journal** application for athletes recovering from injuries or working with coaches. Automatically sync your activities from Strava and annotate how you felt before, during, and after each workout. Track your daily overall condition to help trainers adjust your training plan and monitor your recovery progress.

## Why This App?

When recovering from an injury (like Achilles tendinitis, runner's knee, or other overuse injuries), tracking how your body responds to training is crucial. This app helps you:

- **Document your feelings** - Record pain/discomfort levels and notes for each activity
- **Track daily condition** - Log how you feel each day, even on rest days
- **Identify patterns** - See how different activities affect your recovery
- **Communicate with coaches** - Provide trainers with detailed reports to adjust your plan
- **Monitor progress** - Track your journey back to full fitness over time

## Features

- **Strava Integration** - One-click OAuth sync to automatically import all your activities
- **Feeling Annotations** - Rate pain/discomfort (0-10 scale) before, during, and after each workout
- **Daily Journal** - Record your overall daily condition, even on rest days
- **Visual Reports** - Date-range reports showing activities alongside your subjective feedback
- **Activity Overview** - Activities grouped by day with color-coded sport types
- **Dark Theme UI** - Clean, responsive Bootstrap 5 interface

## Screenshots

The app provides three main views:

1. **Activities Overview** - Daily view with activity cards and day feelings
2. **Activity Detail** - Full activity stats with feeling annotation form
3. **Report** - Tabular view of activities and feelings over a date range

## Quick Start

### Prerequisites

- Python 3.8+
- Strava API credentials ([create an app here](https://www.strava.com/settings/api))

### Installation

```bash
# Clone and enter directory
cd activity-manager

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Strava credentials

# Run the app
python run.py
```

The app will be available at `http://localhost:5000`

### First Use

1. Click "Connect with Strava" to authenticate
2. Click "Sync" to import your activities
3. Click on any activity to add your feeling annotations
4. Use the "Report" page to review your progress over time

## Configuration

Edit `.env` with your Strava API credentials:

```env
FLASK_ENV=development
SECRET_KEY=your-secret-key-here

STRAVA_CLIENT_ID=your-client-id
STRAVA_CLIENT_SECRET=your-client-secret
```

## Data Model

### Activities

Each synced activity includes:
- All Strava metrics (distance, time, heart rate, elevation, etc.)
- **Feeling annotations** (added by you):
  - Before exercise: pain level (0-10) + notes
  - During exercise: pain level (0-10) + notes
  - After exercise: pain level (0-10) + notes

### Days

Each day can have:
- Overall pain/discomfort level (0-10)
- Notes about how you're feeling
- Tracked even on rest days

## Pain Scale

The 0-10 pain scale uses visual indicators:
- **0-2**: Green faces (minimal discomfort)
- **3-4**: Yellow faces (mild discomfort)
- **5-6**: Orange faces (moderate discomfort)
- **7-8**: Red faces (significant pain)
- **9-10**: Dark red faces (severe pain)

## Use Cases

### Injury Recovery
Track your return from injury by documenting how each activity affects you. Share reports with your physiotherapist to adjust rehabilitation protocols.

### Training Load Management
Help your coach understand how you're responding to training. Identify when to push harder or when to back off.

### Pattern Recognition
Over time, identify which activities, intensities, or combinations lead to increased discomfort, helping optimize your training approach.

## Project Structure

```
activity-manager/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── database.py          # SQLite database layer
│   ├── auth/                 # Strava OAuth
│   ├── activities/           # REST API endpoints
│   ├── web/                  # Web UI routes
│   ├── static/
│   │   ├── css/style.css    # Custom styles
│   │   └── svg/             # Pain scale icons
│   └── templates/           # Jinja2 templates
├── requirements.txt         # Dependencies (Flask, stravalib, python-dotenv)
└── run.py                   # Entry point
```

## Technical Notes

- **Lightweight**: Uses Python's built-in `sqlite3` (no ORM)
- **Minimal dependencies**: Flask, stravalib, python-dotenv
- **Preserves annotations**: Strava sync updates activity data without overwriting your feeling notes

## License

This project is for personal use.

## Resources

- [Strava API Documentation](https://developers.strava.com/docs/reference/)
- [Bootstrap 5 Documentation](https://getbootstrap.com/docs/5.3/)
