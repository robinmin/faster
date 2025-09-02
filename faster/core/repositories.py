from collections.abc import Sequence
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.engine import Result

from .database import DatabaseManager
from .models import SysDict, SysMap
from .utilities import qbool, qorder


class SystemRepository:
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
            query = select(SysMap)

            if category is not None:
                query = query.where(qbool(SysMap.category == category))
            if left is not None:
                query = query.where(qbool(SysMap.left_value == left))
            if right is not None:
                query = query.where(qbool(SysMap.right_value == right))
            if in_used_only:
                query = query.where(qbool(SysMap.in_used == 1))

            query = query.order_by(qorder(SysMap.order))

            # Execute and fetch as list of model objects using scalars
            result: Result[Any] = await session.execute(query)
            rows: Sequence[SysMap] = result.scalars().all()

        # Build dictionary from model objects
        data: dict[str, dict[str, Any]] = {}
        for sys_map in rows:
            if sys_map.category not in data:
                data[sys_map.category] = {}
            data[sys_map.category][sys_map.left_value] = sys_map.right_value

        return data

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
            query = select(SysDict)

            if category is not None:
                query = query.where(qbool(SysDict.category == category))
            if key is not None:
                query = query.where(qbool(SysDict.key == key))
            if value is not None:
                query = query.where(qbool(SysDict.value == value))
            if in_used_only:
                query = query.where(qbool(SysDict.in_used == 1))

            query = query.order_by(qorder(SysDict.order))

            # Execute and fetch as list of model objects using scalars
            result: Result[Any] = await session.execute(query)  # pyright: ignore[reportDeprecated]
            rows: Sequence[SysDict] = result.scalars().all()

        # Build dictionary from model objects
        data: dict[str, dict[int, str]] = {}
        for sys_dict in rows:
            if sys_dict.category not in data:
                data[sys_dict.category] = {}
            data[sys_dict.category][sys_dict.key] = sys_dict.value
        return data

    async def disable_category(self, category: str) -> int:
        """
        Set in_used=0 for all rows in SYS_MAP with the given category.
        Returns the number of rows updated.
        """
        async with self.db_mgr.get_txn(readonly=False) as txn:
            stmt = update(SysMap).where(qbool(SysMap.category == category)).values(in_used=0)

            result = await txn.execute(stmt)  # pyright: ignore[reportDeprecated]
            # For SQLAlchemy 1.4+, we can access rowcount directly
            return getattr(result, "rowcount", 0)
