from typing import Any

from jose import jwt

from faster.core.redis import tag2role_get, user2role_get


class AuthService:
    def __init__(
        self,
        jwt_secret: str,
        algorithms: list[str] | None = None,
        expiry_minutes: int = 60,
    ):
        self.jwt_secret = jwt_secret
        self.algorithms = algorithms.split(",") if isinstance(algorithms, str) else (algorithms or ["HS2G"])
        self.expiry_minutes = expiry_minutes

    # JWT Verification
    def verify_jwt(self, token: str) -> dict[str, Any]:
        """
        Verify JWT signature and return payload.
        Raises JWTError if invalid.
        """
        payload = jwt.decode(token, self.jwt_secret, algorithms=self.algorithms)
        return payload

    async def get_user_roles(self, user_id: str) -> set[str]:
        """
        Return set of roles for a given user.
        """
        if not user_id:
            return set()
        roles = await user2role_get(user_id)
        return set(roles or [])

    async def get_roles_for_tags(self, tags: list[str]) -> set[str]:
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
        user_roles = await self.get_user_roles(user_id)
        required_roles = await self.get_roles_for_tags(tags)
        # If endpoint has required roles, ensure intersection exists
        if required_roles:
            return not user_roles.isdisjoint(required_roles)
        return True  # no required roles → allow
