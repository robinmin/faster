from typing import Any

from jose import jwt
from supabase_auth.types import User as UserProfile

from faster.core.redisex import tag2role_get, user2role_get

from .auth_proxy import AuthProxy


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

    async def authenticate_token(self, token: str) -> UserProfile:
        return await self._auth_client.authenticate_token(token)

    # JWT Verification  # TODO: check not used?
    def verify_jwt(self, token: str) -> dict[str, Any]:
        """
        Verify JWT signature and return payload.
        Raises JWTError if invalid.
        """
        payload = jwt.decode(token, self._jwt_secret, algorithms=self._algorithms)
        return payload

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

        required = set()
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
