"""
The auth module provides functionalities for user authentication,
including registration, sign-in, sign-out, and OAuth integration.

This __init__.py file exposes the main router for the auth module,
making it easy to include in the main FastAPI application.
"""

from .routers import router

__all__ = ["router"]
