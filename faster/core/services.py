from typing import Any

from .logger import get_logger
from .redisex import sysdict_set, sysmap_set
from .repositories import AppRepository

logger = get_logger(__name__)


class SysService:
    def __init__(self) -> None:
        self._repository = AppRepository()

    async def get_sys_info(self) -> bool:
        """Get all system information from database into redis."""
        result = True

        # load all sys_dict information and cache into redis
        dict_items = await self._repository.get_sys_dict()
        if dict_items:
            # await sysdict_set(dict_items)
            for cat1, items1 in dict_items.items():
                if not await sysdict_set(cat1, items1):
                    logger.error(f"Failed to set sys_dict for category {cat1}")
                    result = False
                    break

        # load all sys_map information and cache into redis
        map_items = await self._repository.get_sys_map()
        if map_items:
            for cat2, items2 in map_items.items():
                if not await sysmap_set(cat2, items2):
                    logger.error(f"Failed to set sys_map for category {cat2}")
                    result = False
                    break

        return result

    async def _set_sys_dict_info(self, sys_dict: dict[str, dict[int, Any]], to_cache: bool) -> bool:
        """Set sys_dict information to database and redis."""
        for cat1, items1 in sys_dict.items():
            if len(items1) == 0:
                continue

            # set sys_dict into database
            if not await self._repository.set_sys_dict(cat1, items1):
                logger.error(f"Failed to set sys_dict for category {cat1} into database")
                return False

            # set sys_dict into redis
            if to_cache and not await sysdict_set(cat1, items1):
                logger.error(f"Failed to set sys_dict for category {cat1} into redis")
                return False
        return True

    async def _set_sys_map_info(self, sys_map: dict[str, dict[str, str]], to_cache: bool) -> bool:
        """Set sys_map information to database and redis."""
        for cat2, items2 in sys_map.items():
            if len(items2) == 0:
                continue

            # set sys_map into database
            if not await self._repository.set_sys_map(cat2, items2):
                logger.error(f"Failed to set sys_map for category {cat2} into database")
                return False

            # set sys_map into redis
            if to_cache and not await sysmap_set(cat2, items2):
                logger.error(f"Failed to set sys_map for category {cat2}")
                return False
        return True

    async def set_sys_info(
        self, sys_dict: dict[str, dict[int, Any]], sys_map: dict[str, dict[str, str]], to_cache: bool = False
    ) -> bool:
        """Set all system information to database and redis."""
        if sys_dict and not await self._set_sys_dict_info(sys_dict, to_cache):
            return False

        return not sys_map or await self._set_sys_map_info(sys_map, to_cache)
