from enum import Enum

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from fastapi.responses import RedirectResponse

from ..logger import get_logger
from ..models import AppResponseDict
from ..redisex import blacklist_delete
from ..utilities import is_api_call
from .middlewares import get_current_user
from .models import UserProfileData
from .services import AuthService
from .utilities import extract_bearer_token_from_request

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


@router.get("/login", include_in_schema=False, response_model=None)
async def login(
    request: Request, background_tasks: BackgroundTasks, user: UserProfileData | None = Depends(get_current_user)
) -> RedirectResponse | AppResponseDict:
    """
    Enhanced login callback with optimized performance and immediate response.

    This endpoint handles user authentication callbacks and provides immediate feedback
    while processing heavy operations in the background for optimal user experience.

    Key Functions:
    - Extract and validate JWT token from request (handled by middleware)
    - Immediately remove valid token from blacklist for security
    - Check onboarding status and return immediate response to client
    - Process user database operations in background (24h update check)
    - Redirect users based on onboarding completion status
    """

    # Supabase will redirect with a 'code' in the query parameters
    code = request.query_params.get("code")
    logger.info(f"Received Supabase code: {code}")

    resp_url = AuthURL.LOGIN.value
    reesp_msg = ""
    resp_code = status.HTTP_200_OK

    has_profile = False  # Default value to avoid unbound variable

    if user:
        try:
            # Immediately remove token from blacklist for valid user
            token = extract_bearer_token_from_request(request)
            if token:
                _ = await blacklist_delete(token)
                logger.debug(f"Removed token from blacklist for user {user.id}")

            # Check onboarding status immediately
            has_profile = await auth_service.check_user_onboarding_complete(user.id)

            # Check if user needs database update before adding background task
            if await auth_service.should_update_user_in_db(user):
                # Add background task to update user info in database
                background_tasks.add_task(auth_service.background_update_user_info, token, user.id)
                logger.debug(f"Added background task to update user info for {user.id}")

            if has_profile:
                # Existing user with profile - redirect to dashboard
                resp_url = AuthURL.DASHBOARD.value
                reesp_msg = "Welcome back, my friend!"
                resp_code = status.HTTP_303_SEE_OTHER
            else:
                # New user without profile - redirect to onboarding
                resp_url = AuthURL.ONBOARDING.value
                reesp_msg = "Welcome! Please complete your profile setup."
                resp_code = status.HTTP_303_SEE_OTHER

        except Exception as e:
            logger.error(f"Error processing user login: {e}")
            # If there's an error processing login, redirect to login page
            resp_url = AuthURL.LOGIN.value
            reesp_msg = "Login processing failed. Please try again."
            resp_code = status.HTTP_303_SEE_OTHER
    else:
        # Non-authenticated users go to a landing page or login page
        resp_url = AuthURL.LOGIN.value
        reesp_msg = "Hi, Please login first."
        resp_code = status.HTTP_303_SEE_OTHER

    # response to API call or avoid to redirect to itself
    if is_api_call(request) or resp_url == request.url.path:
        response_data = {"url": resp_url, "status_code": resp_code}

        # Add onboarding completion status for authenticated users
        if user:
            response_data["onboarding_complete"] = has_profile
            response_data["user_id"] = user.id

        return AppResponseDict(status="success", message=reesp_msg, data=response_data)

    return RedirectResponse(url=resp_url, status_code=resp_code)


@router.get("/logout", include_in_schema=False, response_model=None)
async def logout(
    request: Request, background_tasks: BackgroundTasks, user: UserProfileData | None = Depends(get_current_user)
) -> RedirectResponse | AppResponseDict:
    """
    Enhanced logout endpoint with optimized performance and immediate response.

    This endpoint handles user logout operations and provides immediate feedback
    while processing security operations in the background for optimal user experience.

    Key Functions:
    - Extract JWT token from request for background processing
    - Provide immediate logout response to user
    - Process token blacklisting and cleanup in background
    - Handle both authenticated and non-authenticated logout attempts

    """

    resp_url = AuthURL.LOGIN.value
    reesp_msg = ""
    resp_code = status.HTTP_200_OK

    if user:
        try:
            # Extract token for background processing
            token = extract_bearer_token_from_request(request)

            # Add background task to process logout operations
            background_tasks.add_task(auth_service.background_process_logout, token, user)
            logger.debug(f"Added background task to process logout for {user.id}")

            # Provide immediate response
            reesp_msg = "Hope you come back soon!"
            logger.info(f"User logout initiated successfully: {user.id}")

        except Exception as e:
            logger.error(f"Error initiating logout for user {user.id}: {e}")
            reesp_msg = "Logout completed, but there was an issue processing your request."
    else:
        resp_url = AuthURL.LOGIN.value
        reesp_msg = "Hi, Please login first."

    # Enhanced response for API calls
    if is_api_call(request):
        response_data = {"url": resp_url, "status_code": resp_code}

        # Add user info for authenticated users
        if user:
            response_data["user_id"] = user.id
            response_data["logout_status"] = "processing"

        return AppResponseDict(status="success", message=reesp_msg, data=response_data)

    return RedirectResponse(url=resp_url, status_code=resp_code)


@router.get("/onboarding", include_in_schema=False, response_model=None)
async def onboarding(request: Request) -> RedirectResponse | AppResponseDict:
    """
    Onboarding page for new users.
    Redirects existing users to the dashboard.
    """
    user: UserProfileData | None = await get_current_user(request)

    if not user:
        # If user is not authenticated, redirect to login
        resp_url = AuthURL.LOGIN.value
        if is_api_call(request):
            return AppResponseDict(
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
            return AppResponseDict(
                status="redirect",
                message="Welcome back, my friend!",
                data={"url": resp_url, "status_code": status.HTTP_303_SEE_OTHER},
            )
        return RedirectResponse(url=resp_url, status_code=status.HTTP_303_SEE_OTHER)

    # New user without profile - show onboarding content
    return AppResponseDict(
        status="success",
        message="Welcome! Please complete your profile setup.",
        data={"user_id": user.id, "email": user.email},
    )


@router.get("/dashboard", include_in_schema=False, response_model=None)
async def dashboard(request: Request) -> RedirectResponse | AppResponseDict:
    """
    Dashboard page for existing users.
    Redirects non-authenticated users to the login page.
    """
    user: UserProfileData | None = await get_current_user(request)

    if not user:
        # If user is not authenticated, redirect to login
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    # Check if user has completed onboarding
    has_profile = await auth_service.check_user_onboarding_complete(user.id)

    if not has_profile:
        # User hasn't completed onboarding, redirect to onboarding
        return RedirectResponse(url=AuthURL.ONBOARDING.value, status_code=status.HTTP_303_SEE_OTHER)

    # Authenticated users with profiles go to the dashboard
    return AppResponseDict(
        status="success", message="Welcome to your dashboard", data={"user_id": user.id, "email": user.email}
    )


@router.get("/profile", include_in_schema=False, response_model=None)
async def profile(request: Request) -> RedirectResponse | AppResponseDict:
    """
    User profile page.
    Only accessible to logged-in users.
    """
    user: UserProfileData | None = await get_current_user(request)

    if not user:
        # If user is not authenticated, redirect to login
        return RedirectResponse(url=AuthURL.LOGIN.value, status_code=status.HTTP_303_SEE_OTHER)

    # Check if user has completed onboarding
    has_profile = await auth_service.check_user_onboarding_complete(user.id)

    if not has_profile:
        # User hasn't completed onboarding, redirect to onboarding
        return RedirectResponse(url=AuthURL.ONBOARDING.value, status_code=status.HTTP_303_SEE_OTHER)

    # Authenticated users with profiles can view their profile
    return AppResponseDict(
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
