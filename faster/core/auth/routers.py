"""API endpoints for authentication and user management."""

from fastapi import APIRouter, Depends, HTTPException, status

from faster.core.auth.dependencies import get_auth_service, get_current_user, oauth2_scheme
from faster.core.auth.exceptions import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
)
from faster.core.auth.schemas import (
    MagicLoginRequest,
    OAuthSignIn,
    ResetPasswordRequest,
    Token,
    UserCreate,
    UserRead,
    UserSignIn,
    UserUpdate,
)
from faster.core.auth.services import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def signup(user_create: UserCreate, auth_service: AuthService = Depends(get_auth_service)) -> UserRead:
    """
    Register a new user.
    """
    try:
        user = await auth_service.signup(user_create)
        return user
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.post("/signin", response_model=Token)
async def signin(user_signin: UserSignIn, auth_service: AuthService = Depends(get_auth_service)) -> Token:
    """
    Authenticate a user and return a token.
    """
    try:
        session = await auth_service.signin(user_signin)
        return session
    except InvalidCredentialsError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e


@router.post("/magic-login", response_model=Token)
async def magic_login(
    magic_login_request: MagicLoginRequest, auth_service: AuthService = Depends(get_auth_service)
) -> Token:
    """
    Authenticate a user using a magic link token.
    """
    try:
        session = await auth_service.magic_login(magic_login_request.email, magic_login_request.token)
        return session
    except InvalidCredentialsError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e


@router.post("/signout", status_code=status.HTTP_204_NO_CONTENT)
async def signout(
    token: str = Depends(oauth2_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    """
    Sign out the current user.
    """
    await auth_service.signout(token)


@router.get("/me", response_model=UserRead)
async def get_me(current_user: UserRead = Depends(get_current_user)) -> UserRead:
    """
    Get the current authenticated user's profile.
    """
    return current_user


@router.patch("/me", response_model=UserRead)
async def update_me(
    user_update: UserUpdate,
    token: str = Depends(oauth2_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserRead:
    """
    Update the current authenticated user's profile.
    """
    user = await auth_service.update_user(token, user_update)
    return user


@router.get("/{provider}/signin", response_model=OAuthSignIn)
async def oauth_signin(provider: str, auth_service: AuthService = Depends(get_auth_service)) -> OAuthSignIn:
    """
    Initiate an OAuth sign-in for a given provider (e.g., google, github).
    """
    if provider not in ["google", "github"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported OAuth provider.",
        )
    oauth_data = await auth_service.signin_with_oauth(provider)
    return OAuthSignIn(**oauth_data)


@router.get("/callback", response_model=Token)
async def auth_callback(code: str, auth_service: AuthService = Depends(get_auth_service)) -> Token:
    """
    Handle the OAuth callback from the provider.
    """
    try:
        session = await auth_service.exchange_code_for_session(code)
        return session
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to exchange code for session.",
        ) from e


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    reset_password_request: ResetPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    """
    Send a password reset email.
    """
    await auth_service.reset_password(reset_password_request.email)
