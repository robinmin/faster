from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.engine import Result

from faster.core.models import SysDict, SysMap
from faster.core.repositories import SystemRepository


@pytest.mark.asyncio
class TestSystemRepository:
    """Test cases for SystemRepository functionality."""

    @pytest.fixture
    def mock_db_mgr(self) -> MagicMock:
        """Mock DatabaseManager for testing."""
        mock_mgr = MagicMock()
        mock_session = MagicMock()
        mock_txn = MagicMock()

        # Mock the context manager
        mock_txn.__aenter__ = AsyncMock(return_value=mock_session)
        mock_txn.__aexit__ = AsyncMock(return_value=None)

        mock_mgr.get_txn = MagicMock(return_value=mock_txn)
        return mock_mgr

    @pytest.fixture
    def repo(self, mock_db_mgr: MagicMock) -> SystemRepository:
        """Create SystemRepository instance with mocked db_mgr."""
        repo = SystemRepository()
        repo.db_mgr = mock_db_mgr
        return repo

    async def test_get_sys_map_no_filters(self, repo: SystemRepository, mock_db_mgr: MagicMock) -> None:
        """Test get_sys_map with no filters."""
        # Mock data
        mock_sys_maps = [
            SysMap(id=1, category="cat1", left_value="left1", right_value="right1", in_used=1),
            SysMap(id=2, category="cat1", left_value="left2", right_value="right2", in_used=1),
            SysMap(id=3, category="cat2", left_value="left3", right_value="right3", in_used=1),
        ]

        # Mock the query execution
        mock_result = MagicMock(spec=Result)
        mock_result.scalars.return_value.all.return_value = mock_sys_maps

        mock_session = mock_db_mgr.get_txn.return_value.__aenter__.return_value
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Call the method
        result = await repo.get_sys_map()

        # Verify the result
        expected = {"cat1": {"left1": "right1", "left2": "right2"}, "cat2": {"left3": "right3"}}
        assert result == expected

        # Verify the query was executed
        mock_session.execute.assert_called_once()

    async def test_get_sys_map_with_category_filter(self, repo: SystemRepository, mock_db_mgr: MagicMock) -> None:
        """Test get_sys_map with category filter."""
        mock_sys_maps = [
            SysMap(id=1, category="cat1", left_value="left1", right_value="right1", in_used=1),
        ]

        mock_result = MagicMock(spec=Result)
        mock_result.scalars.return_value.all.return_value = mock_sys_maps

        mock_session = mock_db_mgr.get_txn.return_value.__aenter__.return_value
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_sys_map(category="cat1")

        expected = {"cat1": {"left1": "right1"}}
        assert result == expected

    async def test_get_sys_map_with_left_filter(self, repo: SystemRepository, mock_db_mgr: MagicMock) -> None:
        """Test get_sys_map with left value filter."""
        mock_sys_maps = [
            SysMap(id=1, category="cat1", left_value="left1", right_value="right1", in_used=1),
        ]

        mock_result = MagicMock(spec=Result)
        mock_result.scalars.return_value.all.return_value = mock_sys_maps

        mock_session = mock_db_mgr.get_txn.return_value.__aenter__.return_value
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_sys_map(left="left1")

        expected = {"cat1": {"left1": "right1"}}
        assert result == expected

    async def test_get_sys_map_with_right_filter(self, repo: SystemRepository, mock_db_mgr: MagicMock) -> None:
        """Test get_sys_map with right value filter."""
        mock_sys_maps = [
            SysMap(id=1, category="cat1", left_value="left1", right_value="right1", in_used=1),
        ]

        mock_result = MagicMock(spec=Result)
        mock_result.scalars.return_value.all.return_value = mock_sys_maps

        mock_session = mock_db_mgr.get_txn.return_value.__aenter__.return_value
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_sys_map(right="right1")

        expected = {"cat1": {"left1": "right1"}}
        assert result == expected

    async def test_get_sys_map_in_used_only_false(self, repo: SystemRepository, mock_db_mgr: MagicMock) -> None:
        """Test get_sys_map with in_used_only=False."""
        mock_sys_maps = [
            SysMap(id=1, category="cat1", left_value="left1", right_value="right1", in_used=0),
            SysMap(id=2, category="cat1", left_value="left2", right_value="right2", in_used=1),
        ]

        mock_result = MagicMock(spec=Result)
        mock_result.scalars.return_value.all.return_value = mock_sys_maps

        mock_session = mock_db_mgr.get_txn.return_value.__aenter__.return_value
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_sys_map(in_used_only=False)

        expected = {"cat1": {"left1": "right1", "left2": "right2"}}
        assert result == expected

    async def test_get_sys_map_empty_result(self, repo: SystemRepository, mock_db_mgr: MagicMock) -> None:
        """Test get_sys_map with empty result."""
        mock_result = MagicMock(spec=Result)
        mock_result.scalars.return_value.all.return_value = []

        mock_session = mock_db_mgr.get_txn.return_value.__aenter__.return_value
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_sys_map()

        assert result == {}

    async def test_get_sys_dict_no_filters(self, repo: SystemRepository, mock_db_mgr: MagicMock) -> None:
        """Test get_sys_dict with no filters."""
        mock_sys_dicts = [
            SysDict(id=1, category="cat1", key=1, value="value1", in_used=1),
            SysDict(id=2, category="cat1", key=2, value="value2", in_used=1),
            SysDict(id=3, category="cat2", key=1, value="value3", in_used=1),
        ]

        mock_result = MagicMock(spec=Result)
        mock_result.scalars.return_value.all.return_value = mock_sys_dicts

        mock_session = mock_db_mgr.get_txn.return_value.__aenter__.return_value
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_sys_dict()

        expected = {"cat1": {1: "value1", 2: "value2"}, "cat2": {1: "value3"}}
        assert result == expected

    async def test_get_sys_dict_with_category_filter(self, repo: SystemRepository, mock_db_mgr: MagicMock) -> None:
        """Test get_sys_dict with category filter."""
        mock_sys_dicts = [
            SysDict(id=1, category="cat1", key=1, value="value1", in_used=1),
        ]

        mock_result = MagicMock(spec=Result)
        mock_result.scalars.return_value.all.return_value = mock_sys_dicts

        mock_session = mock_db_mgr.get_txn.return_value.__aenter__.return_value
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_sys_dict(category="cat1")

        expected = {"cat1": {1: "value1"}}
        assert result == expected

    async def test_get_sys_dict_with_key_filter(self, repo: SystemRepository, mock_db_mgr: MagicMock) -> None:
        """Test get_sys_dict with key filter."""
        mock_sys_dicts = [
            SysDict(id=1, category="cat1", key=1, value="value1", in_used=1),
        ]

        mock_result = MagicMock(spec=Result)
        mock_result.scalars.return_value.all.return_value = mock_sys_dicts

        mock_session = mock_db_mgr.get_txn.return_value.__aenter__.return_value
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_sys_dict(key=1)

        expected = {"cat1": {1: "value1"}}
        assert result == expected

    async def test_get_sys_dict_with_value_filter(self, repo: SystemRepository, mock_db_mgr: MagicMock) -> None:
        """Test get_sys_dict with value filter."""
        mock_sys_dicts = [
            SysDict(id=1, category="cat1", key=1, value="value1", in_used=1),
        ]

        mock_result = MagicMock(spec=Result)
        mock_result.scalars.return_value.all.return_value = mock_sys_dicts

        mock_session = mock_db_mgr.get_txn.return_value.__aenter__.return_value
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_sys_dict(value="value1")

        expected = {"cat1": {1: "value1"}}
        assert result == expected

    async def test_get_sys_dict_empty_result(self, repo: SystemRepository, mock_db_mgr: MagicMock) -> None:
        """Test get_sys_dict with empty result."""
        mock_result = MagicMock(spec=Result)
        mock_result.scalars.return_value.all.return_value = []

        mock_session = mock_db_mgr.get_txn.return_value.__aenter__.return_value
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_sys_dict()

        assert result == {}

    async def test_disable_category(self, repo: SystemRepository, mock_db_mgr: MagicMock) -> None:
        """Test disable_category method."""
        mock_result = MagicMock()
        mock_result.rowcount = 5

        mock_txn = mock_db_mgr.get_txn.return_value.__aenter__.return_value
        mock_txn.execute = AsyncMock(return_value=mock_result)

        result = await repo.disable_category("test_category")

        assert result == 5

        # Verify the update query was called
        mock_txn.execute.assert_called_once()

    async def test_disable_category_no_rows_affected(self, repo: SystemRepository, mock_db_mgr: MagicMock) -> None:
        """Test disable_category when no rows are affected."""
        mock_result = MagicMock()
        mock_result.rowcount = 0

        mock_txn = mock_db_mgr.get_txn.return_value.__aenter__.return_value
        mock_txn.execute = AsyncMock(return_value=mock_result)

        result = await repo.disable_category("nonexistent_category")

        assert result == 0

    async def test_repository_initialization(self) -> None:
        """Test SystemRepository initialization."""

        with patch("faster.core.repositories.DatabaseManager") as mock_db_mgr_class:
            mock_db_mgr_instance = MagicMock()
            mock_db_mgr_class.get_instance.return_value = mock_db_mgr_instance

            repo = SystemRepository()

            assert repo.db_mgr == mock_db_mgr_instance
            mock_db_mgr_class.get_instance.assert_called_once()
