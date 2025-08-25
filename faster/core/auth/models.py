# region Helper Functions for Common Fields


# region Helper Functions for Common Fields


# def created_at_field() -> datetime:
#     """Returns a Field for the creation timestamp."""
#     return cast(
#         datetime,
#         Field(
#             default_factory=lambda: datetime.now(timezone.utc),
#             sa_column=Column(
#                 DateTime(timezone=True),
#                 nullable=False,
#                 default=lambda: datetime.now(timezone.utc),
#             ),
#             description="Create timestamp",
#         ),
#     )


# def updated_at_field() -> datetime | None:
#     """Returns a Field for the update timestamp."""
#     return cast(
#         datetime | None,
#         Field(
#             default=None,
#             sa_column=Column(
#                 DateTime(timezone=True),
#                 onupdate=lambda: datetime.now(timezone.utc),
#             ),
#             description="Update timestamp",
#         ),
#     )


# def deleted_at_field() -> datetime | None:
#     """Returns a Field for the soft-delete timestamp."""
#     return cast(
#         datetime | None,
#         Field(
#             default=None,
#             sa_column=Column(DateTime(timezone=True)),
#             description="Delete timestamp",
#         ),
#     )


# def in_used_field() -> bool:
#     """Returns a Field for the soft-delete flag."""
#     return cast(bool, Field(default=True, description="Soft delete flag"))


# # endregion


# class UserRoleLink(SQLModel, table=True):
#     """Junction table for the many-to-many relationship between users and roles."""

#     __tablename__ = "user_role_links"

#     user_id: uuid.UUID = Field(foreign_key="user_profiles.id", primary_key=True)
#     role_id: uuid.UUID = Field(foreign_key="roles.id", primary_key=True)

#     # Common fields
#     created_at: datetime = created_at_field()
#     updated_at: datetime | None = updated_at_field()
#     deleted_at: datetime | None = deleted_at_field()
#     in_used: bool = in_used_field()


# class Role(SQLModel, table=True):
#     """Stores user roles (e.g., admin, user)."""

#     __tablename__ = "roles"

#     id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
#     name: str = Field(unique=True, index=True)
#     description: str | None = None

#     users: list["UserProfile"] = Relationship(back_populates="roles", link_model=UserRoleLink)

#     # Common fields
#     created_at: datetime = created_at_field()
#     updated_at: datetime | None = updated_at_field()
#     deleted_at: datetime | None = deleted_at_field()
#     in_used: bool = in_used_field()


# class UserProfile(SQLModel, table=True):
#     """Stores user profile information."""

#     __tablename__ = "user_profiles"

#     id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)  # Supabase user id (UUID string from "sub")
#     # super_id: Optional[uuid.UUID] = Field(
#     #     nullable=True, description="Linking with Supabase Auth"
#     # )
#     name: str = Field(index=True)
#     email: str = Field(unique=True, index=True)
#     hashed_password: str = Field(nullable=True, description="Hashed password for the user")
#     avatar_url: str | None = Field(nullable=True, description="Avatar URL")

#     is_active: bool = Field(default=True, description="Is the user active?")
#     activated_at: datetime | None = Field(nullable=True, description="When the user was activated")

#     is_verified: bool = Field(default=False, description="Is the user verified?")
#     verified_at: datetime | None = Field(nullable=True, description="When the user was verified")

#     settings: Optional["UserSettings"] = Relationship(back_populates="user")
#     links: list["UserLink"] = Relationship(back_populates="user")
#     roles: list[Role] = Relationship(back_populates="users", link_model=UserRoleLink)
#     activities: list["UserActivity"] = Relationship(back_populates="user")

#     # Common fields
#     created_at: datetime = created_at_field()
#     updated_at: datetime | None = updated_at_field()
#     deleted_at: datetime | None = deleted_at_field()
#     in_used: bool = in_used_field()


# class UserSettings(SQLModel, table=True):
#     """Stores user-specific settings."""

#     __tablename__ = "user_settings"

#     id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
#     user_id: uuid.UUID = Field(foreign_key="user_profiles.id", unique=True)
#     theme: str = Field(default="light")
#     notifications_enabled: bool = Field(default=True)

#     user: UserProfile = Relationship(back_populates="settings")

#     # Common fields
#     created_at: datetime = created_at_field()
#     updated_at: datetime | None = updated_at_field()
#     deleted_at: datetime | None = deleted_at_field()
#     in_used: bool = in_used_field()


# class UserLink(SQLModel, table=True):
#     """Links external provider IDs to a user."""

#     __tablename__ = "user_links"

#     id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
#     user_id: uuid.UUID = Field(foreign_key="user_profiles.id")
#     provider: str = Field(index=True)
#     external_id: str = Field(unique=True, index=True)

#     user: UserProfile = Relationship(back_populates="links")

#     # Common fields
#     created_at: datetime = created_at_field()
#     updated_at: datetime | None = updated_at_field()
#     deleted_at: datetime | None = deleted_at_field()
#     in_used: bool = in_used_field()


# class UserActivity(SQLModel, table=True):
#     """Logs user activities."""

#     __tablename__ = "user_activities"

#     id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
#     user_id: uuid.UUID = Field(foreign_key="user_profiles.id")
#     action: str
#     timestamp: datetime = Field(default_factory=datetime.utcnow)

#     user: UserProfile = Relationship(back_populates="activities")

#     # Common fields
#     created_at: datetime = created_at_field()
#     updated_at: datetime | None = updated_at_field()
#     deleted_at: datetime | None = deleted_at_field()
#     in_used: bool = in_used_field()
