from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy.engine import Result

from .builders import qb, ub
from .database import DatabaseManager
from .logger import get_logger
from .schemas import SysDict, SysMap

logger = get_logger(__name__)

class AppRepository:
    """
    Repository for accessing SYS_MAP and SYS_DICT tables.
    Provides convenient methods to load data as two-layer dictionaries.
    """

    def __init__(self) -> None:
        self.db_mgr = DatabaseManager.get_instance()

    async def get_sys_map(
        self,
        category: str | None = None,
        left: str | None = None,
        right: str | None = None,
        in_used_only: bool = True,
    ) -> dict[str, dict[str, Any]]:
        """
        Load SYS_MAP as {category: {left: right}}.
        Only includes 'category', 'left', 'right' in the result.
        """
        async with self.db_mgr.get_txn(readonly=True) as session:
            # Select the entire model objects first
            query_builder = qb(SysMap)

            if category is not None:
                query_builder = query_builder.where(SysMap.category, category)
            if left is not None:
                query_builder = query_builder.where(SysMap.left_value, left)
            if right is not None:
                query_builder = query_builder.where(SysMap.right_value, right)
            if in_used_only:
                query_builder = query_builder.where(SysMap.in_used, 1)

            query_builder = query_builder.order_by(SysMap.order)
            query = query_builder.build()

            # Execute and fetch as list of model objects using scalars
            result: Result[Any] = await session.execute(query)  # pyright: ignore[reportDeprecated]
            rows: Sequence[SysMap] = result.scalars().all()

            # Build dictionary from model objects (within session context)
            data: dict[str, dict[str, Any]] = {}
            for sys_map in rows:
                if sys_map.category not in data:
                    data[sys_map.category] = {}
                data[sys_map.category][sys_map.left_value] = sys_map.right_value

        return data

    async def set_sys_map(
        self,
        category: str,
        values: dict[str, str],
    ) -> bool:
        """
        Save SYS_MAP into database.
        """
        if not values:
            return False

        try:
            async with self.db_mgr.get_txn(readonly=False) as txn:
                update_builder = ub(SysMap).where(SysMap.category, category).set(SysMap.in_used, 0)
                stmt = update_builder.build()
                _ = await txn.execute(stmt)  # pyright: ignore[reportDeprecated]

                for left, right in values.items():
                    # Update existing record or create new one
                    sys_map = await txn.get(SysMap, (category, left))
                    if sys_map:
                        sys_map.right_value = right
                        sys_map.in_used = True
                        sys_map.updated_at = datetime.now()
                    else:
                        sys_map = SysMap(
                            category=category,
                            left_value=left,
                            right_value=right,
                            order=0,
                            in_used=True,
                        )
                        txn.add(sys_map)

                # Commit the transaction
                await txn.flush()

                # Return True if successful
                return True
        except Exception as e:
            logger.error(f"Failed to update sys_map in set_sys_map: {e}")
            return False

    async def get_sys_dict(
        self,
        category: str | None = None,
        key: int | None = None,
        value: str | None = None,
        in_used_only: bool = True,
    ) -> dict[str, dict[int, Any]]:
        """
        Load SYS_DICT as {category: {key: row_dict}}.
        Only includes 'category', 'key', 'value' in row_dict.
        """
        async with self.db_mgr.get_txn(readonly=True) as session:
            # Select the entire model objects first
            query_builder = qb(SysDict)

            if category is not None:
                query_builder = query_builder.where(SysDict.category, category)
            if key is not None:
                query_builder = query_builder.where(SysDict.key, key)
            if value is not None:
                query_builder = query_builder.where(SysDict.value, value)
            if in_used_only:
                query_builder = query_builder.where(SysDict.in_used, 1)

            query_builder = query_builder.order_by(SysDict.order)
            query = query_builder.build()

            # Execute and fetch as list of model objects using scalars
            result: Result[Any] = await session.execute(query)  # pyright: ignore[reportDeprecated]
            rows: Sequence[SysDict] = result.scalars().all()

            # Build dictionary from model objects (within session context)
            data: dict[str, dict[int, str]] = {}
            for sys_dict in rows:
                if sys_dict.category not in data:
                    data[sys_dict.category] = {}
                data[sys_dict.category][sys_dict.key] = sys_dict.value

        return data

    async def set_sys_dict(
        self,
        category: str,
        values: dict[int, str],
    ) -> bool:
        """
        Set the values for a category in SYS_DICT.
        Returns True if successful.
        """
        if not values:
            return False

        try:
            async with self.db_mgr.get_txn(readonly=False) as txn:
                update_builder = ub(SysDict).where(SysDict.category, category).set(SysDict.in_used, 0)
                stmt = update_builder.build()
                _ = await txn.execute(stmt)  # pyright: ignore[reportDeprecated]

                for key, val in values.items():
                    # Update existing record or create new one
                    sys_dict = await txn.get(SysDict, (category, key))
                    if sys_dict:
                        sys_dict.right_value = val
                        sys_dict.in_used = True
                        sys_dict.updated_at = datetime.now()
                    else:
                        sys_dict = SysDict(
                            category=category,
                            key=key,
                            value=val,
                            in_used=True,
                            updated_at=datetime.now(),
                        )
                        txn.add(sys_dict)

                # Commit the transaction
                await txn.commit()

                # Return True if successful
                return True
        except Exception as e:
            logger.error(f"Failed to update sys_dict in set_sys_dict:  {e}")
            return False

    async def disable_category(self, category: str) -> int:
        """
        Set in_used=0 for all rows in SYS_MAP with the given category.
        Returns the number of rows updated.
        """
        async with self.db_mgr.get_txn(readonly=False) as txn:
            update_builder = ub(SysMap).where(SysMap.category, category).set(SysMap.in_used, 0)
            stmt = update_builder.build()

            result = await txn.execute(stmt)  # pyright: ignore[reportDeprecated]
            # For SQLAlchemy 1.4+, we can access rowcount directly
            return getattr(result, "rowcount", 0)
