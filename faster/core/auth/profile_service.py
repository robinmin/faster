# faster/core/auth/profile_service.py

from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from faster.core.auth.models import (
    Role,
    UserActivity,
    UserLink,
    UserProfile,
    UserSettings,
)


class UserProfileService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_profile(self, user_id: UUID) -> UserProfile | None:
        return await self.session.get(UserProfile, user_id)

    async def get_user_profile_by_email(self, email: str) -> UserProfile | None:
        statement = select(UserProfile).where(UserProfile.email == email)
        result = await self.session.exec(statement)
        return result.first()

    async def create_user_profile(self, email: str) -> UserProfile:
        user_profile = UserProfile(email=email)
        self.session.add(user_profile)
        await self.session.commit()
        await self.session.refresh(user_profile)
        return user_profile

    async def add_user_activity(self, user_id: UUID, action: str) -> None:
        user_activity = UserActivity(user_id=user_id, action=action)
        self.session.add(user_activity)
        await self.session.commit()

    async def get_user_activities(self, user_id: UUID) -> list[UserActivity]:
        statement = select(UserActivity).where(UserActivity.user_id == user_id)
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_user_settings(self, user_id: UUID) -> UserSettings | None:
        statement = select(UserSettings).where(UserSettings.user_id == user_id)
        result = await self.session.exec(statement)
        return result.first()

    async def get_user_id_by_provider(self, provider: str, external_id: str) -> UUID | None:
        statement = select(UserLink).where(UserLink.provider == provider, UserLink.external_id == external_id)
        result = await self.session.exec(statement)
        user_link = result.first()
        return user_link.user_id if user_link else None

    async def get_user_roles(self, user_id: UUID) -> list[Role]:
        user_profile = await self.get_user_profile(user_id)
        return user_profile.roles if user_profile else []
