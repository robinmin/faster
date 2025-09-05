from datetime import datetime

from sqlmodel import Field

from faster.core.schemas import MyBase, SysDict, SysMap


class TestMyBase:
    """Test cases for MyBase class functionality."""

    def test_mybase_model_initialization(self) -> None:
        """Test MyBase initialization with default values."""

        # Create a concrete subclass for testing
        class TestModel1(MyBase, table=True):
            __tablename__ = "test_model_1"
            id: int = Field(primary_key=True)
            name: str

        model = TestModel1(id=1, name="test")
        assert model.name == "test"
        assert model.in_used == 1
        assert model.is_active is True
        assert model.is_deleted is False
        assert model.deleted_at is None

    def test_mybase_soft_delete(self) -> None:
        """Test soft delete functionality."""

        class TestModel2(MyBase, table=True):
            __tablename__ = "test_model_2"
            id: int = Field(primary_key=True)
            name: str

        model = TestModel2(id=1, name="test")
        model.soft_delete()

        assert model.in_used == 0
        assert model.is_active is False
        assert model.is_deleted is True
        assert model.deleted_at is not None
        assert isinstance(model.deleted_at, datetime)

    def test_mybase_restore(self) -> None:
        """Test restore functionality."""

        class TestModel3(MyBase, table=True):
            __tablename__ = "test_model_3"
            id: int = Field(primary_key=True)
            name: str

        model = TestModel3(id=1, name="test")
        model.soft_delete()

        # Verify it's soft deleted
        assert model.is_deleted is True

        # Restore it
        model.restore()

        assert model.in_used == 1
        assert model.is_active is True
        assert model.is_deleted is False
        assert model.deleted_at is None

    def test_mybase_is_active_property(self) -> None:
        """Test is_active property."""

        class TestModel4(MyBase, table=True):
            __tablename__ = "test_model_4"
            id: int = Field(primary_key=True)
            name: str

        model = TestModel4(id=1, name="test")

        # Initially active
        assert model.is_active is True

        # After soft delete
        model.in_used = 0
        assert model.is_active is False

        # After restore
        model.in_used = 1
        assert model.is_active is True

    def test_mybase_is_deleted_property(self) -> None:
        """Test is_deleted property."""

        class TestModel5(MyBase, table=True):
            __tablename__ = "test_model_5"
            id: int = Field(primary_key=True)
            name: str

        model = TestModel5(id=1, name="test")

        # Initially not deleted
        assert model.is_deleted is False

        # After soft delete
        model.in_used = 0
        assert model.is_deleted is True

        # After restore
        model.in_used = 1
        assert model.is_deleted is False

    def test_mybase_soft_delete_preserves_other_fields(self) -> None:
        """Test that soft delete only affects in_used and deleted_at."""

        class TestModel6(MyBase, table=True):
            __tablename__ = "test_model_6"
            id: int = Field(primary_key=True)
            name: str
            description: str = "test description"

        model = TestModel6(id=1, name="test", description="test description")
        original_created_at = model.created_at
        original_updated_at = model.updated_at

        model.soft_delete()

        # Check that other fields are preserved
        assert model.name == "test"
        assert model.description == "test description"
        assert model.created_at == original_created_at
        assert model.updated_at == original_updated_at

    def test_mybase_restore_preserves_other_fields(self) -> None:
        """Test that restore only affects in_used and deleted_at."""

        class TestModel7(MyBase, table=True):
            __tablename__ = "test_model_7"
            id: int = Field(primary_key=True)
            name: str
            description: str = "test description"

        model = TestModel7(id=1, name="test", description="test description")
        model.soft_delete()

        # Modify some fields while soft deleted
        model.name = "modified"

        model.restore()

        # Check that modifications are preserved
        assert model.name == "modified"
        assert model.description == "test description"
        assert model.in_used == 1
        assert model.deleted_at is None


class TestSysMap:
    """Test cases for SysMap model."""

    def test_sysmap_model_initialization(self) -> None:
        """Test SysMap initialization."""
        sys_map = SysMap(id=1, category="test_category", left_value="left_val", right_value="right_val", order=5)

        assert sys_map.category == "test_category"
        assert sys_map.left_value == "left_val"
        assert sys_map.right_value == "right_val"
        assert sys_map.order == 5
        assert sys_map.in_used == 1
        assert sys_map.is_active is True

    def test_sysmap_model_default_order(self) -> None:
        """Test SysMap default order value."""
        sys_map = SysMap(id=2, category="test_category", left_value="left_val", right_value="right_val")

        assert sys_map.order == 0

    def test_sysmap_inherits_soft_delete_from_mybase(self) -> None:
        """Test SysMap soft delete functionality inherited from MyBase."""
        sys_map = SysMap(id=3, category="test_category", left_value="left_val", right_value="right_val")

        sys_map.soft_delete()

        assert sys_map.in_used == 0
        assert sys_map.is_deleted is True
        assert sys_map.deleted_at is not None


class TestSysDict:
    """Test cases for SysDict model."""

    def test_sysdict_model_initialization(self) -> None:
        """Test SysDict initialization."""
        sys_dict = SysDict(id=1, category="test_category", key=123, value="test_value", order=10)

        assert sys_dict.category == "test_category"
        assert sys_dict.key == 123
        assert sys_dict.value == "test_value"
        assert sys_dict.order == 10
        assert sys_dict.in_used == 1
        assert sys_dict.is_active is True

    def test_sysdict_model_default_order(self) -> None:
        """Test SysDict default order value."""
        sys_dict = SysDict(id=2, category="test_category", key=456, value="test_value")

        assert sys_dict.order == 0

    def test_sysdict_inherits_soft_delete_from_mybase(self) -> None:
        """Test SysDict soft delete functionality inherited from MyBase."""
        sys_dict = SysDict(id=3, category="test_category", key=789, value="test_value")

        sys_dict.soft_delete()

        assert sys_dict.in_used == 0
        assert sys_dict.is_deleted is True
        assert sys_dict.deleted_at is not None


class TestModelIntegration:
    """Integration tests for model functionality."""

    def test_multiple_soft_deletes(self) -> None:
        """Test soft deleting multiple records."""

        class TestModel(MyBase, table=True):
            __tablename__ = "test_model_integration"
            id: int = Field(primary_key=True)
            name: str

        models = [TestModel(id=1, name="model1"), TestModel(id=2, name="model2"), TestModel(id=3, name="model3")]

        # Soft delete all
        for model in models:
            model.soft_delete()

        # Verify all are deleted
        for model in models:
            assert model.is_deleted is True
            assert model.in_used == 0

    def test_mixed_active_deleted_state(self) -> None:
        """Test having both active and deleted records."""

        class TestModelMixed(MyBase, table=True):
            __tablename__ = "test_model_mixed"
            id: int = Field(primary_key=True)
            name: str

        active_model = TestModelMixed(id=1, name="active")
        deleted_model = TestModelMixed(id=2, name="deleted")

        deleted_model.soft_delete()

        assert active_model.is_active is True
        assert deleted_model.is_deleted is True

        # Restore one
        deleted_model.restore()

        assert active_model.is_active is True
        assert deleted_model.is_active is True
