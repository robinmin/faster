from fastapi import APIRouter, BackgroundTasks, Depends, Request

from ..config import Settings
from ..logger import get_logger
from ..models import AppResponseDict
from ..redisex import blacklist_delete
from .middlewares import get_current_user
from .models import UserProfileData
from .services import AuthService
from .utilities import extract_bearer_token_from_request

logger = get_logger(__name__)

url_prefix = "/auth"
router = APIRouter(prefix=url_prefix, tags=["auth"])


# class AuthURL(Enum):
#     ONBOARDING = url_prefix + "/onboarding"
#     DASHBOARD = url_prefix + "/dashboard"
#     PROFILE = url_prefix + "/profile"


# Initialize settings and auth service
settings = Settings()
jwks_url = settings.supabase_jwks_url
if not jwks_url and settings.supabase_url:
    jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"

auth_service = AuthService(
    supabase_url=settings.supabase_url or "",
    supabase_anon_key=settings.supabase_anon_key or "",
    supabase_service_key=settings.supabase_service_key or "",
    supabase_jwks_url=jwks_url or "",
    supabase_audience=settings.supabase_audience or "",
    auto_refresh_jwks=settings.auto_refresh_jwks,
    jwks_cache_ttl_seconds=settings.jwks_cache_ttl_seconds,
    user_cache_ttl_seconds=settings.user_cache_ttl_seconds,
)


@router.get("/onboarding", include_in_schema=False, response_model=None)
async def onboarding(request: Request, user: UserProfileData | None = Depends(get_current_user)) -> AppResponseDict:
    """
    Onboarding page for new users.
    Redirects existing users to the dashboard.
    """
    if not user:
        return AppResponseDict(
            status="failed",
            message="Authentication required. Please login first.",
            data={},
        )

    # User is authenticated, check onboarding status
    has_profile = await auth_service.check_user_onboarding_complete(user.id)

    if has_profile:
        return AppResponseDict(
            status="redirect",
            message="Welcome back, my friend!",
            data={"user_id": user.id},
        )

    # New user without profile - show onboarding content
    return AppResponseDict(
        status="success",
        message="Welcome! Please complete your profile setup.",
        data={"user_id": user.id, "email": user.email},
    )


@router.get("/dashboard", include_in_schema=False, response_model=None)
async def dashboard(request: Request, user: UserProfileData | None = Depends(get_current_user)) -> AppResponseDict:
    """
    Dashboard page for existing users.
    Redirects non-authenticated users to the login page.
    """
    if not user:
        return AppResponseDict(
            status="failed",
            message="Authentication required. Please login first.",
            data={},
        )

    # Check if user has completed onboarding
    has_profile = await auth_service.check_user_onboarding_complete(user.id)

    if not has_profile:
        # User hasn't completed onboarding, redirect to onboarding
        return AppResponseDict(
            status="failed",
            message="Onboarding required. Please complete your profile setup.",
            data={"user_id": user.id},
        )

    # Authenticated users with profiles go to the dashboard
    return AppResponseDict(
        status="success", message="Welcome to your dashboard", data={"user_id": user.id, "email": user.email}
    )


@router.post("/callback/{event}", include_in_schema=False, response_model=None)
async def on_callback(
    event: str,
    request: Request,
    background_tasks: BackgroundTasks,
    user: UserProfileData | None = Depends(get_current_user),
) -> AppResponseDict:
    """
    Centralized callback endpoint for handling authenticated Supabase auth state change events.

    Handles the following events:
    - SIGNED_IN: Emitted each time a user session is confirmed or re-established
    - SIGNED_OUT: Emitted when the user signs out
    - TOKEN_REFRESHED: Emitted each time a new access and refresh token are fetched
    - USER_UPDATED: Emitted each time the supabase.auth.updateUser() method finishes successfully
    - PASSWORD_RECOVERY: Emitted instead of the SIGNED_IN event when the user lands on a page that includes a password recovery link

    This endpoint requires authentication and handles events that occur during an active session.
    """

    if not user:
        logger.warning(f"Callback endpoint accessed without authentication for event: {event}")
        return AppResponseDict(
            status="failed", message="Authentication required for callback endpoint", data={"event": event}
        )

    logger.info(f"Received auth callback event: {event}, user: {user.id}")

    # Log the event to database for tracking and analytics (never throws exceptions)
    client_ip = getattr(request.client, "host", None) if request.client else None
    user_agent = request.headers.get("user-agent")

    _ = await auth_service.log_event(
        event_type="auth",
        event_name=event,
        event_source="supabase",
        user_auth_id=user.id,
        ip_address=client_ip,
        user_agent=user_agent,
        event_payload={"status": "success", "endpoint": "callback"},
        extra_metadata={"request_method": request.method, "url": str(request.url)},
    )

    # Route to specific event handlers
    try:
        if event == "SIGNED_IN":
            result = await _handle_signed_in(request, background_tasks, user)
        elif event == "SIGNED_OUT":
            result = await _handle_signed_out(request, background_tasks, user)
        elif event == "TOKEN_REFRESHED":
            result = await _handle_token_refreshed(request, user)
        elif event == "USER_UPDATED":
            result = await _handle_user_updated(request, background_tasks, user)
        elif event == "PASSWORD_RECOVERY":
            result = await _handle_password_recovery()
        else:
            logger.warning(f"Invalid auth event received: {event}")
            result = AppResponseDict(
                status="failed",
                message=f"Invalid event type: {event}",
                data={
                    "valid_events": ["SIGNED_IN", "SIGNED_OUT", "TOKEN_REFRESHED", "USER_UPDATED", "PASSWORD_RECOVERY"]
                },
            )
        # Future events can be added here with additional elif clauses
    except Exception as e:
        logger.error(f"Error processing event {event}: {e}")
        result = AppResponseDict(status="failed", message=f"Error processing event {event}", data={"error": str(e)})

    return result


@router.post("/notification/{event}", include_in_schema=False, response_model=None, tags=["public"])
async def on_notification(
    event: str,
    request: Request,
    background_tasks: BackgroundTasks,
) -> AppResponseDict:
    """
    Public notification endpoint for handling Supabase auth state change events that don't require authentication.

    Handles the following events:
    - INITIAL_SESSION: Emitted right after the Supabase client is constructed

    This endpoint is public and doesn't require authentication, making it suitable for events
    that occur before a user session is established.
    """

    logger.info(f"Received public auth notification event: {event}")

    # Log the public event to database for tracking and analytics (never throws exceptions)
    client_ip = getattr(request.client, "host", None) if request.client else None
    user_agent = request.headers.get("user-agent")

    _ = await auth_service.log_event(
        event_type="auth",
        event_name=event,
        event_source="supabase",
        user_auth_id=None,  # Public events don't have authenticated users
        ip_address=client_ip,
        user_agent=user_agent,
        event_payload={"status": "success", "endpoint": "notification"},
        extra_metadata={"request_method": request.method, "url": str(request.url)},
    )

    # Route to specific event handlers
    try:
        if event == "INITIAL_SESSION":
            result = await _handle_initial_session()
        else:
            logger.warning(f"Invalid or unauthorized event received: {event}")
            result = AppResponseDict(
                status="failed",
                message=f"Event {event} not allowed on public endpoint",
                data={"valid_events": ["INITIAL_SESSION"]},
            )
        # Future events can be added here with additional elif clauses
    except Exception as e:
        logger.error(f"Error processing event {event}: {e}")
        result = AppResponseDict(status="failed", message=f"Error processing event {event}", data={"error": str(e)})

    return result


async def _handle_initial_session() -> AppResponseDict:
    """Handle initial session loading for public endpoint (no authentication required)."""
    logger.info("Initial session loaded (public endpoint)")

    return AppResponseDict(
        status="success",
        message="Initial session processed",
        data={"event": "INITIAL_SESSION", "user_id": None},
    )


async def _handle_signed_in(
    request: Request, background_tasks: BackgroundTasks, user: UserProfileData
) -> AppResponseDict:
    """Handle user sign in."""

    # Immediately remove token from blacklist for valid user
    token = extract_bearer_token_from_request(request)
    if token:
        _ = await blacklist_delete(token)
        logger.debug(f"Removed token from blacklist for user {user.id}")

    # Check if user needs database update
    if await auth_service.should_update_user_in_db(user):
        background_tasks.add_task(auth_service.background_update_user_info, token, user.id)
        logger.debug(f"Added background task to update user info for {user.id}")

    logger.info(f"User signed in successfully: {user.id}")
    return AppResponseDict(
        status="success", message="User signed in successfully", data={"event": "SIGNED_IN", "user_id": user.id}
    )


async def _handle_signed_out(
    request: Request, background_tasks: BackgroundTasks, user: UserProfileData
) -> AppResponseDict:
    """Handle user sign out."""
    # Extract token for background processing
    token = extract_bearer_token_from_request(request)
    background_tasks.add_task(auth_service.background_process_logout, token, user)
    logger.debug(f"Added background task to process logout for {user.id}")
    logger.info(f"User logout initiated successfully: {user.id}")

    return AppResponseDict(
        status="success",
        message="User logout processed",
        data={"event": "SIGNED_OUT", "user_id": user.id},
    )


async def _handle_token_refreshed(request: Request, user: UserProfileData) -> AppResponseDict:
    """Handle token refresh."""

    # Remove the new token from blacklist to ensure it's valid
    token = extract_bearer_token_from_request(request)
    if token:
        _ = await blacklist_delete(token)
        logger.debug(f"Removed refreshed token from blacklist for user {user.id}")

    logger.info(f"Token refreshed for user: {user.id}")

    return AppResponseDict(
        status="success",
        message="Token refresh processed",
        data={"event": "TOKEN_REFRESHED", "user_id": user.id},
    )


async def _handle_user_updated(
    request: Request, background_tasks: BackgroundTasks, user: UserProfileData
) -> AppResponseDict:
    """Handle user profile updates."""
    logger.info(f"User profile updated: {user.id}")
    token = extract_bearer_token_from_request(request)
    background_tasks.add_task(auth_service.background_update_user_info, token, user.id)

    return AppResponseDict(
        status="success",
        message="User update processed",
        data={"event": "USER_UPDATED", "user_id": user.id},
    )


async def _handle_password_recovery() -> AppResponseDict:
    """Handle password recovery."""
    logger.info("Password recovery event received")
    return AppResponseDict(status="success", message="Password recovery processed", data={"event": "PASSWORD_RECOVERY"})


@router.get("/profile", include_in_schema=False, response_model=None)
async def profile(request: Request, user: UserProfileData | None = Depends(get_current_user)) -> AppResponseDict:
    """
    User profile page.
    Only accessible to logged-in users.

    Shows comprehensive user profile information including:
    - Profile Header: Avatar, display name, email
    - Personal Info: Full name, bio, location
    - Account Settings: Email, password reset, MFA status
    - Preferences: Theme, language, notifications
    - Danger Zone: Account deletion, sign out options
    """

    if not user:
        return AppResponseDict(
            status="failed",
            message="Authentication required. Please login first.",
            data={},
        )

    # Extract user metadata for additional profile information
    user_metadata = user.user_metadata or {}
    app_metadata = getattr(user, "app_metadata", {}) or {}

    # Build comprehensive profile response
    profile_data = {
        "id": user.id,
        "email": user.email,
        "username": user_metadata.get("username"),
        "roles": getattr(request.state, "roles", []),
        "avatar_url": user_metadata.get("avatar_url") or app_metadata.get("avatar_url"),
        "email_confirmed_at": user.email_confirmed_at,
        "created_at": user.created_at,
        "last_sign_in_at": user.last_sign_in_at,
        "confirmed_at": getattr(user, "confirmed_at", None),
        "updated_at": getattr(user, "updated_at", None),
        "user_metadata": user_metadata,  # Keep for backward compatibility
        "app_metadata": app_metadata,
    }

    return AppResponseDict(
        status="success",
        message="User profile retrieved successfully",
        data=profile_data,
    )
