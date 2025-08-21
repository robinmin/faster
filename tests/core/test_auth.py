# tests/core/test_auth.py

"""Unit tests for the authentication module."""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException, status
import pytest
from supabase_auth.errors import AuthApiError

from faster.core.auth.client import get_auth, get_supabase_client
from faster.core.auth.dependencies import get_current_user
from faster.core.auth.exceptions import (
    InvalidCredentialsError,
    InvalidTokenError,
    TokenExpiredError,
    UserAlreadyExistsError,
)
from faster.core.auth.routers import (
    auth_callback,
    get_me,
    magic_login,
    oauth_signin,
    reset_password,
    signin,
    signout,
    signup,
    update_me,
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

# region Fixtures


@pytest.fixture
def mock_auth_service():
    """Fixture for a mocked AuthService."""
    return MagicMock(spec=AuthService)


@pytest.fixture
def user_create_data():
    """Fixture for user creation data."""
    return UserCreate(email="test@example.com", password="password123")


@pytest.fixture
def user_signin_data():
    """Fixture for user sign-in data."""
    return UserSignIn(email="test@example.com", password="password123")


@pytest.fixture
def magic_login_data():
    """Fixture for magic login data."""
    return MagicLoginRequest(email="test@example.com", token="magictoken")


@pytest.fixture
def user_update_data():
    """Fixture for user update data."""
    return UserUpdate(password="newpassword123")


@pytest.fixture
def token_data():
    """Fixture for token data."""
    return Token(access_token="access_token", refresh_token="refresh_token")


@pytest.fixture
def user_read_data():
    """Fixture for user read data."""
    return UserRead(id="user_id", email="test@example.com")


# endregion

# region Test Client


@patch("faster.core.auth.client.create_client")
def test_get_supabase_client_success(mock_create_client, monkeypatch):
    """Test get_supabase_client success."""
    # Arrange
    monkeypatch.setattr("faster.core.config.default_settings.supabase_url", "http://test.com")
    monkeypatch.setattr("faster.core.config.default_settings.supabase_anon_key", "test_key")
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client

    # Act
    client = get_supabase_client()

    # Assert
    assert client == mock_client
    mock_create_client.assert_called_once()


def test_get_supabase_client_missing_config(monkeypatch):
    """Test get_supabase_client with missing config."""
    # Arrange
    monkeypatch.setattr("faster.core.config.default_settings.supabase_url", None)
    get_supabase_client.cache_clear()

    # Act & Assert
    with pytest.raises(ValueError, match="Supabase URL and anonymous key must be configured."):
        get_supabase_client()


@patch("faster.core.auth.client.get_supabase_client")
def test_get_auth(mock_get_supabase_client):
    """Test get_auth."""
    # Arrange
    mock_client = MagicMock()
    mock_get_supabase_client.return_value = mock_client

    # Act
    auth_client = get_auth()

    # Assert
    assert auth_client == mock_client
    mock_get_supabase_client.assert_called_once()


# endregion

# region Test Dependencies


@pytest.mark.asyncio
async def test_get_current_user_success(mock_auth_service):
    """Test get_current_user success."""
    # Arrange
    mock_auth_service.get_user.return_value = "test_user"

    # Act
    user = await get_current_user(token="test_token", auth_service=mock_auth_service)

    # Assert
    assert user == "test_user"
    mock_auth_service.get_user.assert_called_once_with("test_token")


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [TokenExpiredError, InvalidTokenError])
async def test_get_current_user_token_error(mock_auth_service, error):
    """Test get_current_user with token errors."""
    # Arrange
    mock_auth_service.get_user.side_effect = error

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token="test_token", auth_service=mock_auth_service)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


# endregion

# region Test Routers


@pytest.mark.asyncio
async def test_signup_success(mock_auth_service, user_create_data, user_read_data):
    """Test signup success."""
    # Arrange
    mock_auth_service.signup.return_value = user_read_data

    # Act
    result = await signup(user_create_data, mock_auth_service)

    # Assert
    assert result == user_read_data
    mock_auth_service.signup.assert_called_once_with(user_create_data)


@pytest.mark.asyncio
async def test_signup_user_exists(mock_auth_service, user_create_data):
    """Test signup with existing user."""
    # Arrange
    mock_auth_service.signup.side_effect = UserAlreadyExistsError

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await signup(user_create_data, mock_auth_service)
    assert exc_info.value.status_code == status.HTTP_409_CONFLICT


@pytest.mark.asyncio
async def test_signin_success(mock_auth_service, user_signin_data, token_data):
    """Test signin success."""
    # Arrange
    mock_auth_service.signin.return_value = token_data

    # Act
    result = await signin(user_signin_data, mock_auth_service)

    # Assert
    assert result == token_data
    mock_auth_service.signin.assert_called_once_with(user_signin_data)


@pytest.mark.asyncio
async def test_signin_invalid_credentials(mock_auth_service, user_signin_data):
    """Test signin with invalid credentials."""
    # Arrange
    mock_auth_service.signin.side_effect = InvalidCredentialsError

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await signin(user_signin_data, mock_auth_service)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_magic_login_success(mock_auth_service, magic_login_data, token_data):
    """Test magic_login success."""
    # Arrange
    mock_auth_service.magic_login.return_value = token_data

    # Act
    result = await magic_login(magic_login_data, mock_auth_service)

    # Assert
    assert result == token_data
    mock_auth_service.magic_login.assert_called_once_with(magic_login_data.email, magic_login_data.token)


@pytest.mark.asyncio
async def test_magic_login_invalid_credentials(mock_auth_service, magic_login_data):
    """Test magic_login with invalid credentials."""
    # Arrange
    mock_auth_service.magic_login.side_effect = InvalidCredentialsError

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await magic_login(magic_login_data, mock_auth_service)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_signout_success(mock_auth_service):
    """Test signout success."""
    # Act
    await signout("test_token", mock_auth_service)

    # Assert
    mock_auth_service.signout.assert_called_once_with("test_token")


@pytest.mark.asyncio
async def test_get_me(user_read_data):
    """Test get_me."""
    # Act
    result = await get_me(user_read_data)

    # Assert
    assert result == user_read_data


@pytest.mark.asyncio
async def test_update_me_success(mock_auth_service, user_update_data, user_read_data):
    """Test update_me success."""
    # Arrange
    mock_auth_service.update_user.return_value = user_read_data

    # Act
    result = await update_me(user_update_data, "test_token", mock_auth_service)

    # Assert
    assert result == user_read_data
    mock_auth_service.update_user.assert_called_once_with("test_token", user_update_data)


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["google", "github"])
async def test_oauth_signin_success(mock_auth_service, provider):
    """Test oauth_signin success."""
    # Arrange
    oauth_data = {"provider": provider, "url": "http://oauth.url"}
    mock_auth_service.signin_with_oauth.return_value = oauth_data

    # Act
    result = await oauth_signin(provider, mock_auth_service)

    # Assert
    assert isinstance(result, OAuthSignIn)
    assert result.provider == provider
    assert result.url == "http://oauth.url"
    mock_auth_service.signin_with_oauth.assert_called_once_with(provider)


@pytest.mark.asyncio
async def test_oauth_signin_unsupported_provider(mock_auth_service):
    """Test oauth_signin with unsupported provider."""
    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await oauth_signin("facebook", mock_auth_service)
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_auth_callback_success(mock_auth_service, token_data):
    """Test auth_callback success."""
    # Arrange
    mock_auth_service.exchange_code_for_session.return_value = token_data

    # Act
    result = await auth_callback("auth_code", mock_auth_service)

    # Assert
    assert result == token_data
    mock_auth_service.exchange_code_for_session.assert_called_once_with("auth_code")


@pytest.mark.asyncio
async def test_auth_callback_failure(mock_auth_service):
    """Test auth_callback failure."""
    # Arrange
    mock_auth_service.exchange_code_for_session.side_effect = Exception

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await auth_callback("auth_code", mock_auth_service)
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_reset_password_success(mock_auth_service):
    """Test reset_password success."""
    # Arrange
    reset_password_request = ResetPasswordRequest(email="test@example.com")

    # Act
    await reset_password(reset_password_request, mock_auth_service)

    # Assert
    mock_auth_service.reset_password.assert_called_once_with("test@example.com")


# endregion

# region Test Services


@patch("faster.core.auth.services.get_auth")
@pytest.mark.asyncio
async def test_auth_service_signup_success(mock_get_auth, user_create_data):
    """Test AuthService signup success."""
    # Arrange
    mock_auth_client = MagicMock()
    mock_get_auth.return_value = mock_auth_client
    mock_response = MagicMock()
    mock_response.user.model_dump.return_value = {"id": "user_id", "email": user_create_data.email}
    mock_auth_client.auth.sign_up.return_value = mock_response
    service = AuthService(session=AsyncMock())
    mock_user_profile = MagicMock()
    mock_user_profile.id = "user_id"
    service.profile_service.create_user_profile = AsyncMock(return_value=mock_user_profile)
    service.profile_service.add_user_activity = AsyncMock()

    # Act
    result = await service.signup(user_create_data)

    # Assert
    assert isinstance(result, UserRead)
    assert result.email == user_create_data.email
    mock_auth_client.auth.sign_up.assert_called_once()
    service.profile_service.create_user_profile.assert_awaited_once_with(user_create_data.email)
    service.profile_service.add_user_activity.assert_awaited_once_with("user_id", "signup")


@patch("faster.core.auth.services.get_auth")
@pytest.mark.asyncio
async def test_auth_service_signup_user_exists(mock_get_auth, user_create_data):
    """Test AuthService signup with existing user."""
    # Arrange
    mock_auth_client = MagicMock()
    mock_get_auth.return_value = mock_auth_client
    mock_auth_client.auth.sign_up.side_effect = AuthApiError("User already registered", status=400, code="bad_request")
    service = AuthService(session=AsyncMock())

    # Act & Assert
    with pytest.raises(UserAlreadyExistsError):
        await service.signup(user_create_data)


@patch("faster.core.auth.services.get_auth")
@pytest.mark.asyncio
async def test_auth_service_signin_success(mock_get_auth, user_signin_data):
    """Test AuthService signin success."""
    # Arrange
    mock_auth_client = MagicMock()
    mock_get_auth.return_value = mock_auth_client
    mock_response = MagicMock()
    mock_response.session.dict.return_value = {"access_token": "access_token", "refresh_token": "refresh_token"}
    mock_auth_client.auth.sign_in_with_password.return_value = mock_response
    service = AuthService(session=AsyncMock())
    mock_user_profile = MagicMock()
    mock_user_profile.id = "user_id"
    service.profile_service.get_user_profile_by_email = AsyncMock(return_value=mock_user_profile)
    service.profile_service.add_user_activity = AsyncMock()

    # Act
    result = await service.signin(user_signin_data)

    # Assert
    assert isinstance(result, Token)
    assert result.access_token == "access_token"
    mock_auth_client.auth.sign_in_with_password.assert_called_once()
    service.profile_service.get_user_profile_by_email.assert_awaited_once_with(user_signin_data.email)
    service.profile_service.add_user_activity.assert_awaited_once_with("user_id", "signin")


@patch("faster.core.auth.services.get_auth")
@pytest.mark.asyncio
async def test_auth_service_signin_invalid_credentials(mock_get_auth, user_signin_data):
    """Test AuthService signin with invalid credentials."""
    # Arrange
    mock_auth_client = MagicMock()
    mock_get_auth.return_value = mock_auth_client
    mock_auth_client.auth.sign_in_with_password.side_effect = AuthApiError(
        "Invalid credentials", status=400, code="bad_request"
    )
    service = AuthService(session=AsyncMock())

    # Act & Assert
    with pytest.raises(InvalidCredentialsError):
        await service.signin(user_signin_data)


@patch("faster.core.auth.services.get_auth")
@pytest.mark.asyncio
async def test_auth_service_signout(mock_get_auth):
    """Test AuthService signout."""
    # Arrange
    mock_auth_client = MagicMock()
    mock_get_auth.return_value = mock_auth_client
    service = AuthService(session=AsyncMock())
    mock_user_profile = MagicMock()
    mock_user_profile.id = "user_id"
    service.profile_service.get_user_profile_by_email = AsyncMock(return_value=mock_user_profile)
    service.profile_service.add_user_activity = AsyncMock()

    # Patch the get_user method to avoid nested errors
    with patch.object(service, "get_user", return_value=UserRead(id="user_id", email="test@example.com")):
        # Act
        await service.signout("access_token")

    # Assert
    mock_auth_client.auth.sign_out.assert_called_once()
    service.profile_service.get_user_profile_by_email.assert_awaited_once_with("test@example.com")
    service.profile_service.add_user_activity.assert_awaited_once_with("user_id", "signout")


@patch("faster.core.auth.services.get_auth")
@pytest.mark.asyncio
async def test_auth_service_get_user(mock_get_auth):
    """Test AuthService get_user."""
    # Arrange
    mock_auth_client = MagicMock()
    mock_get_auth.return_value = mock_auth_client
    mock_response = MagicMock()
    mock_response.user.dict.return_value = {"id": "user_id", "email": "test@example.com"}
    mock_auth_client.auth.get_user.return_value = mock_response
    service = AuthService(session=AsyncMock())

    # Act
    result = await service.get_user("access_token")

    # Assert
    assert isinstance(result, UserRead)
    assert result.id == "user_id"
    mock_auth_client.auth.get_user.assert_called_once_with("access_token")


@patch("faster.core.auth.services.get_auth")
@pytest.mark.asyncio
async def test_auth_service_update_user(mock_get_auth, user_update_data):
    """Test AuthService update_user."""
    # Arrange
    mock_auth_client = MagicMock()
    mock_get_auth.return_value = mock_auth_client
    mock_response = MagicMock()
    mock_response.user.dict.return_value = {"id": "user_id", "email": "test@example.com"}
    mock_auth_client.auth.update_user.return_value = mock_response
    service = AuthService(session=AsyncMock())

    # Act
    result = await service.update_user("access_token", user_update_data)

    # Assert
    assert isinstance(result, UserRead)
    mock_auth_client.auth.update_user.assert_called_once()


@patch("faster.core.auth.services.get_auth")
@pytest.mark.asyncio
async def test_auth_service_signin_with_oauth(mock_get_auth):
    """Test AuthService signin_with_oauth."""
    # Arrange
    mock_auth_client = MagicMock()
    mock_get_auth.return_value = mock_auth_client
    mock_oauth_response = MagicMock()
    mock_oauth_response.url = "http://oauth.url"
    mock_auth_client.auth.sign_in_with_oauth.return_value = mock_oauth_response
    service = AuthService(session=AsyncMock())

    # Act
    result = await service.signin_with_oauth("google")

    # Assert
    assert result["url"] == "http://oauth.url"
    mock_auth_client.auth.sign_in_with_oauth.assert_called_once_with("google")


@patch("faster.core.auth.services.get_auth")
@pytest.mark.asyncio
async def test_auth_service_exchange_code_for_session(mock_get_auth):
    """Test AuthService exchange_code_for_session."""
    # Arrange
    mock_auth_client = MagicMock()
    mock_get_auth.return_value = mock_auth_client
    mock_response = MagicMock()
    mock_response.session.dict.return_value = {"access_token": "access_token", "refresh_token": "refresh_token"}
    mock_response.user.dict.return_value = {"id": "user_id", "email": "test@example.com"}
    mock_auth_client.auth.exchange_code_for_session.return_value = mock_response
    service = AuthService(session=AsyncMock())
    mock_user_profile = MagicMock()
    mock_user_profile.id = "user_id"
    service.profile_service.get_user_profile_by_email = AsyncMock(return_value=None)  # Simulate user not existing
    service.profile_service.create_user_profile = AsyncMock(return_value=mock_user_profile)
    service.profile_service.add_user_activity = AsyncMock()

    # Act
    result = await service.exchange_code_for_session("auth_code")

    # Assert
    assert isinstance(result, Token)
    mock_auth_client.auth.exchange_code_for_session.assert_called_once_with({"auth_code": "auth_code"})
    service.profile_service.create_user_profile.assert_awaited_once()
    service.profile_service.add_user_activity.assert_awaited_once_with("user_id", "oauth_signin")


@patch("faster.core.auth.services.get_auth")
@pytest.mark.asyncio
async def test_auth_service_magic_login_success(mock_get_auth):
    """Test AuthService magic_login success."""
    # Arrange
    mock_auth_client = MagicMock()
    mock_get_auth.return_value = mock_auth_client
    mock_response = MagicMock()
    mock_response.session.dict.return_value = {"access_token": "access_token", "refresh_token": "refresh_token"}
    mock_auth_client.auth.verify_otp.return_value = mock_response
    service = AuthService(session=AsyncMock())

    # Act
    result = await service.magic_login("test@example.com", "magic_token")

    # Assert
    assert isinstance(result, Token)
    mock_auth_client.auth.verify_otp.assert_called_once_with(
        {"email": "test@example.com", "token": "magic_token", "type": "magiclink"}
    )


@patch("faster.core.auth.services.get_auth")
@pytest.mark.asyncio
async def test_auth_service_magic_login_invalid_credentials(mock_get_auth):
    """Test AuthService magic_login with invalid credentials."""
    # Arrange
    mock_auth_client = MagicMock()
    mock_get_auth.return_value = mock_auth_client
    mock_auth_client.auth.verify_otp.side_effect = AuthApiError("Invalid token", status=400, code="bad_request")
    service = AuthService(session=AsyncMock())

    # Act & Assert
    with pytest.raises(InvalidCredentialsError):
        await service.magic_login("test@example.com", "invalid_token")


@patch("faster.core.auth.services.get_auth")
@pytest.mark.asyncio
async def test_auth_service_reset_password(mock_get_auth):
    """Test AuthService reset_password."""
    # Arrange
    mock_auth_client = MagicMock()
    mock_get_auth.return_value = mock_auth_client
    service = AuthService(session=AsyncMock())
    mock_user_profile = MagicMock()
    mock_user_profile.id = "user_id"
    service.profile_service.get_user_profile_by_email = AsyncMock(return_value=mock_user_profile)
    service.profile_service.add_user_activity = AsyncMock()

    # Act
    await service.reset_password("test@example.com")

    # Assert
    mock_auth_client.auth.reset_password_email.assert_called_once_with("test@example.com")
    service.profile_service.get_user_profile_by_email.assert_awaited_once_with("test@example.com")
    service.profile_service.add_user_activity.assert_awaited_once_with("user_id", "reset_password")


# endregion
