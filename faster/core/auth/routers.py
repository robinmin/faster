from enum import Enum
from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import RedirectResponse
from supabase_auth.types import User as UserProfile

from ..logger import get_logger
from ..schemas import AppResponse
from ..utilities import is_api_call
from .auth_proxy import get_optional_user
from .services import AuthService

logger = get_logger(__name__)

url_prefix = "/auth"
router = APIRouter(prefix=url_prefix, tags=["auth"])


class AuthURL(Enum):
    LOGIN = url_prefix + "/login"
    LOGOUT = url_prefix + "/logout"
    ONBOARDING = url_prefix + "/onboarding"
    DASHBOARD = url_prefix + "/dashboard"
    PROFILE = url_prefix + "/profile"


# TODO: This should be injected as a dependency
auth_service = AuthService(
    jwt_secret="",  # Not used in this service instance
    supabase_url="",  # Not used in this service instance
    supabase_anon_key="",  # Not used in this service instance
    supabase_service_key="",  # Not used in this service instance
    supabase_jwks_url="",  # Not used in this service instance
    supabase_audience="",  # Not used in this service instance
)


@router.get("/login", include_in_schema=False, response_model=None, tags=["public"])
async def login(request: Request) -> RedirectResponse | AppResponse[dict[str, Any]]:
    """
    Default authentication page for all users including non-logged in users.
    This endpoint determines where to redirect users based on their authentication status.
    """

    # Supabase will redirect with a 'code' in the query parameters
    code = request.query_params.get("code")
    logger.info(f"Received Supabase code: {code}")

    user: UserProfile | None = await get_optional_user(request)

    resp_url = AuthURL.LOGIN.value
    reesp_msg = ""
    resp_code = status.HTTP_200_OK
    if user:
        # Check if user has completed onboarding by checking if they have a profile
        has_profile = await auth_service.check_user_onboarding_complete(user.id)

        if has_profile:
            # Existing user with profile - redirect to dashboard
            resp_url = AuthURL.DASHBOARD.value
            reesp_msg = "Welcome back, my friend! "
            resp_code = status.HTTP_303_SEE_OTHER
        else:
            # New user without profile - redirect to onboarding
            resp_url = AuthURL.ONBOARDING.value
            reesp_msg = "Welcome! Please complete your profile setup."
            resp_code = status.HTTP_303_SEE_OTHER
    else:
        # Non-authenticated users go to a landing page or login page
        resp_url = AuthURL.LOGIN.value
        reesp_msg = "Hi, Please login first."
        resp_code = status.HTTP_303_SEE_OTHER

    # response to API call or avoid to redirect to itself
    if is_api_call(request) or resp_url == request.url.path:
        return AppResponse(status="success", message=reesp_msg, data={"url": resp_url, "status_code": resp_code})

    return RedirectResponse(url=resp_url, status_code=resp_code)


@router.get("/logout", include_in_schema=False, response_model=None, tags=["public"])
async def logout(request: Request) -> RedirectResponse | AppResponse[dict[str, Any]]:
    """
    Default page for user logout
    """
    user: UserProfile | None = await get_optional_user(request)

    resp_url = AuthURL.LOGIN.value
    reesp_msg = ""
    resp_code = status.HTTP_200_OK
    if user:
        # TODO: Implement user logout logic
        # await auth_service.logout_user(user.id)

        reesp_msg = "Hope you come back soon!"
    else:
        resp_url = AuthURL.LOGIN.value
        reesp_msg = "Hi, Please login first."

    if is_api_call(request):
        return AppResponse(status="success", message=reesp_msg, data={"url": resp_url, "status_code": resp_code})
    return RedirectResponse(url=resp_url, status_code=resp_code)


@router.get("/onboarding", include_in_schema=False, response_model=None, tags=["public"])
async def onboarding(request: Request) -> RedirectResponse | AppResponse[dict[str, Any]]:
    """
    Onboarding page for new users.
    Redirects existing users to the dashboard.
    """
    user: UserProfile | None = await get_optional_user(request)

    if not user:
        # If user is not authenticated, redirect to login
        resp_url = AuthURL.LOGIN.value
        if is_api_call(request):
            return AppResponse(
                status="redirect",
                message="Hi, Please login first.",
                data={"url": resp_url, "status_code": status.HTTP_303_SEE_OTHER},
            )
        return RedirectResponse(url=resp_url, status_code=status.HTTP_303_SEE_OTHER)

    # User is authenticated, check onboarding status
    has_profile = await auth_service.check_user_onboarding_complete(user.id)

    if has_profile:
        # User already has a profile, redirect to dashboard
        resp_url = AuthURL.DASHBOARD.value
        if is_api_call(request):
            return AppResponse(
                status="redirect",
                message="Welcome back, my friend!",
                data={"url": resp_url, "status_code": status.HTTP_303_SEE_OTHER},
            )
        return RedirectResponse(url=resp_url, status_code=status.HTTP_303_SEE_OTHER)

    # New user without profile - show onboarding content
    return AppResponse(
        status="success",
        message="Welcome! Please complete your profile setup.",
        data={"user_id": user.id, "email": user.email},
    )


@router.get("/dashboard", include_in_schema=False, response_model=None, tags=["public"])
async def dashboard(request: Request) -> RedirectResponse | AppResponse[dict[str, Any]]:
    """
    Dashboard page for existing users.
    Redirects non-authenticated users to the login page.
    """
    user: UserProfile | None = await get_optional_user(request)

    if not user:
        # If user is not authenticated, redirect to login
        return RedirectResponse(url=AuthURL.LOGIN.value, status_code=status.HTTP_303_SEE_OTHER)

    # Check if user has completed onboarding
    has_profile = await auth_service.check_user_onboarding_complete(user.id)

    if not has_profile:
        # User hasn't completed onboarding, redirect to onboarding
        return RedirectResponse(url=AuthURL.ONBOARDING.value, status_code=status.HTTP_303_SEE_OTHER)

    # Authenticated users with profiles go to the dashboard
    return AppResponse(
        status="success", message="Welcome to your dashboard", data={"user_id": user.id, "email": user.email}
    )


@router.get("/profile", include_in_schema=False, response_model=None, tags=["public"])
async def profile(request: Request) -> RedirectResponse | AppResponse[dict[str, Any]]:
    """
    User profile page.
    Only accessible to logged-in users.
    """
    user: UserProfile | None = await get_optional_user(request)

    if not user:
        # If user is not authenticated, redirect to login
        return RedirectResponse(url=AuthURL.LOGIN.value, status_code=status.HTTP_303_SEE_OTHER)

    # Check if user has completed onboarding
    has_profile = await auth_service.check_user_onboarding_complete(user.id)

    if not has_profile:
        # User hasn't completed onboarding, redirect to onboarding
        return RedirectResponse(url=AuthURL.ONBOARDING.value, status_code=status.HTTP_303_SEE_OTHER)

    # Authenticated users with profiles can view their profile
    return AppResponse(
        status="success",
        message="User profile",
        data={
            "id": user.id,
            "email": user.email,
            "email_confirmed_at": user.email_confirmed_at,
            "created_at": user.created_at,
            "last_sign_in_at": user.last_sign_in_at,
            "user_metadata": user.user_metadata,
        },
    )
