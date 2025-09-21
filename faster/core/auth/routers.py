from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from ..logger import get_logger
from ..models import AppResponseDict
from ..redisex import blacklist_delete
from .middlewares import get_current_user, has_role
from .models import UserProfileData
from .services import AuthService
from .utilities import extract_bearer_token_from_request, log_event

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service() -> AuthService:
    """Dependency to get the AuthService singleton instance."""
    return AuthService.get_instance()


@router.get("/onboarding", include_in_schema=False, response_model=None)
async def onboarding(
    request: Request,
    user: UserProfileData | None = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> AppResponseDict:
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

    # Log onboarding access event
    _ = await log_event(
        request=request,
        event_type="user",
        event_name="onboarding_accessed",
        event_source="user_action",
        user_auth_id=user.id,
        event_payload={"has_profile": has_profile, "status": "accessed"},
    )

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
async def dashboard(
    request: Request,
    user: UserProfileData | None = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> AppResponseDict:
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

    # Log dashboard access event
    _ = await log_event(
        request=request,
        event_type="user",
        event_name="dashboard_accessed",
        event_source="user_action",
        user_auth_id=user.id,
        event_payload={"has_profile": has_profile, "status": "accessed"},
    )

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
    auth_service: AuthService = Depends(get_auth_service),
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
    _ = await log_event(
        request=request,
        event_type="auth",
        event_name=event,
        event_source="supabase",
        user_auth_id=user.id,
        event_payload={"status": "success", "endpoint": "callback"},
    )

    # Route to specific event handlers
    try:
        if event == "SIGNED_IN":
            result = await _handle_signed_in(request, background_tasks, user, auth_service)
        elif event == "SIGNED_OUT":
            result = await _handle_signed_out(request, background_tasks, user, auth_service)
        elif event == "TOKEN_REFRESHED":
            result = await _handle_token_refreshed(request, user)
        elif event == "USER_UPDATED":
            result = await _handle_user_updated(request, background_tasks, user, auth_service)
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
    auth_service: AuthService = Depends(get_auth_service),
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
    _ = await log_event(
        request=request,
        event_type="auth",
        event_name=event,
        event_source="supabase",
        user_auth_id=None,  # Public events don't have authenticated users
        event_payload={"status": "success", "endpoint": "notification"},
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
    request: Request, background_tasks: BackgroundTasks, user: UserProfileData, auth_service: AuthService
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

    # Prepare response data
    response_data: dict[str, Any] = {"event": "SIGNED_IN", "user_id": user.id}

    # Check if current user has 'developer' role and add available roles
    if await has_role(request, "developer"):
        available_roles = await auth_service.get_all_available_roles()
        response_data["available_roles"] = available_roles
        logger.debug(f"Added available roles for developer user {user.id}: {available_roles}")

    logger.info(f"User signed in successfully: {user.id}")
    return AppResponseDict(status="success", message="User signed in successfully", data=response_data)


async def _handle_signed_out(
    request: Request, background_tasks: BackgroundTasks, user: UserProfileData, auth_service: AuthService
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
    request: Request, background_tasks: BackgroundTasks, user: UserProfileData, auth_service: AuthService
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

    # Log profile access event
    _ = await log_event(
        request=request,
        event_type="user",
        event_name="profile_accessed",
        event_source="user_action",
        user_auth_id=user.id,
        event_payload={"status": "accessed", "has_metadata": bool(user_metadata)},
    )

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


# =============================================================================
# Password Management Endpoints
# =============================================================================


@router.post("/password/change", include_in_schema=False, response_model=None)
async def change_password(
    request: Request,
    user: UserProfileData | None = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> AppResponseDict:
    """
    Change user password.
    Requires current password verification.
    """
    if not user:
        return AppResponseDict(
            status="failed",
            message="Authentication required. Please login first.",
            data={},
        )

    try:
        body = await request.json()
        current_password = body.get("current_password")
        new_password = body.get("new_password")

        if not current_password or not new_password:
            return AppResponseDict(
                status="failed",
                message="Current password and new password are required.",
                data={},
            )

        result = await auth_service.change_password(user.id, current_password, new_password)

        # Log password change event
        _ = await log_event(
            request=request,
            event_type="password",
            event_name="password_changed",
            event_source="user_action",
            user_auth_id=user.id,
            event_payload={"status": "success" if result else "failed"},
        )

        if result:
            return AppResponseDict(
                status="success",
                message="Password changed successfully.",
                data={"user_id": user.id},
            )
        return AppResponseDict(
            status="failed",
            message="Failed to change password. Please verify your current password.",
            data={},
        )

    except Exception as e:
        logger.error(f"Error changing password for user {user.id}: {e}")
        return AppResponseDict(
            status="failed",
            message="An error occurred while changing password.",
            data={},
        )


@router.post("/password/reset/initiate", include_in_schema=False, response_model=None, tags=["public"])
async def initiate_password_reset(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> AppResponseDict:
    """
    Initiate password reset process.
    Public endpoint - sends reset email to user.
    """
    try:
        body = await request.json()
        email = body.get("email")

        if not email:
            return AppResponseDict(
                status="failed",
                message="Email address is required.",
                data={},
            )

        result = await auth_service.initiate_password_reset(email)

        # Log password reset initiation event (no user_auth_id since it's public)
        _ = await log_event(
            request=request,
            event_type="password",
            event_name="password_reset_initiated",
            event_source="user_action",
            user_auth_id=None,
            event_payload={"email": email, "status": "success" if result else "failed"},
        )

        if result:
            return AppResponseDict(
                status="success",
                message="Password reset email sent if account exists.",
                data={"email": email},
            )
        return AppResponseDict(
            status="success",
            message="Password reset email sent if account exists.",
            data={"email": email},
        )

    except Exception as e:
        logger.error(f"Error initiating password reset for email: {e}")
        return AppResponseDict(
            status="failed",
            message="An error occurred while processing password reset request.",
            data={},
        )


@router.post("/password/reset/confirm", include_in_schema=False, response_model=None, tags=["public"])
async def confirm_password_reset(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> AppResponseDict:
    """
    Confirm password reset with token.
    Public endpoint - completes password reset process.
    """
    try:
        body = await request.json()
        token = body.get("token")
        new_password = body.get("new_password")

        if not token or not new_password:
            return AppResponseDict(
                status="failed",
                message="Reset token and new password are required.",
                data={},
            )

        result = await auth_service.confirm_password_reset(token, new_password)

        # Log password reset confirmation event (no user_auth_id since it's public)
        _ = await log_event(
            request=request,
            event_type="password",
            event_name="password_reset_confirmed",
            event_source="user_action",
            user_auth_id=None,
            event_payload={"status": "success" if result else "failed", "token_valid": result},
        )

        if result:
            return AppResponseDict(
                status="success",
                message="Password reset completed successfully.",
                data={},
            )
        return AppResponseDict(
            status="failed",
            message="Invalid or expired reset token.",
            data={},
        )

    except Exception as e:
        logger.error(f"Error confirming password reset: {e}")
        return AppResponseDict(
            status="failed",
            message="An error occurred while resetting password.",
            data={},
        )


# =============================================================================
# Account Management Endpoints
# =============================================================================


@router.post("/deactivate", include_in_schema=False, response_model=None, tags=["admin"])
async def deactivate(
    request: Request,
    background_tasks: BackgroundTasks,
    user: UserProfileData | None = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> AppResponseDict:
    """
    Deactivate user account and all associated data.
    This performs a comprehensive deactivation of the account.
    """
    if not user:
        return AppResponseDict(
            status="failed",
            message="Authentication required. Please login first.",
            data={},
        )

    try:
        body = await request.json()
        password = body.get("password")

        if not password:
            return AppResponseDict(
                status="failed",
                message="Password confirmation is required to deactivate account.",
                data={},
            )

        result = await auth_service.deactivate(user.id, password)

        # Log account deactivation event
        _ = await log_event(
            request=request,
            event_type="user",
            event_name="account_deactivated",
            event_source="user_action",
            user_auth_id=user.id,
            event_payload={"status": "success" if result else "failed"},
        )

        if result:
            token = extract_bearer_token_from_request(request)
            background_tasks.add_task(auth_service.background_process_logout, token, user)

            return AppResponseDict(
                status="success",
                message="Account deactivated successfully.",
                data={"user_id": user.id},
            )
        return AppResponseDict(
            status="failed",
            message="Failed to deactivate account. Please verify your password.",
            data={},
        )

    except Exception as e:
        logger.error(f"Error deactivating account for user {user.id}: {e}")
        return AppResponseDict(
            status="failed",
            message="An error occurred while deactivating account.",
            data={},
        )


# =============================================================================
# User Administration Endpoints
# =============================================================================


@router.post("/users/{user_id}/ban", include_in_schema=False, response_model=None, tags=["admin"])
async def ban_user(
    user_id: str,
    request: Request,
    user: UserProfileData | None = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> AppResponseDict:
    """
    Ban a user account.
    """
    if not user:
        return AppResponseDict(
            status="failed",
            message="Authentication required. Please login first.",
            data={},
        )

    try:
        body = await request.json()
        reason = body.get("reason", "")

        result = await auth_service.ban_user(user.id, user_id, reason)

        # Log user ban event
        _ = await log_event(
            request=request,
            event_type="admin",
            event_name="user_banned",
            event_source="admin_action",
            user_auth_id=user.id,
            event_payload={
                "target_user_id": user_id,
                "reason": reason,
                "status": "success" if result else "failed",
            },
        )

        if result:
            return AppResponseDict(
                status="success",
                message="User banned successfully.",
                data={"target_user_id": user_id, "banned_by": user.id},
            )
        return AppResponseDict(
            status="failed",
            message="Failed to ban user. Insufficient permissions or user not found.",
            data={},
        )

    except Exception as e:
        logger.error(f"Error banning user {user_id} by admin {user.id}: {e}")
        return AppResponseDict(
            status="failed",
            message="An error occurred while banning user.",
            data={},
        )


@router.post("/users/{user_id}/unban", include_in_schema=False, response_model=None, tags=["admin"])
async def unban_user(
    user_id: str,
    request: Request,
    user: UserProfileData | None = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> AppResponseDict:
    """
    Unban a user account.
    """
    if not user:
        return AppResponseDict(
            status="failed",
            message="Authentication required. Please login first.",
            data={},
        )

    try:
        result = await auth_service.unban_user(user.id, user_id)

        # Log user unban event
        _ = await log_event(
            request=request,
            event_type="admin",
            event_name="user_unbanned",
            event_source="admin_action",
            user_auth_id=user.id,
            event_payload={"target_user_id": user_id, "status": "success" if result else "failed"},
        )

        if result:
            return AppResponseDict(
                status="success",
                message="User unbanned successfully.",
                data={"target_user_id": user_id, "unbanned_by": user.id},
            )
        return AppResponseDict(
            status="failed",
            message="Failed to unban user. Insufficient permissions or user not found.",
            data={},
        )

    except Exception as e:
        logger.error(f"Error unbanning user {user_id} by admin {user.id}: {e}")
        return AppResponseDict(
            status="failed",
            message="An error occurred while unbanning user.",
            data={},
        )


# =============================================================================
# Role Management Endpoints (Admin Only)
# =============================================================================


@router.post("/users/{user_id}/roles/adjust", include_in_schema=False, response_model=None, tags=["admin"])
async def adjust_roles(
    user_id: str,
    request: Request,
    user: UserProfileData | None = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> AppResponseDict:
    """
    Adjust user roles. Replaces all existing roles with the provided roles list.
    """
    if not user:
        return AppResponseDict(
            status="failed",
            message="Authentication required. Please login first.",
            data={},
        )

    try:
        body = await request.json()
        roles = body.get("roles", [])

        if not roles or not isinstance(roles, list):
            return AppResponseDict(
                status="failed",
                message="At least one role is required.",
                data={},
            )

        # Validate that at least one role is provided
        if len(roles) == 0:
            return AppResponseDict(
                status="failed",
                message="Please select at least one role.",
                data={},
            )

        result = await auth_service.adjust_roles(
            user.id,
            user_id,
            roles,
        )

        # Log role adjustment event
        _ = await log_event(
            request=request,
            event_type="admin",
            event_name="roles_adjusted",
            event_source="admin_action",
            user_auth_id=user.id,
            event_payload={
                "target_user_id": user_id,
                "new_roles": roles,
                "status": "success" if result else "failed",
            },
        )

        if result:
            return AppResponseDict(
                status="success",
                message="User roles adjusted successfully.",
                data={"target_user_id": user_id, "new_roles": roles, "adjusted_by": user.id},
            )
        return AppResponseDict(
            status="failed",
            message="Failed to adjust roles. Insufficient permissions or user not found.",
            data={},
        )

    except Exception as e:
        logger.error(f"Error adjusting roles for user {user_id} by admin {user.id}: {e}")
        return AppResponseDict(
            status="failed",
            message="An error occurred while adjusting roles.",
            data={},
        )


@router.get("/users/{user_id}/basic", include_in_schema=False, response_model=None, tags=["admin"])
async def get_user_basic_info(
    user_id: str,
    request: Request,
    user: UserProfileData | None = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> AppResponseDict:
    """
    Get user basic information including ID, email, status, and roles.
    """
    if not user:
        return AppResponseDict(
            status="failed",
            message="Authentication required. Please login first.",
            data={},
        )

    try:
        basic_info = await auth_service.get_user_basic_info_by_id(
            user.id,
            user_id,
        )

        # Log user basic info access event
        _ = await log_event(
            request=request,
            event_type="admin",
            event_name="user_basic_info_accessed",
            event_source="admin_action",
            user_auth_id=user.id,
            event_payload={
                "target_user_id": user_id,
                "status": "success" if basic_info is not None else "failed",
            },
        )

        if basic_info is not None:
            return AppResponseDict(
                status="success",
                message="User basic information retrieved successfully.",
                data={
                    "target_user_id": user_id,
                    "id": basic_info.get("id"),
                    "email": basic_info.get("email"),
                    "status": basic_info.get("status", "unknown"),
                    "roles": basic_info.get("roles", []),
                },
            )
        return AppResponseDict(
            status="failed",
            message="Failed to get user basic information. Insufficient permissions or user not found.",
            data={},
        )

    except Exception as e:
        logger.error(f"Error getting basic info for user {user_id} by admin {user.id}: {e}")
        return AppResponseDict(
            status="failed",
            message="An error occurred while retrieving user basic information.",
            data={},
        )
