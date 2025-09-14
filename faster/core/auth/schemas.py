from datetime import datetime

from sqlalchemy import Column, Index, Text, UniqueConstraint, func
from sqlmodel import Field

from ..schemas import MyBase

###############################################################################
# schemas:
#
# Use to define all database related entities only(NEVER add any business logic).
#
###############################################################################


class User(MyBase, table=True):
    """
    User table to store core user information from Supabase Auth.
    Maps to the main user object from Supabase Auth response.
    """

    __tablename__ = "AUTH_USER"
    __table_args__ = (
        UniqueConstraint("C_AUTH_ID", name="uk_auth_user_auth_id"),
        Index("idx_auth_user_email", "C_EMAIL"),
        Index("idx_auth_user_role", "C_ROLE"),
    )

    id: int | None = Field(default=None, primary_key=True, description="Primary key")
    auth_id: str = Field(max_length=64, sa_column_kwargs={"name": "C_AUTH_ID"}, description="Supabase Auth user ID")
    aud: str = Field(max_length=32, sa_column_kwargs={"name": "C_AUD"}, description="JWT audience")
    role: str = Field(max_length=32, sa_column_kwargs={"name": "C_ROLE"}, description="User role")
    email: str = Field(max_length=256, sa_column_kwargs={"name": "C_EMAIL"}, description="User email")
    email_confirmed_at: datetime | None = Field(
        default=None, sa_column_kwargs={"name": "D_EMAIL_CONFIRMED_AT"}, description="Email confirmation timestamp"
    )
    phone: str | None = Field(
        default=None, max_length=32, sa_column_kwargs={"name": "C_PHONE"}, description="User phone number"
    )
    confirmed_at: datetime | None = Field(
        default=None, sa_column_kwargs={"name": "D_CONFIRMED_AT"}, description="Account confirmation timestamp"
    )
    last_sign_in_at: datetime | None = Field(
        default=None, sa_column_kwargs={"name": "D_LAST_SIGN_IN_AT"}, description="Last sign in timestamp"
    )
    is_anonymous: bool = Field(
        default=False,
        sa_column_kwargs={"name": "B_IS_ANONYMOUS", "server_default": "0"},
        description="Anonymous user flag",
    )
    auth_created_at: datetime | None = Field(
        default=None, sa_column_kwargs={"name": "D_AUTH_CREATED_AT"}, description="Auth creation timestamp"
    )
    auth_updated_at: datetime | None = Field(
        default=None, sa_column_kwargs={"name": "D_AUTH_UPDATED_AT"}, description="Auth update timestamp"
    )


class UserMetadata(MyBase, table=True):
    """
    User metadata table to store additional user information from app_metadata and user_metadata.
    """

    __tablename__ = "AUTH_USER_METADATA"
    __table_args__ = (
        UniqueConstraint("C_USER_AUTH_ID", "C_METADATA_TYPE", "C_KEY", name="uk_user_metadata_user_type_key"),
        Index("idx_user_metadata_user_id", "C_USER_AUTH_ID"),
        Index("idx_user_metadata_type", "C_METADATA_TYPE"),
    )

    id: int | None = Field(default=None, primary_key=True, description="Primary key")
    user_auth_id: str = Field(max_length=64, sa_column_kwargs={"name": "C_USER_AUTH_ID"}, description="User auth ID")
    metadata_type: str = Field(
        max_length=32, sa_column_kwargs={"name": "C_METADATA_TYPE"}, description="Metadata type (app/user)"
    )
    key: str = Field(max_length=128, sa_column_kwargs={"name": "C_KEY"}, description="Metadata key")
    value: str | None = Field(default=None, sa_column=Column("C_VALUE", Text), description="Metadata value")


class UserIdentity(MyBase, table=True):
    """
    User identity table to store OAuth provider identity information and data.
    Maps to the identities array from Supabase Auth response.
    """

    __tablename__ = "AUTH_USER_IDENTITY"
    __table_args__ = (
        UniqueConstraint("C_IDENTITY_ID", name="uk_user_identity_identity_id"),
        UniqueConstraint("C_USER_AUTH_ID", "C_PROVIDER", name="uk_user_identity_user_provider"),
        Index("idx_user_identity_user_id", "C_USER_AUTH_ID"),
        Index("idx_user_identity_provider", "C_PROVIDER"),
    )

    id: int | None = Field(default=None, primary_key=True, description="Primary key")
    identity_id: str = Field(max_length=64, sa_column_kwargs={"name": "C_IDENTITY_ID"}, description="Identity ID")
    user_auth_id: str = Field(max_length=64, sa_column_kwargs={"name": "C_USER_AUTH_ID"}, description="User auth ID")
    provider_user_id: str = Field(
        max_length=128, sa_column_kwargs={"name": "C_PROVIDER_USER_ID"}, description="Provider user ID"
    )
    provider: str = Field(max_length=32, sa_column_kwargs={"name": "C_PROVIDER"}, description="OAuth provider")
    email: str | None = Field(
        default=None, max_length=256, sa_column_kwargs={"name": "C_EMAIL"}, description="Provider email"
    )
    last_sign_in_at: datetime | None = Field(
        default=None, sa_column_kwargs={"name": "D_LAST_SIGN_IN_AT"}, description="Last sign in timestamp"
    )
    identity_created_at: datetime | None = Field(
        default=None, sa_column_kwargs={"name": "D_IDENTITY_CREATED_AT"}, description="Identity creation timestamp"
    )
    identity_updated_at: datetime | None = Field(
        default=None, sa_column_kwargs={"name": "D_IDENTITY_UPDATED_AT"}, description="Identity update timestamp"
    )
    # Consolidated identity data as JSON
    identity_data: str | None = Field(
        default=None, sa_column=Column("C_IDENTITY_DATA", Text), description="Identity data as JSON"
    )


class UserProfile(MyBase, table=True):
    """
    User profile table to store user profile information.
    This is used to determine if a user has completed onboarding.
    """

    __tablename__ = "AUTH_USER_PROFILE"
    __table_args__ = (
        UniqueConstraint("C_USER_AUTH_ID", name="uk_user_profile_user_auth_id"),
        Index("idx_user_profile_user_auth_id", "C_USER_AUTH_ID"),
    )

    id: int | None = Field(default=None, primary_key=True, description="Primary key")
    user_auth_id: str = Field(max_length=64, sa_column_kwargs={"name": "C_USER_AUTH_ID"}, description="User auth ID")
    first_name: str | None = Field(
        default=None, max_length=128, sa_column_kwargs={"name": "C_FIRST_NAME"}, description="User first name"
    )
    last_name: str | None = Field(
        default=None, max_length=128, sa_column_kwargs={"name": "C_LAST_NAME"}, description="User last name"
    )
    display_name: str | None = Field(
        default=None, max_length=256, sa_column_kwargs={"name": "C_DISPLAY_NAME"}, description="User display name"
    )
    avatar_url: str | None = Field(
        default=None, max_length=512, sa_column_kwargs={"name": "C_AVATAR_URL"}, description="User avatar URL"
    )
    bio: str | None = Field(default=None, sa_column=Column("C_BIO", Text), description="User biography")
    location: str | None = Field(
        default=None, max_length=256, sa_column_kwargs={"name": "C_LOCATION"}, description="User location"
    )
    website: str | None = Field(
        default=None, max_length=256, sa_column_kwargs={"name": "C_WEBSITE"}, description="User website"
    )
    created_at: datetime = Field(
        default=None,
        sa_column_kwargs={
            "name": "D_CREATED_AT",
            "server_default": func.now(),
        },
        description="Profile creation timestamp",
    )
    updated_at: datetime = Field(
        default=None,
        sa_column_kwargs={
            "name": "D_UPDATED_AT",
            "server_default": func.now(),
        },
        description="Profile update timestamp",
    )


class UserRole(MyBase, table=True):
    """
    User role table to store user-role relationships.
    One user can have many roles.
    """

    __tablename__ = "AUTH_USER_ROLE"
    __table_args__ = (
        UniqueConstraint("C_USER_AUTH_ID", "C_ROLE", name="uk_user_role_user_role"),
        Index("idx_user_role_user_auth_id", "C_USER_AUTH_ID"),
        Index("idx_user_role_role", "C_ROLE"),
    )

    id: int | None = Field(default=None, primary_key=True, description="Primary key")
    user_auth_id: str = Field(max_length=64, sa_column_kwargs={"name": "C_USER_AUTH_ID"}, description="User auth ID")
    role: str = Field(max_length=32, sa_column_kwargs={"name": "C_ROLE"}, description="User role")


class UserAction(MyBase, table=True):
    """
    User action table to store all user events and behaviors for tracking and analytics.
    Initially designed for Supabase auth events, but extensible for all user interactions.
    """

    __tablename__ = "AUTH_USER_ACTION"
    __table_args__ = (
        Index("idx_user_action_user_auth_id", "C_USER_AUTH_ID"),
        Index("idx_user_action_timestamp", "D_TIMESTAMP"),
        Index("idx_user_action_event_type", "C_EVENT_TYPE"),
        Index("idx_user_action_event_name", "C_EVENT_NAME"),
        Index("idx_user_action_trace_id", "C_TRACE_ID"),
        Index("idx_user_action_session_id", "C_SESSION_ID"),
        Index("idx_user_action_source", "C_EVENT_SOURCE"),
        # Composite indexes for common queries
        Index("idx_user_action_user_time", "C_USER_AUTH_ID", "D_TIMESTAMP"),
        Index("idx_user_action_type_time", "C_EVENT_TYPE", "D_TIMESTAMP"),
    )

    id: int | None = Field(default=None, primary_key=True, description="Primary key")

    # Core identification
    user_auth_id: str | None = Field(
        default=None,
        max_length=64,
        sa_column_kwargs={"name": "C_USER_AUTH_ID"},
        description="User auth ID (null for anonymous events)",
    )
    trace_id: str | None = Field(
        default=None,
        max_length=128,
        sa_column_kwargs={"name": "C_TRACE_ID"},
        description="Trace ID for correlating related events",
    )
    session_id: str | None = Field(
        default=None,
        max_length=128,
        sa_column_kwargs={"name": "C_SESSION_ID"},
        description="Session ID for grouping user actions",
    )

    # Event categorization
    event_type: str = Field(
        max_length=32,
        sa_column_kwargs={"name": "C_EVENT_TYPE"},
        description="Event category (auth, navigation, api_call, user_action, system)",
    )
    event_name: str = Field(
        max_length=64,
        sa_column_kwargs={"name": "C_EVENT_NAME"},
        description="Specific event name (login, logout, page_view, button_click, etc.)",
    )
    event_source: str = Field(
        max_length=32,
        sa_column_kwargs={"name": "C_EVENT_SOURCE"},
        description="Event source (supabase, frontend, api, system, mobile_app)",
    )

    # Temporal information
    timestamp: datetime = Field(
        default=None,
        sa_column_kwargs={
            "name": "D_TIMESTAMP",
            "server_default": func.now(),
        },
        description="When the action occurred",
    )

    # Location and client context
    ip_address: str | None = Field(
        default=None,
        max_length=45,  # IPv6 max length
        sa_column_kwargs={"name": "C_IP_ADDRESS"},
        description="Client IP address (hashed for privacy if needed)",
    )
    user_agent: str | None = Field(
        default=None,
        max_length=512,
        sa_column_kwargs={"name": "C_USER_AGENT"},
        description="Browser/client user agent string",
    )
    client_info: str | None = Field(
        default=None,
        max_length=256,
        sa_column_kwargs={"name": "C_CLIENT_INFO"},
        description="Additional client information (device, OS, app version)",
    )
    referrer: str | None = Field(
        default=None,
        max_length=512,
        sa_column_kwargs={"name": "C_REFERRER"},
        description="HTTP referrer or previous page",
    )

    # Geographical context (optional)
    country_code: str | None = Field(
        default=None,
        max_length=2,
        sa_column_kwargs={"name": "C_COUNTRY_CODE"},
        description="ISO country code derived from IP",
    )
    city: str | None = Field(
        default=None,
        max_length=128,
        sa_column_kwargs={"name": "C_CITY"},
        description="City derived from IP geolocation",
    )
    timezone: str | None = Field(
        default=None, max_length=64, sa_column_kwargs={"name": "C_TIMEZONE"}, description="User's timezone"
    )

    # Flexible data storage
    event_payload: str | None = Field(
        default=None, sa_column=Column("C_EVENT_PAYLOAD", Text), description="Event-specific data as JSON"
    )
    extra_metadata: str | None = Field(
        default=None, sa_column=Column("C_EXTRA_METADATA", Text), description="Additional system metadata as JSON"
    )

    # Status and processing flags
    is_processed: bool = Field(
        default=False,
        sa_column_kwargs={"name": "B_IS_PROCESSED", "server_default": "0"},
        description="Whether this action has been processed by analytics pipeline",
    )
    processing_status: str | None = Field(
        default=None,
        max_length=32,
        sa_column_kwargs={"name": "C_PROCESSING_STATUS"},
        description="Processing status (pending, completed, failed, skipped)",
    )
