"""Authentication decorators for route protection"""

from functools import wraps
from flask import redirect, url_for, flash, request, session
from flask_login import current_user


def login_required(f):
    """Decorator to require user login

    Redirects to login page if user is not authenticated.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            # Store the original destination
            session['next'] = request.url
            return redirect(url_for('auth.user_login'))
        return f(*args, **kwargs)
    return decorated_function


def athlete_required(f):
    """Decorator to require athlete role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.user_login'))

        if not current_user.is_athlete():
            flash('This page is only accessible to athletes.', 'danger')
            return redirect(url_for('web.index'))

        return f(*args, **kwargs)
    return decorated_function


def coach_required(f):
    """Decorator to require coach role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.user_login'))

        if not current_user.is_coach():
            flash('This page is only accessible to coaches.', 'danger')
            return redirect(url_for('web.index'))

        return f(*args, **kwargs)
    return decorated_function


def anonymous_required(f):
    """Decorator to require anonymous user (not logged in)

    Useful for login/register pages - redirects to index if already logged in.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated:
            return redirect(url_for('web.index'))
        return f(*args, **kwargs)
    return decorated_function
