from typing import Any

import sqlalchemy as sa

from faster.core.builders import (
    DB,
    # Convenience aliases
    QB,
    UB,
    DeleteBuilder,
    QueryBuilder,
    UpdateBuilder,
    db,
    delete_builder,
    qb,
    query_builder,
    sdb,
    soft_delete_query_builder,
    ub,
    update_builder,
)
from faster.core.schemas import SysDict, SysMap


def get_sql_string(query: Any) -> str:
    """Helper function to get SQL string from query."""
    return str(query.compile(compile_kwargs={"literal_binds": True}))


class TestWhereClauseMixin:
    """Test cases for WhereClauseMixin functionality."""

    def test_where_str(self) -> None:
        """Test where_str method adds string equality condition."""
        builder = QueryBuilder(SysMap)
        result = builder.where_str(SysMap.category, "user")

        assert result is builder  # Should return self for chaining

        # Build and check the SQL
        query = builder.build()
        sql_str = get_sql_string(query)
        assert "C_CATEGORY" in sql_str and "user" in sql_str

    def test_where_int(self) -> None:
        """Test where_int method adds integer equality condition."""
        builder = QueryBuilder(SysMap)
        result = builder.where_int(SysMap.order, 42)

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "N_ORDER" in sql_str and "42" in sql_str

    def test_where_bool(self) -> None:
        """Test where_bool method adds boolean equality condition."""
        builder = QueryBuilder(SysMap)
        result = builder.where_bool(SysMap.in_used, True)

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "N_IN_USED" in sql_str and ("true" in sql_str.lower() or "1" in sql_str)

    def test_where_float(self) -> None:
        """Test where_float method adds float equality condition."""
        builder = QueryBuilder(SysDict)

        # Create a test model with a float field for testing
        float_col = sa.Column("score", sa.Float)

        result = builder.where_float(float_col, 3.14)
        assert result is builder

    def test_generic_where_method_string(self) -> None:
        """Test generic where method with string value."""
        builder = QueryBuilder(SysMap)
        result = builder.where(SysMap.category, "admin")

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "C_CATEGORY" in sql_str and "admin" in sql_str

    def test_generic_where_method_int(self) -> None:
        """Test generic where method with integer value."""
        builder = QueryBuilder(SysMap)
        result = builder.where(SysMap.order, 100)

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "N_ORDER" in sql_str and "100" in sql_str

    def test_generic_where_method_bool(self) -> None:
        """Test generic where method with boolean value."""
        builder = QueryBuilder(SysMap)
        result = builder.where(SysMap.in_used, 1)  # Using 1 as truthy value

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "N_IN_USED" in sql_str and "1" in sql_str

    def test_where_custom(self) -> None:
        """Test where_custom method with custom condition."""
        builder = QueryBuilder(SysMap)
        custom_condition = SysMap.order > 50
        result = builder.where_custom(custom_condition)

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "N_ORDER" in sql_str and ">" in sql_str and "50" in sql_str

    def test_where_in(self) -> None:
        """Test where_in method with list of values."""
        builder = QueryBuilder(SysMap)
        result = builder.where_in(SysMap.category, ["user", "admin", "guest"])

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "C_CATEGORY" in sql_str and "IN" in sql_str and "user" in sql_str

    def test_where_like(self) -> None:
        """Test where_like method with pattern matching."""
        builder = QueryBuilder(SysMap)
        result = builder.where_like(SysMap.category, "%admin%")

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "C_CATEGORY" in sql_str and "LIKE" in sql_str and "%admin%" in sql_str

    def test_where_gt(self) -> None:
        """Test where_gt method for greater than comparison."""
        builder = QueryBuilder(SysMap)
        result = builder.where_gt(SysMap.order, 10)

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "N_ORDER" in sql_str and ">" in sql_str and "10" in sql_str

    def test_where_lt(self) -> None:
        """Test where_lt method for less than comparison."""
        builder = QueryBuilder(SysMap)
        result = builder.where_lt(SysMap.order, 100)

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "N_ORDER" in sql_str and "<" in sql_str and "100" in sql_str

    def test_where_gte(self) -> None:
        """Test where_gte method for greater than or equal comparison."""
        builder = QueryBuilder(SysMap)
        result = builder.where_gte(SysMap.order, 5)

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "N_ORDER" in sql_str and ">=" in sql_str and "5" in sql_str

    def test_where_lte(self) -> None:
        """Test where_lte method for less than or equal comparison."""
        builder = QueryBuilder(SysMap)
        result = builder.where_lte(SysMap.order, 50)

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "N_ORDER" in sql_str and "<=" in sql_str and "50" in sql_str

    def test_method_chaining(self) -> None:
        """Test that multiple where methods can be chained together."""
        builder = QueryBuilder(SysMap)
        result = (
            builder.where_str(SysMap.category, "user")
            .where_gt(SysMap.order, 10)
            .where_in(SysMap.left_value, ["key1", "key2"])
        )

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "C_CATEGORY" in sql_str and "user" in sql_str
        assert "N_ORDER" in sql_str and ">" in sql_str and "10" in sql_str
        assert "C_LEFT_VALUE" in sql_str and "IN" in sql_str


class TestQueryBuilder:
    """Test cases for QueryBuilder functionality."""

    def test_initialization(self) -> None:
        """Test QueryBuilder initialization."""
        builder = QueryBuilder(SysMap)

        assert builder._model is SysMap
        assert builder._query is not None

    def test_active_only_soft_delete_model(self) -> None:
        """Test active_only method for soft delete models."""
        builder = QueryBuilder(SysMap)  # SysMap inherits from MyBase which has in_used
        result = builder.active_only()

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "N_IN_USED" in sql_str and "1" in sql_str

    def test_deleted_only_soft_delete_model(self) -> None:
        """Test deleted_only method for soft delete models."""
        builder = QueryBuilder(SysMap)
        result = builder.deleted_only()

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "N_IN_USED" in sql_str and "0" in sql_str

    def test_order_by_ascending(self) -> None:
        """Test order_by method for ascending order."""
        builder = QueryBuilder(SysMap)
        result = builder.order_by(SysMap.order)

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "ORDER BY" in sql_str and "N_ORDER" in sql_str
        assert "DESC" not in sql_str

    def test_order_by_descending(self) -> None:
        """Test order_by method for descending order."""
        builder = QueryBuilder(SysMap)
        result = builder.order_by(SysMap.order, desc=True)

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "ORDER BY" in sql_str and "N_ORDER" in sql_str and "DESC" in sql_str

    def test_limit(self) -> None:
        """Test limit method."""
        builder = QueryBuilder(SysMap)
        result = builder.limit(10)

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "LIMIT" in sql_str or hasattr(query, "_limit")

    def test_offset(self) -> None:
        """Test offset method."""
        builder = QueryBuilder(SysMap)
        result = builder.offset(5)

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "OFFSET" in sql_str or hasattr(query, "_offset")

    def test_build_returns_select_query(self) -> None:
        """Test that build method returns a Select query."""
        builder = QueryBuilder(SysMap)
        query = builder.build()

        # Check that it's a Select object
        assert hasattr(query, "whereclause")
        assert str(query).startswith("SELECT")

    def test_build_delete_returns_delete_query(self) -> None:
        """Test that build_delete method returns a Delete query."""
        builder = QueryBuilder(SysMap)
        builder.where_str(SysMap.category, "test")

        delete_query = builder.build_delete()

        # Check that it's a Delete object
        sql_str = get_sql_string(delete_query)
        assert "DELETE FROM" in sql_str
        assert "C_CATEGORY" in sql_str and "test" in sql_str

    def test_complex_query_building(self) -> None:
        """Test building a complex query with multiple conditions."""
        builder = QueryBuilder(SysMap)
        query = (
            builder.where_str(SysMap.category, "user")
            .where_gt(SysMap.order, 10)
            .active_only()
            .order_by(SysMap.order, desc=True)
            .limit(50)
            .offset(10)
            .build()
        )

        sql_str = get_sql_string(query)

        # Check all conditions are present
        assert "C_CATEGORY" in sql_str and "user" in sql_str
        assert "N_ORDER" in sql_str and ">" in sql_str and "10" in sql_str
        assert "N_IN_USED" in sql_str and "1" in sql_str
        assert "ORDER BY" in sql_str and "DESC" in sql_str


class TestDeleteBuilder:
    """Test cases for DeleteBuilder functionality."""

    def test_initialization(self) -> None:
        """Test DeleteBuilder initialization."""
        builder = DeleteBuilder(SysMap)

        assert builder._model is SysMap
        assert builder._query is not None

    def test_build_returns_delete_query(self) -> None:
        """Test that build method returns a Delete query."""
        builder = DeleteBuilder(SysMap)
        query = builder.build()

        sql_str = get_sql_string(query)
        assert "DELETE FROM" in sql_str

    def test_delete_with_conditions(self) -> None:
        """Test delete query with WHERE conditions."""
        builder = DeleteBuilder(SysMap)
        query = builder.where_str(SysMap.category, "old_data").where_gt(SysMap.order, 100).build()

        sql_str = get_sql_string(query)
        assert "DELETE FROM" in sql_str and "SYS_MAP" in sql_str
        assert "C_CATEGORY" in sql_str and "old_data" in sql_str
        assert "N_ORDER" in sql_str and ">" in sql_str and "100" in sql_str

    def test_inherits_where_mixin_methods(self) -> None:
        """Test that DeleteBuilder inherits all WhereClauseMixin methods."""
        builder = DeleteBuilder(SysMap)

        # Test that all mixin methods are available
        assert hasattr(builder, "where_str")
        assert hasattr(builder, "where_int")
        assert hasattr(builder, "where_bool")
        assert hasattr(builder, "where_float")
        assert hasattr(builder, "where")
        assert hasattr(builder, "where_custom")
        assert hasattr(builder, "where_in")
        assert hasattr(builder, "where_like")
        assert hasattr(builder, "where_gt")
        assert hasattr(builder, "where_lt")
        assert hasattr(builder, "where_gte")
        assert hasattr(builder, "where_lte")


class TestUpdateBuilder:
    """Test cases for UpdateBuilder functionality."""

    def test_initialization(self) -> None:
        """Test UpdateBuilder initialization."""
        builder = UpdateBuilder(SysMap)

        assert builder._model is SysMap
        assert builder._query is not None
        assert builder._values == {}

    def test_set_str(self) -> None:
        """Test set_str method for setting string values."""
        builder = UpdateBuilder(SysMap)
        result = builder.set_str(SysMap.category, "updated_category")

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "UPDATE" in sql_str and "SET" in sql_str
        assert "C_CATEGORY" in sql_str and "updated_category" in sql_str

    def test_set_int(self) -> None:
        """Test set_int method for setting integer values."""
        builder = UpdateBuilder(SysMap)
        result = builder.set_int(SysMap.order, 999)

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "UPDATE" in sql_str and "SET" in sql_str
        assert "N_ORDER" in sql_str and "999" in sql_str

    def test_set_bool(self) -> None:
        """Test set_bool method for setting boolean values."""
        builder = UpdateBuilder(SysMap)
        result = builder.set_bool(SysMap.in_used, False)

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "UPDATE" in sql_str and "SET" in sql_str
        assert "N_IN_USED" in sql_str and ("false" in sql_str.lower() or "0" in sql_str)

    def test_generic_set_method_string(self) -> None:
        """Test generic set method with string value."""
        builder = UpdateBuilder(SysMap)
        result = builder.set(SysMap.category, "new_category")

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "UPDATE" in sql_str and "SET" in sql_str
        assert "C_CATEGORY" in sql_str and "new_category" in sql_str

    def test_generic_set_method_int(self) -> None:
        """Test generic set method with integer value."""
        builder = UpdateBuilder(SysMap)
        result = builder.set(SysMap.order, 555)

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "UPDATE" in sql_str and "SET" in sql_str
        assert "N_ORDER" in sql_str and "555" in sql_str

    def test_set_values_multiple(self) -> None:
        """Test set_values method for setting multiple values at once."""
        builder = UpdateBuilder(SysMap)
        result = builder.set_values(category="bulk_update", order=777)

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        # Order of SET clauses may vary, so check both are present
        assert "UPDATE" in sql_str and "SET" in sql_str
        assert "bulk_update" in sql_str and "777" in sql_str

    def test_increment(self) -> None:
        """Test increment method for numeric columns."""
        builder = UpdateBuilder(SysMap)
        result = builder.increment(SysMap.order, 5)

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "UPDATE" in sql_str and "SET" in sql_str
        assert "N_ORDER" in sql_str and "+" in sql_str and "5" in sql_str

    def test_increment_default_amount(self) -> None:
        """Test increment method with default amount of 1."""
        builder = UpdateBuilder(SysMap)
        result = builder.increment(SysMap.order)

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "UPDATE" in sql_str and "SET" in sql_str
        assert "N_ORDER" in sql_str and "+" in sql_str and "1" in sql_str

    def test_decrement(self) -> None:
        """Test decrement method for numeric columns."""
        builder = UpdateBuilder(SysMap)
        result = builder.decrement(SysMap.order, 3)

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "UPDATE" in sql_str and "SET" in sql_str
        assert "N_ORDER" in sql_str and "-" in sql_str and "3" in sql_str

    def test_decrement_default_amount(self) -> None:
        """Test decrement method with default amount of 1."""
        builder = UpdateBuilder(SysMap)
        result = builder.decrement(SysMap.order)

        assert result is builder

        query = builder.build()
        sql_str = get_sql_string(query)
        assert "UPDATE" in sql_str and "SET" in sql_str
        assert "N_ORDER" in sql_str and "-" in sql_str and "1" in sql_str

    def test_update_with_where_conditions(self) -> None:
        """Test update query with WHERE conditions."""
        builder = UpdateBuilder(SysMap)
        query = (
            builder.set_str(SysMap.category, "updated_category")
            .set_int(SysMap.order, 999)
            .where_str(SysMap.left_value, "old_value")
            .build()
        )

        sql_str = get_sql_string(query)
        assert "UPDATE" in sql_str and "SET" in sql_str
        assert "C_CATEGORY" in sql_str and "updated_category" in sql_str
        assert "N_ORDER" in sql_str and "999" in sql_str
        assert "WHERE" in sql_str and "C_LEFT_VALUE" in sql_str and "old_value" in sql_str

    def test_build_returns_update_query(self) -> None:
        """Test that build method returns an Update query."""
        builder = UpdateBuilder(SysMap)
        builder.set_str(SysMap.category, "test")

        query = builder.build()
        sql_str = get_sql_string(query)
        assert sql_str.startswith("UPDATE")

    def test_inherits_where_mixin_methods(self) -> None:
        """Test that UpdateBuilder inherits all WhereClauseMixin methods."""
        builder = UpdateBuilder(SysMap)

        # Test that all mixin methods are available
        assert hasattr(builder, "where_str")
        assert hasattr(builder, "where_int")
        assert hasattr(builder, "where_bool")
        assert hasattr(builder, "where_float")
        assert hasattr(builder, "where")
        assert hasattr(builder, "where_custom")
        assert hasattr(builder, "where_in")
        assert hasattr(builder, "where_like")
        assert hasattr(builder, "where_gt")
        assert hasattr(builder, "where_lt")
        assert hasattr(builder, "where_gte")
        assert hasattr(builder, "where_lte")


class TestFactoryFunctions:
    """Test cases for factory functions."""

    def test_query_builder_factory(self) -> None:
        """Test query_builder factory function."""
        builder = query_builder(SysMap)

        assert isinstance(builder, QueryBuilder)
        assert builder._model is SysMap

    def test_soft_delete_query_builder_factory(self) -> None:
        """Test soft_delete_query_builder factory function."""
        builder = soft_delete_query_builder(SysMap)

        assert isinstance(builder, QueryBuilder)
        assert builder._model is SysMap

        # Test that soft delete methods are available
        result = builder.active_only()
        assert result is builder

    def test_delete_builder_factory(self) -> None:
        """Test delete_builder factory function."""
        builder = delete_builder(SysMap)

        assert isinstance(builder, DeleteBuilder)
        assert builder._model is SysMap

    def test_update_builder_factory(self) -> None:
        """Test update_builder factory function."""
        builder = update_builder(SysMap)

        assert isinstance(builder, UpdateBuilder)
        assert builder._model is SysMap


class TestConvenienceAliases:
    """Test cases for convenience aliases."""

    def test_class_aliases(self) -> None:
        """Test class aliases QB, DB, UB."""
        # Test that aliases point to the correct classes
        assert QB is QueryBuilder
        assert DB is DeleteBuilder
        assert UB is UpdateBuilder

    def test_function_aliases(self) -> None:
        """Test function aliases qb, sdb, db, ub."""
        # Test that function aliases work correctly
        qb_instance = qb(SysMap)
        assert isinstance(qb_instance, QueryBuilder)

        sdb_instance = sdb(SysMap)
        assert isinstance(sdb_instance, QueryBuilder)

        db_instance = db(SysMap)
        assert isinstance(db_instance, DeleteBuilder)

        ub_instance = ub(SysMap)
        assert isinstance(ub_instance, UpdateBuilder)

    def test_alias_functionality(self) -> None:
        """Test that aliases work with actual operations."""
        # Test QB alias
        qb_query = QB(SysMap).where_str(SysMap.category, "test").build()
        assert str(qb_query).startswith("SELECT")

        # Test DB alias
        db_query = DB(SysMap).where_str(SysMap.category, "test").build()
        assert "DELETE" in get_sql_string(db_query)

        # Test UB alias
        ub_query = UB(SysMap).set_str(SysMap.category, "test").build()
        assert "UPDATE" in get_sql_string(ub_query)


class TestIntegration:
    """Integration tests for the complete builder system."""

    def test_query_builder_full_workflow(self) -> None:
        """Test a complete QueryBuilder workflow."""
        query = (
            QueryBuilder(SysMap)
            .where_str(SysMap.category, "user")
            .where_gt(SysMap.order, 10)
            .active_only()
            .order_by(SysMap.order, desc=True)
            .limit(50)
            .build()
        )

        sql_str = get_sql_string(query)

        # Verify all parts are present
        assert "SELECT" in sql_str
        assert "SYS_MAP" in sql_str
        assert "C_CATEGORY" in sql_str and "user" in sql_str
        assert "N_ORDER" in sql_str and ">" in sql_str and "10" in sql_str
        assert "N_IN_USED" in sql_str and "1" in sql_str
        assert "ORDER BY" in sql_str and "DESC" in sql_str

    def test_delete_builder_full_workflow(self) -> None:
        """Test a complete DeleteBuilder workflow."""
        query = DeleteBuilder(SysMap).where_str(SysMap.category, "old_data").where_gt(SysMap.order, 100).build()

        sql_str = get_sql_string(query)

        # Verify all parts are present
        assert "DELETE FROM" in sql_str and "SYS_MAP" in sql_str
        assert "C_CATEGORY" in sql_str and "old_data" in sql_str
        assert "N_ORDER" in sql_str and ">" in sql_str and "100" in sql_str

    def test_update_builder_full_workflow(self) -> None:
        """Test a complete UpdateBuilder workflow."""
        query = (
            UpdateBuilder(SysMap)
            .set_str(SysMap.category, "updated_category")
            .set_int(SysMap.order, 999)
            .where_str(SysMap.left_value, "old_value")
            .where_gt(SysMap.order, 0)
            .build()
        )

        sql_str = get_sql_string(query)

        # Verify all parts are present
        assert "UPDATE" in sql_str and "SET" in sql_str and "SYS_MAP" in sql_str
        assert "WHERE" in sql_str
        assert "C_LEFT_VALUE" in sql_str and "old_value" in sql_str
        assert "N_ORDER" in sql_str and ">" in sql_str and "0" in sql_str

    def test_multiple_models_support(self) -> None:
        """Test that builders work with different model types."""
        # Test with SysMap
        sys_map_query = QueryBuilder(SysMap).where_str(SysMap.category, "test").build()
        assert "SYS_MAP" in str(sys_map_query)

        # Test with SysDict
        sys_dict_query = QueryBuilder(SysDict).where_int(SysDict.key, 42).build()
        assert "SYS_DICT" in str(sys_dict_query)

    def test_builder_isolation(self) -> None:
        """Test that different builder instances are isolated."""
        builder1 = QueryBuilder(SysMap)
        builder2 = QueryBuilder(SysMap)

        # Modify each independently
        builder1.where_str(SysMap.category, "user1")
        builder2.where_str(SysMap.category, "user2")

        query1 = builder1.build()
        query2 = builder2.build()

        sql1 = get_sql_string(query1)
        sql2 = get_sql_string(query2)

        # Each should have its own conditions
        assert "user1" in sql1
        assert "user1" not in sql2
        assert "user2" in sql2
        assert "user2" not in sql1

    def test_type_safety_protocol_compliance(self) -> None:
        """Test that soft delete models work with protocol-based typing."""
        # Both SysMap and SysDict inherit from MyBase which has in_used column
        # So they should work with soft delete methods

        sys_map_builder = soft_delete_query_builder(SysMap)
        sys_map_query = sys_map_builder.active_only().build()

        sys_dict_builder = soft_delete_query_builder(SysDict)
        sys_dict_query = sys_dict_builder.deleted_only().build()

        # Both queries should compile without errors
        assert str(sys_map_query) is not None
        assert str(sys_dict_query) is not None
