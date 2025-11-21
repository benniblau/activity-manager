#!/usr/bin/env python3
"""
Activity Manager - Flask Application Entry Point

Usage:
    python run.py
"""
import os
from app import create_app

# Create Flask application instance
app = create_app()

if __name__ == '__main__':
    # Get host and port from environment or use defaults
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5001))

    # Run the application
    app.run(host=host, port=port, debug=app.config.get('DEBUG', True))
