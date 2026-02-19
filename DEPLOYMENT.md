# Production Deployment Guide

This guide covers deploying the Activity Manager application to production.

## Prerequisites

- Python 3.8+
- Web server (Nginx recommended)
- WSGI server (Gunicorn recommended)
- Domain with SSL certificate (Let's Encrypt recommended)
- SMTP server credentials (optional, for coach invitations)

## Database Migrations

### Fresh Installation

If deploying to a fresh environment with no existing data:

```bash
# 1. Initialize the database
python -c "from app import create_app; app = create_app(); app.app_context().push(); from app.database import init_db; init_db()"

# 2. Run multi-user migration to create tables
python scripts/migrate_to_multiuser.py

# 3. Run coach invitation migration
python scripts/migrate_coach_invitations.py
```

### Migrating Existing Single-User Installation

If you have an existing single-user Activity Manager database:

```bash
# 1. IMPORTANT: Backup your database first!
cp activities.db activities.db.backup

# 2. Run multi-user migration (creates users table, prompts for admin user)
python scripts/migrate_to_multiuser.py activities.db

# 3. Run coach invitation migration (adds email-based invitations)
python scripts/migrate_coach_invitations.py activities.db
```

The multi-user migration will:
- ✓ Create a backup automatically
- ✓ Create `users` table with authentication
- ✓ Create `coach_athlete_relationships` table
- ✓ Prompt you to create an admin user
- ✓ Assign all existing activities to the admin user
- ✓ Migrate Strava tokens to per-user storage

The coach invitation migration will:
- ✓ Create a backup automatically
- ✓ Add `coach_email` field to `coach_athlete_relationships`
- ✓ Update schema to support email-based invitations

## Environment Configuration

### Required Settings

Create a `.env` file with the following **required** settings:

```env
# Main Configuration
HOST=https://activity.yourdomain.com

# Flask Configuration
FLASK_APP=run.py
FLASK_ENV=production
SECRET_KEY=<generate-strong-random-key>

# Session Configuration (in seconds)
SESSION_LIFETIME=86400
REMEMBER_ME_DURATION=2592000

# Database
DATABASE_PATH=/var/www/activity-manager/activities.db

# Strava API Credentials
STRAVA_CLIENT_ID=<your-strava-client-id>
STRAVA_CLIENT_SECRET=<your-strava-client-secret>
```

**Important:** Do NOT use inline comments in `.env` files (e.g., `SESSION_LIFETIME=86400 # comment`). Comments must be on separate lines.

### Optional Settings

Email notifications for coach invitations (recommended):

```env
# Email Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=<app-specific-password>
FROM_EMAIL=your-email@gmail.com
```

**Note:** Many SMTP providers (Gmail, ProtonMail) require `FROM_EMAIL` to match `SMTP_USERNAME`.

### Generate SECRET_KEY

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Strava OAuth Setup

1. Go to https://www.strava.com/settings/api
2. Update your Strava application:
   - **Authorization Callback Domain**: `yourdomain.com` (without http/https)
3. Verify `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET` in `.env`

## Server Setup (Ubuntu/Debian)

### 1. Install Dependencies

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv nginx -y
```

### 2. Deploy Application

```bash
# Clone repository
cd /var/www
sudo git clone <your-repo-url> activity-manager
cd activity-manager

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file (copy settings from above)
sudo nano .env
```

### 3. Run Migrations

```bash
# Initialize database and run migrations (see Database Migrations section above)
python scripts/migrate_to_multiuser.py
python scripts/migrate_coach_invitations.py
```

### 4. Configure Gunicorn

Create systemd service:

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

### 5. Configure Nginx

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
        expires 30d;
    }
}
```

Enable site:

```bash
sudo ln -s /etc/nginx/sites-available/activity-manager /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 6. SSL with Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d activity.yourdomain.com
```

## File Permissions

Ensure proper permissions:

```bash
sudo chown -R www-data:www-data /var/www/activity-manager
sudo chmod 644 /var/www/activity-manager/activities.db
sudo chmod 755 /var/www/activity-manager
```

## First User Registration

After deployment:

1. Navigate to `https://activity.yourdomain.com/auth/user/register`
2. Create your first user account (athlete or coach)
3. Connect to Strava and sync activities

If you migrated from single-user, log in with the admin credentials you created during migration.

## Updating the Application

```bash
cd /var/www/activity-manager
source venv/bin/activate

# Pull latest changes
sudo git pull

# Update dependencies (if changed)
pip install -r requirements.txt

# Run any new migrations (check migration files)
# python scripts/new_migration.py

# Restart service
sudo systemctl restart activity-manager
```

## Troubleshooting

### Check Logs

```bash
# Gunicorn service logs
sudo journalctl -u activity-manager -f

# Nginx logs
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

### Common Issues

**SMTP Email Not Sending:**
- Check SMTP credentials in `.env`
- For Gmail: Use [app-specific password](https://support.google.com/accounts/answer/185833)
- Ensure `FROM_EMAIL` matches `SMTP_USERNAME`

**Strava OAuth Fails:**
- Verify `HOST` in `.env` matches actual domain (with https://)
- Check Strava app's Authorization Callback Domain
- Ensure domain matches exactly (no trailing slashes)

**Database Permission Errors:**
- Check file ownership: `ls -la activities.db`
- Fix permissions: `sudo chown www-data:www-data activities.db`

**Activities Not Showing:**
- Log in as the user who owns the activities
- For coaches: Check that athlete has invited and you've accepted

## Security Checklist

- [ ] Strong `SECRET_KEY` generated and set
- [ ] `FLASK_ENV=production` set in `.env`
- [ ] SSL certificate installed (HTTPS)
- [ ] `.env` file permissions: `chmod 600 .env`
- [ ] Database not publicly accessible
- [ ] Firewall configured (ports 80, 443 open)
- [ ] Regular database backups scheduled
- [ ] Strava OAuth credentials kept secret

## Backup Strategy

### Database Backup

```bash
# Manual backup
cp activities.db activities.db.backup_$(date +%Y%m%d)

# Automated daily backup (add to crontab)
0 2 * * * cp /var/www/activity-manager/activities.db /var/backups/activity-manager/activities.db.$(date +\%Y\%m\%d)
```

### Restore from Backup

```bash
# Stop service
sudo systemctl stop activity-manager

# Restore database
cp activities.db.backup activities.db

# Start service
sudo systemctl start activity-manager
```

## Migration Order Summary

For production deployment with existing data:

1. **Backup database** ← CRITICAL
2. Run `migrate_to_multiuser.py` (creates users, assigns activities)
3. Run `migrate_coach_invitations.py` (adds email invitations)
4. Configure `.env` with production settings
5. Set up Gunicorn + Nginx
6. Enable SSL
7. Test thoroughly

## Support

For issues or questions:
- Check logs first (see Troubleshooting section)
- Review README.md for feature documentation
- Check GitHub issues
