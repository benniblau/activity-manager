# Activity Manager

A **multi-user sports training and recovery journal** for athletes working with coaches or recovering from injuries. Automatically sync activities from Strava, plan your training schedule, and track how your body responds to workouts with detailed annotations.

<img width="1194" height="1086" alt="FLOG_activities" src="https://github.com/user-attachments/assets/3da0137f-dda6-4632-a881-91211029462b" />

**Tech Stack**: Python 3.8+, Flask 3.0, SQLite (raw `sqlite3`, no ORM), Bootstrap 5, Bootstrap Icons

---

## Features

### Multi-User & Coach-Athlete Relationships
- **Invitation-Only Registration** — New users join via a secure, expiring token link; no open sign-up
- **Bootstrap Mode** — First user registers freely; all subsequent registrations require an invitation
- **Role-Based Access** — Separate athlete and coach accounts with distinct permissions
- **Instant Coach Activation** — When a coach registers via an athlete's invitation, they immediately gain access (no manual accept step)
- **Data Sharing** — Coaches can view their athletes' activities, reports, and daily journals
- **View Switching** — Coaches can switch between their own view and each athlete's view
- **Email Notifications** — Invitation emails sent via SMTP; registration link included in flash message as fallback

### Invitation System
- Any logged-in user can send invitations from their Profile page
- Invitations carry the recipient's email and intended role (athlete or coach)
- Tokens expire after a configurable number of days (default: 30)
- Senders can cancel pending invitations; status badges show Pending / Used / Expired / Cancelled

### Planning & Training
- **Weekly Training Calendar** — Plan workouts day-by-day in a `/plan` week view; navigate with Prev/Next week
- **Planned Activity Fields** — Sport type, optional sub-type, target distance (km), target duration (h:mm), free-text notes
- **Drag-to-Reorder** — Reorder planned activities within a day; order is persisted automatically
- **Duplicate & Delete** — Copy an existing planned item or remove it with a single click
- **Match to Actual** — Link each planned activity to a recorded Strava activity on the same day; matched items show a green badge
- **Coach Planning** — Coaches can create and edit plans on behalf of their athletes
- **Standard Activity Types** — 50+ official Strava sport types in 7 categories
- **Extended Activity Types** — 70+ custom classifications:
  - **HIIT**: Tabata, EMOM, AMRAP, Circuit Training
  - **CrossFit**: WOD, MetCon, Olympic Lifting, Hero WODs
  - **Yoga**: Vinyasa, Hatha, Power, Restorative, Yin, Hot Yoga
  - **Swimming**: Pool, Open Water, Technique, Intervals
  - **Running**: Easy, Tempo, Interval, Long Run, Recovery
  - **Cycling**: Zone 2, Threshold, Recovery
  - **Climbing**: Bouldering, Sport, Top Rope, Trad

### Activity Tracking
- **Strava Integration** — OAuth sync to import all activities (athletes only)
- **Activity Overview** — Activities grouped by day with collapsible rest days
- **Detailed Activity View** — Full stats, maps, and performance metrics
- **Sport Type Badges** — Color-coded badges for different activity types

### Feeling & Recovery Annotations
- **Pain Scale Tracking** — Rate pain/discomfort (0–10) before, during, and after each workout (athletes only)
- **Visual Pain Icons** — Face icons with colour gradient (green → red)
- **Daily Journal** — Record your overall daily condition
- **Coach Comments** — Coaches have a dedicated comment field on activities and days; athletes see it read-only
- **Activity Notes** — Detailed notes for each workout session

### Reporting & Analysis
- **Date Range Reports** — Tabular view of activities, feelings, and patterns
- **Coach Dashboard** — View all athlete activities and progress
- **Rest Day Tracking** — Monitor rest days with daily feelings and pain levels

### User Interface
- **Dark Theme** — Clean, responsive Bootstrap 5 interface
- **Mobile-First Design** — Card-based layouts prioritising key information
- **Responsive Design** — Separate optimised layouts for desktop and mobile

---

## Quick Start

### Prerequisites

- Python 3.8+
- Strava API credentials ([create an app](https://www.strava.com/settings/api)) — needed only for athletes
- SMTP server for invitation emails (optional)

### Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd activity-manager

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings (see Configuration below)

# Initialise database
python -c "from app import create_app; app = create_app(); app.app_context().push(); from app.database import init_db; init_db()"

# Run the app
python run.py
```

The app will be available at `http://localhost:5001`

### Configuration

Edit `.env`:

```env
# Main Configuration
HOST=http://localhost:5001  # Full URL used for OAuth callbacks and invitation links

# Flask Configuration
FLASK_APP=run.py
FLASK_ENV=development  # or 'production'
SECRET_KEY=your-random-secret-key  # python -c "import secrets; print(secrets.token_hex(32))"
FLASK_HOST=0.0.0.0
FLASK_PORT=5001

# Session
SESSION_LIFETIME=86400        # seconds (1 day)
REMEMBER_ME_DURATION=2592000  # seconds (30 days)
INVITATION_EXPIRY_DAYS=30

# Database
DATABASE_URL=sqlite:///instance/activities.db

# Strava API (get from https://www.strava.com/settings/api)
STRAVA_CLIENT_ID=your-client-id
STRAVA_CLIENT_SECRET=your-client-secret

# Email (optional — for invitation emails)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@example.com
SMTP_PASSWORD=your-smtp-password
FROM_EMAIL=your-email@example.com
```

#### Strava OAuth Setup

1. Go to [https://www.strava.com/settings/api](https://www.strava.com/settings/api)
2. Create an application
3. Set **Authorization Callback Domain** to match your `HOST`:
   - Development: `localhost` or `127.0.0.1`
   - Production: `your-domain.com`
4. Copy Client ID and Client Secret to `.env`

#### Email Setup (Optional)

If SMTP is not configured, invitation emails won't be sent — but the registration link is shown in a flash message so you can copy and share it manually.

**Gmail**: server `smtp.gmail.com`, port `587`, use an [App Password](https://support.google.com/accounts/answer/185833)

**ProtonMail**: server `smtp.protonmail.ch`, port `587`, use ProtonMail Bridge password; `FROM_EMAIL` must match `SMTP_USERNAME`

---

### First Use

1. **Register the first account** — Navigate to `/auth/user/register` (open registration for the first user only)
2. **Choose your role** — Select *athlete* or *coach*
3. **Connect to Strava** (athletes) — Click "Connect with Strava" on the Activities page or Profile
4. **Sync activities** (athletes) — Click "Sync from Strava"
5. **Invite others** — Go to Profile → Invitations → send an invitation by email and role
6. **Invitees register** — They follow the link in the invitation email (or the link you share manually) to create their account with the pre-assigned role
7. **Add feeling annotations** — Click any activity to add pain levels and notes
8. **Create extended types** — Admin → Extended Activity Types

---

## User Roles

### Athlete
- Connect their own Strava account and sync activities
- Add feeling/pain annotations and activity notes
- Send invitations (e.g. invite a coach)
- Remove coach access at any time

### Coach
- View all activities, daily journals, and reports for their athletes
- Add coach comments to activities and daily entries (athletes see these read-only)
- Create and edit planned activities on behalf of athletes via the Plan view
- Switch between viewing their own data and each athlete's data
- Send invitations to bring in other users
- **Cannot** connect to Strava (Strava sync is exclusive to athletes)

---

## Deployment

### Development

```bash
python run.py
```

Runs on `http://0.0.0.0:5001` with debug mode enabled.

### Production (Linux/Ubuntu)

#### 1. Install Dependencies

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv nginx -y

cd /var/www
sudo git clone <your-repo-url> activity-manager
cd activity-manager

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 2. Configure Environment

```bash
sudo nano .env
# Set HOST=https://activity.yourdomain.com, FLASK_ENV=production, SECRET_KEY=<strong-key>, etc.
```

#### 3. Initialise Database

```bash
python -c "from app import create_app; app = create_app(); app.app_context().push(); from app.database import init_db; init_db()"
```

#### 4. Set Up Gunicorn

```bash
sudo nano /etc/systemd/system/activity-manager.service
```

```ini
[Unit]
Description=Activity Manager Gunicorn Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/activity-manager
Environment="PATH=/var/www/activity-manager/venv/bin"
ExecStart=/var/www/activity-manager/venv/bin/gunicorn -w 4 -b 127.0.0.1:8000 wsgi:app

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl start activity-manager
sudo systemctl enable activity-manager
```

#### 5. Configure Nginx

```nginx
server {
    listen 80;
    server_name activity.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /var/www/activity-manager/app/static;
    }
}
```

#### 6. SSL with Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d activity.yourdomain.com
```

---

## Database Utilities

### Schema Migrations

**No manual migration steps are required.** The app uses an incremental migration system built into `app/database.py`. Every time the app starts, `init_db()` runs all migrations in order using `CREATE TABLE IF NOT EXISTS` and `ALTER TABLE … ADD COLUMN` guards — so they are safe to run repeatedly and will only apply changes that are missing from the current database.

This means:
- **Fresh install** — the full schema is created on first startup
- **Code update / deployment** — restart the app; new migrations run automatically
- **Production** — just `sudo systemctl restart activity-manager` after deploying; no separate migration script needed

### Multi-User Migration (legacy single-user databases)

```bash
python scripts/migrate_to_multiuser.py activities.db
```

Creates users/coach tables, prompts for an admin user, and reassigns existing activities.

### Reset to Single Admin User

Useful when switching a test database to production. Deletes all users except the first (lowest ID), along with their coach relationships, Strava tokens, and invitations:

```bash
python scripts/reset_to_single_user.py activities.db
```

Always creates a timestamped backup before making any changes.

---

## Data Model

### Core Tables

| Table | Purpose |
|---|---|
| `users` | Accounts with bcrypt-hashed passwords and roles |
| `coach_athlete_relationships` | Coach access control (active / inactive) |
| `invitations` | Token-based registration invitations with expiry |
| `activities` | Strava activities with feeling annotations (per user) |
| `days` | Daily overall feelings and coach comments (per user) |
| `planned_activities` | Training plan entries with target distance/duration and match to actual activity |
| `strava_tokens` | OAuth tokens (per user, athletes only) |
| `extended_activity_types` | Custom activity classifications |
| `standard_activity_types` | Official Strava sport types |
| `gear` | Equipment tracking (bikes, shoes, etc.) |
| `activity_media` | Photos linked to activities |

---

## API Endpoints

### Authentication
- `GET /auth/user/login` — Login page
- `POST /auth/user/login` — Process login
- `GET /auth/user/register` — Registration page (token required unless first user)
- `POST /auth/user/register` — Create account
- `GET /auth/user/logout` — Logout

### Strava OAuth (athletes only)
- `GET /auth/strava/connect` — Initiate Strava OAuth
- `GET /auth/strava/callback` — OAuth callback
- `GET /auth/strava/disconnect` — Disconnect Strava

### Activities
- `GET /api/activities/` — List activities
- `GET /api/activities/<id>` — Get single activity
- `POST /api/activities/sync` — Sync from Strava (athletes only)
- `GET /api/activities/stats` — Aggregate statistics

### Admin / Profile
- `GET /admin/profile` — Profile management
- `POST /admin/profile/update` — Update name / email
- `POST /admin/profile/password` — Change password
- `POST /admin/invitations/send` — Send a registration invitation
- `POST /admin/invitations/<id>/cancel` — Cancel a pending invitation
- `POST /admin/coaches/<id>/remove` — Remove coach access (athletes)
- `POST /admin/switch-view/<id>` — Switch viewing context (coaches)

### Training Plan
- `GET /plan` — Weekly planning view (`?week=YYYY-MM-DD` selects the week; defaults to current Mon–Sun)
- `POST /api/plan/` — Create a planned activity
- `PUT /api/plan/<id>` — Update a planned activity (fields or matched actual)
- `DELETE /api/plan/<id>` — Delete a planned activity
- `POST /api/plan/<id>/duplicate` — Duplicate a planned activity to the end of the same day
- `POST /api/plan/reorder` — Batch-update sort order within a day (`{day_date, ordered_ids:[…]}`)

### Annotations (athletes only)
- `POST /activity/<id>/annotations` — Save feeling annotations
- `POST /day/<date>/annotations` — Save day annotations

### Coach Comments (coaches only)
- `POST /activity/<id>/coach-comment` — Save coach comment on an activity
- `POST /day/<date>/coach-comment` — Save coach comment on a day entry

---

## Security Notes

- Passwords hashed with bcrypt
- Session-based authentication via Flask-Login
- Invitation tokens generated with `secrets.token_urlsafe(32)`, expire after configurable days
- CSRF protection on all forms
- OAuth tokens stored per-user in database
- Role-based access control: coaches cannot write athlete feeling data; athletes cannot write coach comments
- `.env` and database files excluded from version control

---

## Pain Scale

The 0–10 pain scale uses face icons with a colour gradient:

| Range | Description | Colour |
|---|---|---|
| 0 | No discomfort | Green |
| 1–2 | Minimal discomfort | Light green |
| 3–4 | Mild discomfort | Yellow |
| 5–6 | Moderate discomfort | Orange |
| 7–8 | Significant pain | Red |
| 9–10 | Severe pain | Dark red |

---

## Tech Stack

- **Backend**: Flask 3.0, Python 3.8+
- **Database**: SQLite (raw `sqlite3`, no ORM)
- **Authentication**: Flask-Login, bcrypt
- **API Integration**: stravalib (Strava API)
- **Frontend**: Bootstrap 5, Bootstrap Icons, SortableJS (drag-to-reorder)
- **Email**: SMTP (configurable)
- **Production Server**: Gunicorn

---

## Resources

- [Strava API Documentation](https://developers.strava.com/docs/reference/)
- [Bootstrap 5 Documentation](https://getbootstrap.com/docs/5.3/)
- [Flask Documentation](https://flask.palletsprojects.com/)
