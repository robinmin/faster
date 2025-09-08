from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

from sqlmodel import select

from .database import BaseRepository, DatabaseManager, DBSession
from .exceptions import DBError
from .logger import get_logger
from .schemas import SysDict, SysMap

###############################################################################
# AppRepository - System Configuration Data Access
#
# Provides methods to manage system configuration stored in SYS_MAP and SYS_DICT
# tables using a soft-delete pattern (in_used flag) for data consistency.
#
# SYS_MAP: Key-value mappings organized by category
#   Structure: {category: {left_value: right_value}}
#
# SYS_DICT: Integer-keyed values organized by category
#   Structure: {category: {key: value}}
###############################################################################

logger = get_logger(__name__)


class AppRepository(BaseRepository):
    """
    Repository for system configuration data access.

    Manages SYS_MAP and SYS_DICT tables that store application configuration
    as nested dictionaries. Uses soft-delete pattern (in_used flag) to maintain
    data consistency during updates.

    Inherits from BaseRepository for standard database operations and session management.
    """

    def __init__(
        self, session_factory: Callable[[], DBSession] | None = None, db_manager: DatabaseManager | None = None
    ) -> None:
        # Initialize base repository
        super().__init__(db_manager)

        # Override session factory if provided
        if session_factory is not None:
            self.configure_session_factory(session_factory)

    async def find_by_criteria(self, criteria: dict[str, Any]) -> list[Any]:
        """
        Find system configuration items by criteria (placeholder implementation).

        Args:
            criteria: Search criteria dictionary

        Returns:
            Empty list (placeholder - implement based on specific needs)
        """
        async with self.session(readonly=True) as _:
            return []

    async def get_sys_map(
        self,
        category: str | None = None,
        left: str | None = None,
        right: str | None = None,
        in_used_only: bool = True,
    ) -> dict[str, dict[str, Any]]:
        """
        Load SYS_MAP as {category: {left: right}} dictionary structure.

        Args:
            category: Filter by category name (optional)
            left: Filter by left_value (optional)
            right: Filter by right_value (optional)
            in_used_only: Only return active records (default: True)

        Returns:
            Nested dictionary: {category: {left_value: right_value}}
            Empty dict if no records found

        Raises:
            DBError: If database query fails

        Example:
            >>> repo = AppRepository()
            >>> data = await repo.get_sys_map(category="user_settings")
            >>> print(data)  # {"user_settings": {"theme": "dark", "lang": "en"}}
        """
        try:
            async with self.session(readonly=True) as session:
                # Build query with optional filters using SQLModel select
                query = select(SysMap)

                if category is not None:
                    query = query.where(SysMap.category == category)
                if left is not None:
                    query = query.where(SysMap.left_value == left)
                if right is not None:
                    query = query.where(SysMap.right_value == right)
                if in_used_only:
                    query = query.where(SysMap.in_used == 1)

                # Order by the N_ORDER column
                query = query.order_by(SysMap.order)  # type: ignore[arg-type]

                # Execute query using SQLModel exec() method
                result = await session.exec(query)
                rows: Sequence[SysMap] = result.all()

                data: dict[str, dict[str, Any]] = {}
                for sys_map in rows:
                    if sys_map.category not in data:
                        data[sys_map.category] = {}
                    data[sys_map.category][sys_map.left_value] = sys_map.right_value

                return data
        except Exception as e:
            logger.error(f"Failed to get sys_map: {e}", extra={"category": category, "left": left, "right": right})
            raise DBError(f"Failed to retrieve system map data: {e}") from e

    async def set_sys_map(self, category: str, values: dict[str, str]) -> bool:
        """
        Save/update SYS_MAP entries for a category using soft-delete pattern.

        First marks all existing entries as inactive (in_used=0), then creates/updates
        the provided entries as active (in_used=1).

        Args:
            category: Category name (required, non-empty string)
            values: Dictionary of {left_value: right_value} pairs (required, non-empty)

        Returns:
            True if successful, False otherwise

        Raises:
            ValueError: If category is empty or values is empty/None
            DBError: If database operation fails

        Example:
            >>> repo = AppRepository()
            >>> success = await repo.set_sys_map("user_settings", {"theme": "dark", "lang": "en"})
            >>> print(success)  # True
        """
        # Input validation
        if not category or not category.strip():
            raise ValueError("Category cannot be empty")
        if not values:
            raise ValueError("Values dictionary cannot be empty")

        async with self.transaction() as session:
            try:
                # Soft-delete: mark all existing entries as inactive using BaseRepository method
                _ = await self.soft_delete(self.table_name(SysMap), {"C_CATEGORY": category}, session)

                # Create/update entries with new values
                for left_value, right_value in values.items():
                    existing_map = await session.get(SysMap, (category, left_value))
                    if existing_map:
                        # Update existing record
                        existing_map.right_value = right_value
                        existing_map.in_used = True
                        existing_map.updated_at = datetime.now()
                    else:
                        # Create new record
                        new_map = SysMap(
                            category=category,
                            left_value=left_value,
                            right_value=right_value,
                            order=0,
                            in_used=True,
                        )
                        session.add(new_map)

                await session.flush()
                return True

            except Exception as e:
                logger.error(f"Failed to update sys_map for category '{category}': {e}")
                return False

    async def get_sys_dict(
        self,
        category: str | None = None,
        key: int | None = None,
        value: str | None = None,
        in_used_only: bool = True,
    ) -> dict[str, dict[int, Any]]:
        """
        Load SYS_DICT as {category: {key: value}} dictionary structure.

        Args:
            category: Filter by category name (optional)
            key: Filter by integer key (optional)
            value: Filter by string value (optional)
            in_used_only: Only return active records (default: True)

        Returns:
            Nested dictionary: {category: {key: value}}
            Empty dict if no records found

        Raises:
            DBError: If database query fails

        Example:
            >>> repo = AppRepository()
            >>> data = await repo.get_sys_dict(category="user_prefs")
            >>> print(data)  # {"user_prefs": {1: "enabled", 2: "disabled"}}
        """
        try:
            async with self.session(readonly=True) as session:
                # Build query with optional filters using SQLModel select
                query = select(SysDict)

                if category is not None:
                    query = query.where(SysDict.category == category)
                if key is not None:
                    query = query.where(SysDict.key == key)
                if value is not None:
                    query = query.where(SysDict.value == value)
                if in_used_only:
                    query = query.where(SysDict.in_used == 1)

                # Order by the N_ORDER column
                query = query.order_by(SysDict.order)  # type: ignore[arg-type]

                # Execute query using SQLModel exec() method
                result = await session.exec(query)
                rows: Sequence[SysDict] = result.all()

                data: dict[str, dict[int, str]] = {}
                for sys_dict in rows:
                    if sys_dict.category not in data:
                        data[sys_dict.category] = {}
                    data[sys_dict.category][sys_dict.key] = sys_dict.value

                return data
        except Exception as e:
            logger.error(f"Failed to get sys_dict: {e}", extra={"category": category, "key": key, "value": value})
            raise DBError(f"Failed to retrieve system dict data: {e}") from e

    async def set_sys_dict(self, category: str, values: dict[int, str]) -> bool:
        """
        Save/update SYS_DICT entries for a category using soft-delete pattern.

        First marks all existing entries as inactive (in_used=0), then creates/updates
        the provided entries as active (in_used=1).

        Args:
            category: Category name (required, non-empty string)
            values: Dictionary of {key: value} pairs where key is int, value is str

        Returns:
            True if successful, False otherwise

        Raises:
            ValueError: If category is empty or values is empty/None
            DBError: If database operation fails

        Example:
            >>> repo = AppRepository()
            >>> success = await repo.set_sys_dict("user_prefs", {1: "enabled", 2: "disabled"})
            >>> print(success)  # True
        """
        # Input validation
        if not category or not category.strip():
            raise ValueError("Category cannot be empty")
        if not values:
            raise ValueError("Values dictionary cannot be empty")

        async with self.transaction() as session:
            try:
                # Soft-delete: mark all existing entries as inactive using BaseRepository method
                _ = await self.soft_delete(self.table_name(SysDict), {"C_CATEGORY": category}, session)

                # Create/update entries with new values
                for dict_key, dict_value in values.items():
                    existing_dict = await session.get(SysDict, (category, dict_key))
                    if existing_dict:
                        # Update existing record
                        existing_dict.value = dict_value
                        existing_dict.in_used = True
                        existing_dict.updated_at = datetime.now()
                    else:
                        # Create new record
                        new_dict = SysDict(
                            category=category,
                            key=dict_key,
                            value=dict_value,
                            in_used=True,
                            updated_at=datetime.now(),
                        )
                        session.add(new_dict)

                await session.flush()
                return True

            except Exception as e:
                logger.error(f"Failed to update sys_dict for category '{category}': {e}")
                return False

    async def disable_category(self, category: str) -> int:
        """
        Disable all SYS_MAP entries for a category by setting in_used=0.

        Args:
            category: Category name to disable (required, non-empty string)

        Returns:
            Number of rows affected (0 if category not found)

        Raises:
            ValueError: If category is empty
            DBError: If database operation fails

        Example:
            >>> repo = AppRepository()
            >>> affected = await repo.disable_category("old_settings")
            >>> print(f"Disabled {affected} entries")  # "Disabled 3 entries"
        """
        # Input validation
        if not category or not category.strip():
            raise ValueError("Category cannot be empty")

        try:
            async with self.transaction() as session:
                # Mark all entries in category as inactive using BaseRepository method
                affected_rows = await self.soft_delete(self.table_name(SysMap), {"C_CATEGORY": category}, session)
                logger.info(f"Disabled {affected_rows} entries for category '{category}'")
                return affected_rows
        except Exception as e:
            logger.error(f"Failed to disable category '{category}': {e}")
            raise DBError(f"Failed to disable category '{category}': {e}") from e
