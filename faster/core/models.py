from datetime import datetime

from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.sql import func
from sqlmodel import Field, SQLModel

###############################################################################
# Summary of best practices with SQLModel + Mapped
#
# Fetch full objects : select(SysMap) + scalars() → list[SysMap]
# Fetch some columns : select(SysMap.category, SysMap.left_value) → list[tuple[str, str]]
# Defaults	mapped_column(..., default=..., server_default=...), No need for Field(sa_column=...) anymore
# Indexes / Unique constraints	Keep __table_args__ as before
# Relationships	Use Mapped[OtherModel] = relationship(...) in the new typed style
###############################################################################


class MyBase(SQLModel):
    """
    Base class for all models.

    ## Basic usage
    class User(MyBase, table=True):
        id: int = Field(primary_key=True)
        name: str

    ## Using the class
    user = User(name="John")
    print(user.is_active)  # True

    user.soft_delete()
    print(user.is_active)  # False
    print(user.is_deleted)  # True

    ## Query examples
    from sqlalchemy.orm import Session

    def get_active_users(session: Session):
        return session.query(User).filter(User.active_filter()).all()

    def get_deleted_users(session: Session):
        return session.query(User).filter(User.deleted_filter()).all()
    """

    in_used: int = Field(
        default=1,
        sa_column_kwargs={
            "name": "N_IN_USED",
            "server_default": "1",
        },
        description="1=active, 0=soft deleted",
    )
    created_at: datetime = Field(
        default=None,
        sa_column_kwargs={
            "name": "D_CREATED_AT",
            "server_default": func.now(),
        },
        description="Creation timestamp",
    )
    updated_at: datetime = Field(
        default=None,
        sa_column_kwargs={
            "name": "D_UPDATED_AT",
            "server_default": func.now(),
            "onupdate": func.now(),
        },
        description="Last update timestamp",
    )
    deleted_at: datetime | None = Field(
        default=None,
        sa_column_kwargs={
            "name": "D_DELETED_AT",
        },
        description="Soft deleting timestamp",
    )

    # Instance methods
    def soft_delete(self) -> None:
        """Soft delete the record by setting in_used=0 and recording timestamp."""
        self.in_used = 0
        self.deleted_at = datetime.now()

    def restore(self) -> None:
        """Restore soft deleted record by setting in_used=1."""
        self.in_used = 1
        self.deleted_at = None

    @property
    def is_active(self) -> bool:
        """Check if record is active (in_used=1)."""
        return self.in_used == 1

    @property
    def is_deleted(self) -> bool:
        """Check if record is soft deleted (in_used=0)."""
        return self.in_used == 0

    # Class methods for common query filters
    @classmethod
    def active_filter(cls) -> bool:
        """Filter for active records (in_used=1)."""
        return cls.in_used == 1

    @classmethod
    def deleted_filter(cls) -> bool:
        """Filter for soft deleted records (in_used=0)."""
        return cls.in_used == 0


###############################################################################


class SysMap(MyBase, table=True):
    """
    System mapping table
    - Maps C_LEFT to C_RIGHT within a category.
    - Unique constraint ensures no duplicate triplets.
    """

    __tablename__ = "SYS_MAP"
    __table_args__ = (
        UniqueConstraint("category", "left_value", "right_value", name="uk_sys_map_category_left_right"),
        Index("idx_sys_map_category", "category"),
    )

    id: int = Field(default=None, primary_key=True)
    category: str = Field(max_length=64)
    left_value: str = Field(max_length=64)
    right_value: str = Field(max_length=64)
    order: int = Field(default=0, sa_column_kwargs={"server_default": "0"})


class SysDict(MyBase, table=True):
    """
    System dictionary table
    - Stores (key, value) pairs within a category.
    - Unique constraint ensures no duplicate (category, key) pairs.
    """

    __tablename__ = "SYS_DICT"
    __table_args__ = (
        UniqueConstraint("category", "key", name="uk_sys_dict_category_key"),
        Index("idx_sys_dict_category", "category"),
    )

    id: int = Field(default=None, primary_key=True)
    category: str = Field(max_length=64)
    key: int = Field()
    value: str = Field(max_length=64)
    order: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
