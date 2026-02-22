"""API blueprint for RESTful endpoints"""

from flask import Blueprint

api_bp = Blueprint('api', __name__, url_prefix='/api')

from app.api import types_routes
from app.api import plan_routes

__all__ = ['api_bp']
