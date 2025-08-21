"""FastAPI dependencies for the authentication module."""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel.ext.asyncio.session import AsyncSession

from faster.core.auth.exceptions import InvalidTokenError, TokenExpiredError
from faster.core.auth.schemas import UserRead
from faster.core.auth.services import AuthService
from faster.core.database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/signin")


def get_auth_service(session: AsyncSession = Depends(get_db)) -> AuthService:
    """
    Dependency to get the authentication service.

    Args:
        session: The database session.

    Returns:
        The authentication service.
    """
    return AuthService(session)


async def get_current_user(
    token: str = Depends(oauth2_scheme), auth_service: AuthService = Depends(get_auth_service)
) -> UserRead:
    """
    Dependency to get the current authenticated user.

    Args:
        token: The OAuth2 token.
        auth_service: The authentication service.

    Returns:
        The current user's data.

    Raises:
        HTTPException: If the token is invalid or expired.
    """
    try:
        user = await auth_service.get_user(token)
        if user is None:
            raise InvalidTokenError()
        return user
    except (TokenExpiredError, InvalidTokenError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
