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

    async def set_sys_info(  # noqa: C901
        self, sys_dict: dict[str, dict[int, Any]], sys_map: dict[str, dict[str, Any]], to_cache: bool = False
    ) -> bool:
        """Set all system information to database and redis."""
        result = True

        # save all sys_dict information into database and redis
        if sys_dict:
            for cat1, items1 in sys_dict.items():
                if len(items1) == 0:
                    continue

                # set sys_dict into database
                if not await self._repository.set_sys_dict(cat1, items1):
                    logger.error(f"Failed to set sys_dict for category {cat1} into database")
                    result = False
                    break

                # set sys_dict into redis
                if to_cache and not await sysdict_set(cat1, items1):
                    logger.error(f"Failed to set sys_dict for category {cat1} into redis")
                    result = False
                    break

        # save all sys_map information into database and redis
        if sys_map:
            for cat2, items2 in sys_map.items():
                if len(items2) == 0:
                    continue

                # set sys_map into database
                if not await self._repository.set_sys_map(cat2, items2):
                    logger.error(f"Failed to set sys_map for category {cat2} into database")
                    result = False
                    break

                # set sys_map into redis
                if to_cache and not await sysmap_set(cat2, items2):
                    logger.error(f"Failed to set sys_map for category {cat2}")
                    result = False
                    break

        return result
