import contextlib

import pytest
import pytest_asyncio
from sqlmodel import delete

from faster.core.database import DatabaseManager, DBSession
from faster.core.repositories import AppRepository
from faster.core.schemas import SysDict, SysMap


@pytest.mark.asyncio
class TestAppRepository:
    """Test cases for AppRepository functionality."""

    @pytest_asyncio.fixture(autouse=True)
    async def cleanup_tables(self, db_manager: DatabaseManager) -> None:
        """Clean up all test data before each test to ensure test isolation."""
        # Clean up data before each test
        async with db_manager.get_transaction() as session:
            # Delete all test data from the tables using SQLAlchemy delete statements
            # Only delete if tables exist to avoid errors during initial setup
            with contextlib.suppress(Exception):
                _ = await session.execute(delete(SysMap))  # type: ignore[unused-ignore]
            with contextlib.suppress(Exception):
                _ = await session.execute(delete(SysDict))  # type: ignore[unused-ignore]
            await session.commit()

    @pytest.fixture
    def app_repository(self, db_manager: DatabaseManager) -> AppRepository:
        """Create AppRepository instance with real database manager."""
        return AppRepository(db_manager=db_manager)

    async def test_get_sys_map_no_filters(self, app_repository: AppRepository, db_session: DBSession) -> None:
        """Test get_sys_map with no filters using real database."""
        # Create test data in the database
        test_sys_maps = [
            SysMap(category="cat1", left_value="left1", right_value="right1", in_used=1, order=1),
            SysMap(category="cat1", left_value="left2", right_value="right2", in_used=1, order=2),
            SysMap(category="cat2", left_value="left3", right_value="right3", in_used=1, order=3),
        ]

        # Insert test data using real database transaction
        async with app_repository.transaction() as session:
            for sys_map in test_sys_maps:
                session.add(sys_map)
            await session.flush()

        # Call the method under test
        result = await app_repository.get_sys_map()

        # Verify the result
        expected = {"cat1": {"left1": ["right1"], "left2": ["right2"]}, "cat2": {"left3": ["right3"]}}
        assert result == expected

    async def test_get_sys_map_with_category_filter(self, app_repository: AppRepository, db_session: DBSession) -> None:
        """Test get_sys_map with category filter using real database."""
        # Create test data in the database
        test_sys_maps = [
            SysMap(category="cat1", left_value="left1", right_value="right1", in_used=1, order=1),
            SysMap(category="cat2", left_value="left2", right_value="right2", in_used=1, order=2),
        ]

        # Insert test data
        async with app_repository.transaction() as session:
            for sys_map in test_sys_maps:
                session.add(sys_map)
            await session.flush()

        # Test with category filter
        result = await app_repository.get_sys_map(category="cat1")

        expected = {"cat1": {"left1": ["right1"]}}
        assert result == expected

    async def test_get_sys_map_with_left_filter(self, app_repository: AppRepository, db_session: DBSession) -> None:
        """Test get_sys_map with left value filter using real database."""
        # Create test data in the database
        test_sys_maps = [
            SysMap(category="cat1", left_value="left1", right_value="right1", in_used=1, order=1),
            SysMap(category="cat1", left_value="left2", right_value="right2", in_used=1, order=2),
        ]

        # Insert test data
        async with app_repository.transaction() as session:
            for sys_map in test_sys_maps:
                session.add(sys_map)
            await session.flush()

        # Test with left filter
        result = await app_repository.get_sys_map(left="left1")

        expected = {"cat1": {"left1": ["right1"]}}
        assert result == expected

    async def test_get_sys_map_with_right_filter(self, app_repository: AppRepository, db_session: DBSession) -> None:
        """Test get_sys_map with right value filter using real database."""
        # Create test data in the database
        test_sys_maps = [
            SysMap(category="cat1", left_value="left1", right_value="right1", in_used=1, order=1),
            SysMap(category="cat1", left_value="left2", right_value="right2", in_used=1, order=2),
        ]

        # Insert test data
        async with app_repository.transaction() as session:
            for sys_map in test_sys_maps:
                session.add(sys_map)
            await session.flush()

        # Test with right filter
        result = await app_repository.get_sys_map(right="right1")

        expected = {"cat1": {"left1": ["right1"]}}
        assert result == expected

    async def test_get_sys_map_in_used_only_false(self, app_repository: AppRepository, db_session: DBSession) -> None:
        """Test get_sys_map with in_used_only=False using real database."""
        # Create test data with mixed in_used values
        test_sys_maps = [
            SysMap(category="cat1", left_value="left1", right_value="right1", in_used=1, order=1),
            SysMap(category="cat1", left_value="left2", right_value="right2", in_used=0, order=2),  # inactive
        ]

        # Insert test data
        async with app_repository.transaction() as session:
            for sys_map in test_sys_maps:
                session.add(sys_map)
            await session.flush()

        # Test with in_used_only=False (should include inactive records)
        result = await app_repository.get_sys_map(in_used_only=False)

        expected = {"cat1": {"left1": ["right1"], "left2": ["right2"]}}
        assert result == expected

        # Test with in_used_only=True (default, should exclude inactive records)
        result_active_only = await app_repository.get_sys_map(in_used_only=True)

        expected_active_only = {"cat1": {"left1": ["right1"]}}
        assert result_active_only == expected_active_only

    async def test_get_sys_map_empty_result(self, app_repository: AppRepository, db_session: DBSession) -> None:
        """Test get_sys_map when no data matches criteria using real database."""
        # No test data inserted - should return empty dict
        result = await app_repository.get_sys_map(category="nonexistent")

        assert result == {}

    async def test_get_sys_dict_no_filters(self, app_repository: AppRepository, db_session: DBSession) -> None:
        """Test get_sys_dict with no filters using real database."""
        # Create test data in the database
        test_sys_dicts = [
            SysDict(category="cat1", key=1, value="value1", in_used=1, order=1),
            SysDict(category="cat1", key=2, value="value2", in_used=1, order=2),
            SysDict(category="cat2", key=3, value="value3", in_used=1, order=3),
        ]

        # Insert test data
        async with app_repository.transaction() as session:
            for sys_dict in test_sys_dicts:
                session.add(sys_dict)
            await session.flush()

        # Test get_sys_dict
        result = await app_repository.get_sys_dict()

        expected = {"cat1": {1: "value1", 2: "value2"}, "cat2": {3: "value3"}}
        assert result == expected

    async def test_get_sys_dict_with_category_filter(
        self, app_repository: AppRepository, db_session: DBSession
    ) -> None:
        """Test get_sys_dict with category filter using real database."""
        # Create test data in the database
        test_sys_dicts = [
            SysDict(category="cat1", key=1, value="value1", in_used=1, order=1),
            SysDict(category="cat2", key=2, value="value2", in_used=1, order=2),
        ]

        # Insert test data
        async with app_repository.transaction() as session:
            for sys_dict in test_sys_dicts:
                session.add(sys_dict)
            await session.flush()

        # Test with category filter
        result = await app_repository.get_sys_dict(category="cat1")

        expected = {"cat1": {1: "value1"}}
        assert result == expected

    async def test_get_sys_dict_with_key_filter(self, app_repository: AppRepository, db_session: DBSession) -> None:
        """Test get_sys_dict with key filter using real database."""
        # Create test data in the database
        test_sys_dicts = [
            SysDict(category="cat1", key=1, value="value1", in_used=1, order=1),
            SysDict(category="cat1", key=2, value="value2", in_used=1, order=2),
        ]

        # Insert test data
        async with app_repository.transaction() as session:
            for sys_dict in test_sys_dicts:
                session.add(sys_dict)
            await session.flush()

        # Test with key filter
        result = await app_repository.get_sys_dict(key=1)

        expected = {"cat1": {1: "value1"}}
        assert result == expected

    async def test_get_sys_dict_with_value_filter(self, app_repository: AppRepository, db_session: DBSession) -> None:
        """Test get_sys_dict with value filter using real database."""
        # Create test data in the database
        test_sys_dicts = [
            SysDict(category="cat1", key=1, value="value1", in_used=1, order=1),
            SysDict(category="cat1", key=2, value="value2", in_used=1, order=2),
        ]

        # Insert test data
        async with app_repository.transaction() as session:
            for sys_dict in test_sys_dicts:
                session.add(sys_dict)
            await session.flush()

        # Test with value filter
        result = await app_repository.get_sys_dict(value="value1")

        expected = {"cat1": {1: "value1"}}
        assert result == expected

    async def test_get_sys_dict_empty_result(self, app_repository: AppRepository, db_session: DBSession) -> None:
        """Test get_sys_dict when no data matches criteria using real database."""
        # No test data inserted - should return empty dict
        result = await app_repository.get_sys_dict(category="nonexistent")

        assert result == {}

    async def test_disable_category(self, app_repository: AppRepository, db_session: DBSession) -> None:
        """Test disable_category method using real database."""
        # Create test data in the database
        test_sys_maps = [
            SysMap(category="test_category", left_value="left1", right_value="right1", in_used=1, order=1),
            SysMap(category="test_category", left_value="left2", right_value="right2", in_used=1, order=2),
            SysMap(category="other_category", left_value="left3", right_value="right3", in_used=1, order=3),
        ]

        # Insert test data
        async with app_repository.transaction() as session:
            for sys_map in test_sys_maps:
                session.add(sys_map)
            await session.flush()

        # Test disable_category
        result = await app_repository.disable_category("test_category")

        # Should return number of rows affected (2 records with "test_category")
        assert result == 2

        # Should only contain the "other_category" records as active
        active_data = await app_repository.get_sys_map(in_used_only=True)
        expected_active = {"other_category": {"left3": ["right3"]}}
        assert active_data == expected_active

    async def test_disable_category_no_rows_affected(
        self, app_repository: AppRepository, db_session: DBSession
    ) -> None:
        """Test disable_category when no rows are affected using real database."""
        # No test data inserted for the target category
        result = await app_repository.disable_category("nonexistent_category")

        # Should return 0 as no rows were affected
        assert result == 0

    async def test_repository_initialization(self) -> None:
        """Test AppRepository initialization."""
        repo = AppRepository()
        assert repo.db_manager is not None
