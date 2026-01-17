# Activity Manager

A comprehensive **sports training and recovery journal** application for athletes working with coaches or recovering from injuries. Automatically sync activities from Strava, plan your training schedule, and track how your body responds to workouts with detailed annotations.

## Why This App?

When training for performance or recovering from injury (like Achilles tendinitis, runner's knee, or other overuse injuries), tracking both your planned training and actual performance alongside how your body responds is crucial. This app helps you:

- **Plan your training** - Create weekly training schedules with specific workouts
- **Match plan to reality** - Link planned activities to actual workouts
- **Document your feelings** - Record pain/discomfort levels and notes for each activity
- **Track daily condition** - Log how you feel each day, even on rest days
- **Classify workouts** - Use extended activity types (Easy Run, Tempo, Intervals, etc.)
- **Identify patterns** - See how different activities affect your recovery
- **Communicate with coaches** - Provide trainers with detailed reports to adjust your plan
- **Monitor progress** - Track your journey over time with comprehensive reports

## Features

### Planning & Training
- **Training Calendar** - Weekly planning view showing planned vs. actual activities
- **Standard Activity Types** - 50+ official Strava sport types organized into 7 categories (Foot, Cycle, Water, Winter, Fitness, Racket, Other)
- **Extended Activity Types** - 55+ custom classifications including HIIT variations (Tabata, EMOM, AMRAP), Crossfit (WOD, MetCon), Yoga styles (Vinyasa, Hatha, Power), Swimming types (Pool, Open Water), and more
- **Planned Activities** - Create workouts with target distance, duration, intensity, and coaching notes
- **Activity Matching** - Link planned workouts to actual Strava activities with validation
- **Multi-day Planning** - Copy planned activities to multiple dates at once
- **Type Grouping** - Extended types organized by base sport for easy selection

### Activity Tracking
- **Strava Integration** - One-click OAuth sync to automatically import all your activities
- **Auto-Type Creation** - Unknown sport types from Strava are automatically added to maintain compatibility
- **Activity Overview** - Activities grouped by day with collapsible rest days
- **Detailed Activity View** - Full stats, maps, and performance metrics
- **Sport Type Badges** - Color-coded badges for different activity types
- **Type Validation** - Foreign key constraints ensure data integrity

### Feeling & Recovery Annotations
- **Pain Scale Tracking** - Rate pain/discomfort (0-10 scale) before, during, and after each workout
- **Visual Pain Icons** - Font Awesome face icons with color gradient (green to red)
- **Daily Journal** - Record your overall daily condition and coach comments
- **Activity Notes** - Detailed notes for each workout session

### Reporting & Analysis
- **Date Range Reports** - Tabular view showing activities, feelings, and patterns
- **Coach Comments** - Track trainer feedback alongside your training log
- **Rest Day Tracking** - Monitor rest days with daily feelings and pain levels

### User Interface
- **Dark Theme** - Clean, responsive Bootstrap 5 interface optimized for readability
- **Collapsible Days** - Compact view with expandable activity details
- **Mobile-First Design** - Card-based layouts on mobile showing priority information at a glance
- **Progressive Disclosure** - Tap to expand details on mobile, keeping initial views clean
- **Responsive Design** - Separate optimized layouts for desktop tables and mobile cards
- **Font Awesome Icons** - Modern icon set for activities and pain scale

## Screenshots

The app provides four main views:

1. **Activities Overview** - Daily view with activity cards, day feelings, and collapsible rest days
2. **Activity Detail** - Full activity stats with feeling annotation form and type classification
3. **Planning Calendar** - Weekly training plan with planned vs. actual activities and matching
4. **Report** - Comprehensive tabular view of activities and feelings over any date range

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
3. Go to "Planning" to create your training schedule
4. Use "Manage Types" to create custom activity classifications
5. Click on any activity to add your feeling annotations
6. Use the "Report" page to review your progress over time

## Database Utilities

The app includes utility scripts for database maintenance:

### Schema Migrations

For general database schema updates:

```bash
python migrate_db.py activities.db
```

### Fixing Sport Types

If sport types from Strava sync incorrectly, clean them up:

```bash
python fix_sport_types.py activities.db
```

This script normalizes sport type values and removes any formatting artifacts.

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
- All Strava metrics (distance, time, heart rate, elevation, pace, etc.)
- **Extended type classification** (optional custom categorization)
- **Feeling annotations** (added by you):
  - Before exercise: pain level (0-10) + notes
  - During exercise: pain level (0-10) + notes
  - After exercise: pain level (0-10) + notes
- **Matching** to planned activities

### Planned Activities

Each planned workout includes:
- Date, name, and description
- Activity type (standard or extended)
- Target metrics (distance, duration, elevation)
- Intensity level
- Coaching notes
- Match status (linked to actual activity or unmatched)

### Extended Activity Types

Custom activity classifications with:
- Base sport type (Run, Ride, WeightTraining, etc.)
- Custom name (Easy Run, Tempo, HYROX, LAG, etc.)
- Description
- Color badge for visual distinction

Available extended types:
- **Running**: Easy Run, Tempo Run, Interval Run, Long Run, Recovery Run
- **Cycling**: Zone 2 Ride, Threshold Ride, Recovery Ride
- **Gym**: HYROX, Weight Training, LAG (Laufausgleichgymnastik), Stretching

### Days

Each day can have:
- Overall pain/discomfort level (0-10)
- Notes about how you're feeling
- Coach comments
- Tracked even on rest days

## Pain Scale

The 0-10 pain scale uses Font Awesome face icons with visual indicators:
- **0**: Grinning face - No discomfort (green)
- **1-2**: Smiling faces - Minimal discomfort (light green)
- **3-4**: Neutral faces - Mild discomfort (yellow)
- **5-6**: Concerned faces - Moderate discomfort (orange)
- **7-8**: Sad faces - Significant pain (red)
- **9-10**: Severe pain faces - Severe pain (dark red)

## Use Cases

### Training Plan Management
Create and track your weekly training schedule. Plan recovery runs, tempo workouts, and long runs with specific targets. Match each planned workout to your actual Strava activities.

### Injury Recovery
Document your return from injury by tracking how each activity affects you. Use extended types to classify workouts by intensity (Easy, Recovery, etc.). Share reports with your physiotherapist to adjust rehabilitation protocols.

### Training Load Management
Help your coach understand how you're responding to training. Track pain levels and fatigue. Identify when to push harder or when to back off based on feeling annotations.

### Pattern Recognition
Over time, identify which activities, intensities, or combinations lead to increased discomfort. Use extended types to see patterns (e.g., "Tempo runs cause more knee pain than Easy runs").

### Coach Communication
Provide detailed reports showing planned vs. actual training, along with how you felt during each workout. Share coach comments and feedback directly in the app.

## Project Structure

```
activity-manager/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── database.py              # SQLite database layer
│   ├── repositories/            # Data access layer
│   │   ├── activity_repository.py
│   │   ├── day_repository.py
│   │   ├── planned_activity_repository.py
│   │   └── extended_type_repository.py
│   ├── services/                # Business logic layer
│   │   ├── strava_service.py
│   │   └── sync_service.py
│   ├── utils/                   # Shared utilities
│   │   └── formatters.py
│   ├── auth/                    # Strava OAuth
│   ├── activities/              # REST API endpoints
│   ├── planning/                # Planning and extended types
│   ├── web/                     # Web UI routes
│   ├── static/
│   │   ├── css/
│   │   │   ├── style.css       # Main dark theme styles
│   │   │   └── planning.css    # Planning-specific styles
│   │   ├── js/
│   │   │   ├── activities.js   # Activities view interactions
│   │   │   └── planning.js     # Planning view interactions
│   │   └── fontawesome/        # Font Awesome icon library
│   └── templates/              # Jinja2 templates
│       ├── activities.html     # Main activities overview
│       ├── activity_detail.html # Individual activity view
│       ├── planning.html       # Training calendar
│       ├── planning_modals.html # Planning UI modals
│       ├── planning_types.html # Extended types management
│       ├── report.html         # Comprehensive report view
│       ├── macros.html         # Reusable template macros
│       └── base.html           # Base template with navigation
├── activities.db               # SQLite database
├── requirements.txt            # Dependencies
├── config.py                   # Configuration settings
├── run.py                      # Development entry point
└── wsgi.py                     # Production entry point
```

## Technical Notes

- **Lightweight Database**: Uses Python's built-in `sqlite3` (no ORM overhead)
- **Minimal Dependencies**: Flask, stravalib, python-dotenv, Font Awesome
- **Preserves Annotations**: Strava sync updates activity data without overwriting:
  - Your feeling notes and pain scale ratings
  - Extended activity type classifications
  - Custom annotations and coach comments
- **Dark Theme**: GitHub-inspired dark mode optimized for low-light use
- **Collapsible UI**: Efficient display of many days with rest day tracking
- **Smart Matching**: Validation prevents duplicate matches and cross-date matching

## API Endpoints

The app includes a REST API for programmatic access:

- `GET /api/activities/` - List activities with filtering (by date, sport type, day_date)
- `GET /api/activities/<id>` - Get single activity details
- `POST /api/activities/sync` - Sync from Strava
- `GET /api/activities/stats` - Get aggregate statistics

Planning API:
- `GET /planning` - View training calendar
- `POST /planning/activity` - Create planned activity
- `PUT /planning/activity/<id>` - Update planned activity
- `DELETE /planning/activity/<id>` - Delete planned activity
- `POST /planning/activity/<id>/match/<activity_id>` - Match planned to actual
- `DELETE /planning/activity/<id>/match` - Unmatch activities

## License

This project is for personal use.

## Resources

- [Strava API Documentation](https://developers.strava.com/docs/reference/)
- [Bootstrap 5 Documentation](https://getbootstrap.com/docs/5.3/)
- [Font Awesome Icons](https://fontawesome.com/)
