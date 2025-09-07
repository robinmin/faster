from datetime import datetime

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import Field, SQLModel

###############################################################################
# schemas:
#
# Use to define all database related entities only(NEVER add any business logic).
#
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
            "server_default": "CURRENT_TIMESTAMP",
        },
        description="Creation timestamp",
    )
    updated_at: datetime = Field(
        default=None,
        sa_column_kwargs={
            "name": "D_UPDATED_AT",
            "server_default": "CURRENT_TIMESTAMP",
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
        UniqueConstraint("C_CATEGORY", "C_LEFT_VALUE", "C_RIGHT_VALUE", name="uk_sys_map_category_left_right"),
        Index("idx_sys_map_category", "C_CATEGORY"),
    )

    id: int = Field(default=None, primary_key=True)
    category: str = Field(max_length=64, sa_column_kwargs={"name": "C_CATEGORY"})
    left_value: str = Field(max_length=64, sa_column_kwargs={"name": "C_LEFT_VALUE"})
    right_value: str = Field(max_length=64, sa_column_kwargs={"name": "C_RIGHT_VALUE"})
    order: int = Field(default=0, sa_column_kwargs={"name": "N_ORDER", "server_default": "0"})


class SysDict(MyBase, table=True):
    """
    System dictionary table
    - Stores (key, value) pairs within a category.
    - Unique constraint ensures no duplicate (category, key) pairs.
    """

    __tablename__ = "SYS_DICT"
    __table_args__ = (
        UniqueConstraint("C_CATEGORY", "N_KEY", name="uk_sys_dict_category_key"),
        Index("idx_sys_dict_category", "C_CATEGORY"),
    )

    id: int = Field(default=None, primary_key=True)
    category: str = Field(max_length=64, sa_column_kwargs={"name": "C_CATEGORY"})
    key: int = Field(sa_column_kwargs={"name": "N_KEY"})
    value: str = Field(max_length=64, sa_column_kwargs={"name": "C_VALUE"})
    order: int = Field(default=0, sa_column_kwargs={"name": "N_ORDER", "server_default": "0"})
