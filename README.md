# Activity Manager

A comprehensive **multi-user sports training and recovery journal** application for athletes working with coaches or recovering from injuries. Automatically sync activities from Strava, plan your training schedule, and track how your body responds to workouts with detailed annotations.

## Features

### Multi-User & Coach-Athlete Relationships
- **User Authentication** - Secure login with bcrypt password hashing
- **Role-Based Access** - Separate athlete and coach accounts
- **Coach Invitations** - Athletes can invite coaches via email
- **Data Sharing** - Coaches can view their athletes' activities and reports
- **View Switching** - Coaches can switch between viewing their own data and athlete data
- **Email Notifications** - Automatic invitation emails via SMTP

### Planning & Training
- **Weekly Training Calendar** - Plan workouts with target metrics
- **Standard Activity Types** - 50+ official Strava sport types organized into 7 categories
- **Extended Activity Types** - 70+ custom classifications including:
  - **HIIT**: Tabata, EMOM, AMRAP, Circuit Training
  - **CrossFit**: WOD, MetCon, Olympic Lifting, Hero WODs
  - **Yoga**: Vinyasa, Hatha, Power, Restorative, Yin, Hot Yoga
  - **Swimming**: Pool, Open Water, Technique, Intervals
  - **Running**: Easy, Tempo, Interval, Long Run, Recovery
  - **Cycling**: Zone 2, Threshold, Recovery
  - **Climbing**: Bouldering, Sport, Top Rope, Trad
  - **And many more...**

### Activity Tracking
- **Strava Integration** - OAuth sync to import all your activities
- **Per-User Strava Connections** - Each user maintains their own Strava connection
- **Activity Overview** - Activities grouped by day with collapsible rest days
- **Detailed Activity View** - Full stats, maps, and performance metrics
- **Sport Type Badges** - Color-coded badges for different activity types

### Feeling & Recovery Annotations
- **Pain Scale Tracking** - Rate pain/discomfort (0-10 scale) before, during, and after each workout
- **Visual Pain Icons** - Font Awesome face icons with color gradient (green to red)
- **Daily Journal** - Record your overall daily condition
- **Coach Comments** - Track trainer feedback alongside your training log
- **Activity Notes** - Detailed notes for each workout session

### Reporting & Analysis
- **Date Range Reports** - Tabular view showing activities, feelings, and patterns
- **Coach Dashboard** - View all athlete activities and progress
- **Rest Day Tracking** - Monitor rest days with daily feelings and pain levels

### User Interface
- **Dark Theme** - Clean, responsive Bootstrap 5 interface optimized for readability
- **Mobile-First Design** - Card-based layouts on mobile showing priority information at a glance
- **Responsive Design** - Separate optimized layouts for desktop and mobile

## Quick Start

### Prerequisites

- Python 3.8+
- Strava API credentials ([create an app here](https://www.strava.com/settings/api))
- SMTP server for email notifications (optional, e.g., Gmail, ProtonMail)

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
# Edit .env with your configuration (see Configuration section below)

# Initialize database
python -c "from app import create_app; app = create_app(); app.app_context().push(); from app.database import init_db; init_db()"

# Run migration to multi-user (for new installations, creates admin user)
python scripts/migrate_to_multiuser.py

# Run the app
python run.py
```

The app will be available at `http://localhost:5000`

### Configuration

Edit `.env` with your settings:

```env
# Main Configuration
HOST=http://localhost:5000  # Full URL for OAuth callbacks

# Flask Configuration
FLASK_APP=run.py
FLASK_ENV=development  # or 'production'
SECRET_KEY=your-random-secret-key-here  # Generate with: python -c "import secrets; print(secrets.token_hex(32))"

# Database (optional, defaults to activities.db in project root)
# DATABASE_PATH=activities.db

# Strava API Credentials (get from https://www.strava.com/settings/api)
STRAVA_CLIENT_ID=your-client-id
STRAVA_CLIENT_SECRET=your-client-secret

# Email Configuration (optional, for coach invitation notifications)
# NOTE: Many SMTP providers require FROM_EMAIL to match SMTP_USERNAME
SMTP_SERVER=smtp.gmail.com  # or smtp.protonmail.ch, etc.
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
4. Copy the Client ID and Client Secret to your `.env`

#### Email Setup (Optional)

For coach invitation emails, configure SMTP settings. Popular options:

**Gmail:**
- Server: `smtp.gmail.com`
- Port: `587`
- Username: Your Gmail address
- Password: [App-specific password](https://support.google.com/accounts/answer/185833)

**ProtonMail:**
- Server: `smtp.protonmail.ch`
- Port: `587`
- Username: Your ProtonMail address
- Password: ProtonMail Bridge password

If SMTP is not configured, the app will still work but invitation emails won't be sent (athletes will need to notify coaches manually).

### First Use

1. **Register an account** - Navigate to `/auth/user/register`
2. **Choose your role** - Select 'athlete' or 'coach'
3. **Connect to Strava** - Click "Connect with Strava" to authenticate
4. **Sync activities** - Click "Sync" to import your activities
5. **Invite coaches** (athletes) - Go to Profile → Coach Management → Invite by email
6. **Accept invitations** (coaches) - Go to Profile → Pending Invitations → Accept
7. **Add feeling annotations** - Click on any activity to add pain levels and notes
8. **Create extended types** - Go to Admin → Extended Activity Types to create custom classifications
9. **View reports** - Use the "Report" page to review progress over time

## Deployment

### Development

```bash
python run.py
```

Runs on `http://localhost:5000` with debug mode enabled.

### Production (Linux/Ubuntu)

#### 1. Install Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and required packages
sudo apt install python3 python3-pip python3-venv nginx -y

# Clone repository
cd /var/www
sudo git clone <your-repo-url> activity-manager
cd activity-manager

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### 2. Configure Environment

```bash
# Create .env file
sudo nano .env

# Add production settings:
# HOST=https://activity.yourdomain.com
# FLASK_ENV=production
# SECRET_KEY=<generate-strong-key>
# STRAVA_CLIENT_ID=<your-id>
# STRAVA_CLIENT_SECRET=<your-secret>
# (and other settings)
```

#### 3. Initialize Database

```bash
python -c "from app import create_app; app = create_app(); app.app_context().push(); from app.database import init_db; init_db()"
python scripts/migrate_to_multiuser.py
```

#### 4. Set Up Gunicorn

Create systemd service file:

```bash
sudo nano /etc/systemd/system/activity-manager.service
```

Add:

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

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl start activity-manager
sudo systemctl enable activity-manager
sudo systemctl status activity-manager
```

#### 5. Configure Nginx

```bash
sudo nano /etc/nginx/sites-available/activity-manager
```

Add:

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

Enable site:

```bash
sudo ln -s /etc/nginx/sites-available/activity-manager /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### 6. SSL with Let's Encrypt (Recommended)

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d activity.yourdomain.com
```

## Database Utilities

### Multi-User Migration

For existing single-user databases, migrate to multi-user:

```bash
python scripts/migrate_to_multiuser.py activities.db
```

This will:
1. Create a backup of your database
2. Create users and coach-athlete relationship tables
3. Prompt you to create an admin user
4. Assign all existing activities to the admin user
5. Migrate Strava tokens to per-user storage

### Schema Migrations

For general database schema updates:

```bash
python migrate_db.py activities.db
```

## User Roles

### Athlete
- Register and manage their own account
- Connect to their own Strava account
- Sync their activities
- Add feeling annotations and notes
- Invite coaches by email
- Remove coach access

### Coach
- Register as a coach
- Accept/reject athlete invitations
- View all activities for their athletes
- Add coach comments to activities
- Switch between viewing own data and athlete data
- Cannot directly invite athletes (athletes must invite them)

## Data Model

### Core Tables

- **users** - User accounts with authentication
- **coach_athlete_relationships** - Coach-athlete access control
- **activities** - Strava activities with feeling annotations (per user)
- **days** - Daily overall feelings and coach comments (per user)
- **strava_tokens** - OAuth tokens (per user)
- **extended_activity_types** - Custom activity classifications
- **standard_activity_types** - Official Strava sport types
- **gear** - Equipment tracking (bikes, shoes, etc.)
- **activity_media** - Photos linked to activities

### Key Features

- **Foreign Key Constraints** - Maintain data integrity
- **Per-User Data** - All activities and tokens scoped to individual users
- **Role-Based Access** - Coach access controlled through relationships table
- **Session-Based View Switching** - Coaches can view athlete data without changing accounts

## API Endpoints

### Authentication
- `GET /auth/user/login` - User login page
- `POST /auth/user/login` - Process login
- `GET /auth/user/register` - Registration page
- `POST /auth/user/register` - Create account
- `GET /auth/user/logout` - Logout

### Strava OAuth
- `GET /auth/strava/connect` - Initiate Strava OAuth
- `GET /auth/strava/callback` - OAuth callback
- `GET /auth/strava/disconnect` - Disconnect Strava

### Activities
- `GET /api/activities/` - List activities (filtered by current user/viewing context)
- `GET /api/activities/<id>` - Get single activity
- `POST /api/activities/sync` - Sync from Strava
- `GET /api/activities/stats` - Aggregate statistics

### Admin
- `GET /admin/profile` - User profile management
- `POST /admin/profile/update` - Update profile
- `POST /admin/profile/password` - Change password
- `POST /admin/coaches/invite` - Invite coach (athletes)
- `POST /admin/coaches/<id>/remove` - Remove coach (athletes)
- `POST /admin/athletes/<id>/accept` - Accept invitation (coaches)
- `POST /admin/athletes/<id>/reject` - Reject invitation (coaches)
- `POST /admin/switch-view/<id>` - Switch viewing context (coaches)

## Security Notes

- Passwords are hashed with bcrypt
- Session-based authentication via Flask-Login
- CSRF protection on all forms
- OAuth tokens stored per-user in database
- Role-based access control for coach-athlete data
- `.env` file excluded from version control (.gitignore)
- Database files excluded from version control

## Troubleshooting

### SMTP Email Errors

If coach invitations don't send emails:

1. Check SMTP credentials in `.env`
2. For Gmail: Use app-specific password, not regular password
3. For ProtonMail: Ensure FROM_EMAIL matches SMTP_USERNAME
4. Test SMTP: `python test_smtp.py your-email@example.com`

### Strava OAuth Errors

If Strava connection fails:

1. Verify `HOST` in `.env` matches your actual URL
2. Check Strava app's Authorization Callback Domain matches `HOST` domain
3. Ensure `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET` are correct

### Database Errors

If activities don't sync:

1. Check database permissions
2. Run migrations: `python scripts/migrate_to_multiuser.py`
3. Initialize schema: `python -c "from app import create_app; app = create_app(); app.app_context().push(); from app.database import init_db; init_db()"`

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
Create and track your weekly training schedule. Plan recovery runs, tempo workouts, and long runs with specific targets.

### Injury Recovery
Document your return from injury by tracking how each activity affects you. Use extended types to classify workouts by intensity. Share reports with your physiotherapist.

### Coaching
Coaches can monitor multiple athletes, view their training data, add feedback, and track progress over time.

### Pattern Recognition
Identify which activities, intensities, or combinations lead to increased discomfort using the comprehensive reporting features.

## Tech Stack

- **Backend**: Flask, Python 3.8+
- **Database**: SQLite (lightweight, no setup required)
- **Authentication**: Flask-Login, bcrypt
- **API Integration**: stravalib (Strava API)
- **Frontend**: Bootstrap 5, Font Awesome
- **Email**: SMTP (configurable)
- **Production Server**: Gunicorn

## License

This project is for personal use.

## Contributing

This is a personal project, but suggestions and bug reports are welcome via issues.

## Resources

- [Strava API Documentation](https://developers.strava.com/docs/reference/)
- [Bootstrap 5 Documentation](https://getbootstrap.com/docs/5.3/)
- [Font Awesome Icons](https://fontawesome.com/)
- [Flask Documentation](https://flask.palletsprojects.com/)
