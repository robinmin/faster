# mypy: ignore-errors
"""
This module contains the business logic for authentication and user management.
It interacts with the Supabase client to perform auth-related operations.
"""

from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession
from supabase import Client
from supabase_auth.errors import AuthApiError

from faster.core.auth.client import get_auth
from faster.core.auth.exceptions import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from faster.core.auth.profile_service import UserProfileService
from faster.core.auth.schemas import Token, UserCreate, UserRead, UserSignIn, UserUpdate


class AuthService:
    """
    Service class for handling authentication logic.
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initializes the AuthService with a Supabase auth client.
        """
        self.auth: Client = get_auth()
        self.profile_service = UserProfileService(session)

    async def signup(self, user_create: UserCreate) -> UserRead:
        """
        Registers a new user.

        Args:
            user_create: A Pydantic model containing the new user's details.

        Returns:
            The newly created user's information.

        Raises:
            UserAlreadyExistsError: If the user already exists.
        """
        try:
            response = self.auth.auth.sign_up(
                {
                    "email": user_create.email,
                    "password": user_create.password,
                }
            )
            if response.user is None:
                raise UserNotFoundError()

            user = UserRead(**response.user.model_dump())
            user_profile = await self.profile_service.create_user_profile(user.email)
            await self.profile_service.add_user_activity(user_profile.id, "signup")
            return user
        except AuthApiError as e:
            if "User already registered" in e.message:
                raise UserAlreadyExistsError() from e
            raise

    async def signin(self, user_signin: UserSignIn) -> Token:
        """
        Authenticates a user.

        Args:
            user_signin: A Pydantic model containing the user's credentials.

        Returns:
            The user's session information upon successful authentication.

        Raises:
            InvalidCredentialsError: If the credentials are invalid.
        """
        try:
            response = self.auth.auth.sign_in_with_password(
                {
                    "email": user_signin.email,
                    "password": user_signin.password,
                }
            )
            user_profile = await self.profile_service.get_user_profile_by_email(user_signin.email)
            if user_profile:
                await self.profile_service.add_user_activity(user_profile.id, "signin")

            if response.session is None:
                raise InvalidCredentialsError()
            return Token(**response.session.dict())
        except AuthApiError as e:
            raise InvalidCredentialsError() from e

    async def signout(self, access_token: str) -> None:
        """
        Signs out a user.

        Args:
            access_token: The user's JWT access token.
        """
        user = await self.get_user(access_token)
        if user:
            user_profile = await self.profile_service.get_user_profile_by_email(user.email)
            if user_profile:
                await self.profile_service.add_user_activity(user_profile.id, "signout")
        self.auth.auth.sign_out()

    async def get_user(self, access_token: str) -> UserRead | None:
        """
        Retrieves a user's information based on the access token.

        Args:
            access_token: The user's JWT access token.

        Returns:
            The user's information.
        """
        response = self.auth.auth.get_user(access_token)
        if response.user:
            return UserRead(**response.user.dict())
        return None

    async def update_user(self, access_token: str, user_update: UserUpdate) -> UserRead:
        """
        Updates a user's profile.

        Args:
            access_token: The user's JWT access token.
            user_update: A Pydantic model with the updated user details.

        Returns:
            The updated user's information.
        """
        update_data = user_update.model_dump(exclude_unset=True)
        response = self.auth.auth.update_user(update_data)  # type: ignore
        return UserRead(**response.user.dict())

    async def signin_with_oauth(self, provider: str) -> dict[str, Any]:
        """
        Initiates an OAuth sign-in process.

        Args:
            provider: The OAuth provider (e.g., 'google', 'github').

        Returns:
            A dictionary containing the provider and the authorization URL.
        """
        response = self.auth.auth.sign_in_with_oauth(provider)  # type: ignore
        return {"url": response.url}

    async def exchange_code_for_session(self, code: str) -> Token:
        """
        Exchanges an authorization code for a user session.

        Args:
            code: The authorization code provided by the OAuth provider.

        Returns:
            The user's session information.
        """
        response = self.auth.auth.exchange_code_for_session({"auth_code": code})  # type: ignore
        if response.user is None:
            raise UserNotFoundError()
        user = UserRead(**response.user.dict())
        user_profile = await self.profile_service.get_user_profile_by_email(user.email)
        if not user_profile:
            user_profile = await self.profile_service.create_user_profile(user.email)
        await self.profile_service.add_user_activity(user_profile.id, "oauth_signin")

        if response.session is None:
            raise InvalidCredentialsError()
        return Token(**response.session.dict())

    async def magic_login(self, email: str, token: str) -> Token:
        """
        Authenticates a user using a magic link token.

        Args:
            email: The user's email address.
            token: The magic link token received via email.

        Returns:
            The user's session information upon successful authentication.

        Raises:
            InvalidCredentialsError: If the email or token is invalid.
        """
        try:
            response = self.auth.auth.verify_otp({"email": email, "token": token, "type": "magiclink"})
            if response.session is None:
                raise InvalidCredentialsError()
            return Token(**response.session.dict())
        except AuthApiError as e:
            raise InvalidCredentialsError() from e

    async def reset_password(self, email: str) -> None:
        """
        Sends a password reset email to the user.

        Args:
            email: The user's email address.
        """
        user_profile = await self.profile_service.get_user_profile_by_email(email)
        if user_profile:
            await self.profile_service.add_user_activity(user_profile.id, "reset_password")
        self.auth.auth.reset_password_email(email)
