"""
WSGI entry point for production deployment with Gunicorn.

Usage:
    gunicorn wsgi:app
    gunicorn wsgi:app -w 4 -b 0.0.0.0:8000
    gunicorn wsgi:app --workers 4 --bind 0.0.0.0:8000 --timeout 120
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
