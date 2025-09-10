from ..database import get_transaction
from ..logger import get_logger
from ..redisex import blacklist_add, blacklist_delete, tag2role_get, user2role_get
from .auth_proxy import AuthProxy
from .models import UserProfileData
from .repositories import AuthRepository
from .schemas import User

logger = get_logger(__name__)


class AuthService:
    def __init__(
        self,
        jwt_secret: str,
        algorithms: list[str] | None = None,
        expiry_minutes: int = 60,
        supabase_url: str = "",
        supabase_anon_key: str = "",
        supabase_service_key: str = "",
        supabase_jwks_url: str = "",
        # supabase_client_id: str = "",
        supabase_audience: str = "",
        auto_refresh_jwks: bool = True,
    ):
        self._jwt_secret = jwt_secret
        self._algorithms = algorithms.split(",") if isinstance(algorithms, str) else (algorithms or ["HS2G"])
        self._expiry_minutes = expiry_minutes

        self._supabase_url = supabase_url
        self._supabase_anon_key = supabase_anon_key
        self._supabase_service_key = supabase_service_key
        self._supabase_jwks_url = supabase_jwks_url
        # self._supabase_client_id = supabase_client_id
        self._supabase_audience = supabase_audience
        self._auto_refresh_jwks = auto_refresh_jwks

        self._auth_client = AuthProxy(
            supabase_url=self._supabase_url,
            supabase_anon_key=self._supabase_anon_key,
            supabase_service_key=self._supabase_service_key,
            supabase_jwks_url=self._supabase_jwks_url,
            # supabase_client_id=self._supabase_client_id,
            supabase_audience=self._supabase_audience,
            cache_ttl=self._expiry_minutes * 60,
            auto_refresh_jwks=self._auto_refresh_jwks,
        )

        self._repository = AuthRepository()

    async def process_user_login(self, token: str | None, user_profile: UserProfileData) -> User:
        """
        Process user login by:
        1. Validating JWT token
        2. Removing token from blacklist if it exists
        3. Saving/updating user profile in database
        4. Returning database user record
        """
        logger.info(f"Processing login for user: {user_profile.id}")

        # Remove token from blacklist (if it exists)
        if token and not await blacklist_delete(token):
            logger.warning(f"Failed to remove token {token} from blacklist")

        # Save user profile to database
        try:
            user = await self._save_user_profile_to_database(user_profile)
            logger.info(f"Saved user profile to database: {user.auth_id}")
            return user
        except Exception as e:
            logger.error(f"Failed to save user profile to database: {e}")
            raise

    async def process_user_logout(self, token: str | None, user_profile: UserProfileData) -> None:
        """
        Logout user by adding their token to blacklist.
        Note: This would require the actual JWT token to blacklist it properly.
        For now, we'll implement basic logout logic.
        """

        # Add token into blacklist
        if token and not await blacklist_add(token):
            logger.warning(f"Failed to add token {token} into blacklist")

        user_id = user_profile.id
        try:
            # TODO: Implement proper token blacklisting
            # This would require accessing the actual JWT token
            logger.info(f"Logging out user: {user_id}")
        except Exception as e:
            logger.error(f"Failed to logout user {user_id}: {e}")
            raise

    async def get_roles_by_user_id(self, user_id: str) -> set[str]:
        """
        Return set of roles for a given user.
        """
        if not user_id:
            return set()
        roles = await user2role_get(user_id)
        return set(roles or [])

    async def get_roles_by_tags(self, tags: list[str]) -> set[str]:
        """
        Return set of roles for a given list of tags.
        """
        if not tags:
            return set()

        required: set[str] = set()
        for t in tags:
            r = await tag2role_get(t)
            required |= set(r or [])
        return required

    async def check_access(self, user_id: str, tags: list[str]) -> bool:
        """Check if user has access to a given list of tags."""
        user_roles = await self.get_roles_by_user_id(user_id)
        required_roles = await self.get_roles_by_tags(tags)

        # If endpoint has required roles, ensure intersection exists
        if required_roles:
            return not user_roles.isdisjoint(required_roles)
        return False  # no required roles → deny access

    async def _save_user_profile_to_database(self, user_profile: UserProfileData) -> User:
        """Save complete user profile to database."""
        async with await get_transaction() as session:
            # Create or update user
            user_data = {
                "id": user_profile.id,
                "aud": user_profile.aud,
                "role": user_profile.role,
                "email": user_profile.email,
                "email_confirmed_at": user_profile.email_confirmed_at,
                "phone": user_profile.phone,
                "confirmed_at": user_profile.confirmed_at,
                "last_sign_in_at": user_profile.last_sign_in_at,
                "is_anonymous": user_profile.is_anonymous,
                "created_at": user_profile.created_at,
                "updated_at": user_profile.updated_at,
            }
            user = await self._repository.create_or_update_user(session, user_data)

            # Save metadata
            if user_profile.app_metadata:
                await self._repository.create_or_update_user_metadata(
                    session, user_profile.id, "app", user_profile.app_metadata
                )
            if user_profile.user_metadata:
                await self._repository.create_or_update_user_metadata(
                    session, user_profile.id, "user", user_profile.user_metadata
                )

            # Identities are now handled as part of simplified UserProfileData model

            return user

    ###########################################################################
    # Proxy to enable external can call some methods defined in _auth_client
    ###########################################################################
    async def get_user_id_from_token(self, token: str) -> str | None:
        """Get user ID from JWT token."""
        return await self._auth_client.get_user_id_from_token(token)

    async def get_user_by_id(self, user_id: str, from_cache: bool = True) -> UserProfileData | None:
        """Get user profile data by user ID."""
        return await self._auth_client.get_user_by_id(user_id, from_cache)

    async def get_user_by_token(self, token: str) -> UserProfileData | None:
        """Authenticate JWT token and return user profile data."""
        return await self._auth_client.get_user_by_token(token)

    ###########################################################################
    # Proxy to enable external can call some methods defined in _repository
    ###########################################################################
    async def check_user_onboarding_complete(self, user_id: str) -> bool:
        """
        Check if a user has completed onboarding by checking if they have a profile.
        """
        return await self._repository.check_user_profile_exists(user_id)

    async def get_user_by_auth_id(self, auth_id: str) -> User | None:
        """Get user from database by Supabase auth ID."""
        async with await get_transaction(readonly=True) as session:
            return await self._repository.get_user_by_auth_id(session, auth_id)
