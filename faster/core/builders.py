"""
Query builders for type-safe database operations.

This module provides sophisticated query builders with fluent interfaces
for building SQLAlchemy queries with proper type safety and elegant APIs.

Example usage:
    from faster.core.builders import QueryBuilder, query_builder, soft_delete_query_builder

    # Explicit method approach
    users = (QueryBuilder(User)
             .where_str(User.name, "John")
             .where_int(User.age, 25)
             .active_only()
             .build())

    # Generic method approach
    users = (query_builder(User)
             .where(User.name, "John")
             .where(User.age, 25)
             .where(User.active, True)
             .build())

    # Soft delete operations (type-safe)
    active_users = (soft_delete_query_builder(User)
                   .where(User.role, "admin")
                   .active_only()  # Only available for soft delete models
                   .build())
"""

from typing import Any, Generic, Protocol, TypeVar, cast, overload

from sqlalchemy import delete, select, update
from sqlalchemy.sql.dml import Delete, Update
from sqlalchemy.sql.elements import ColumnClause, ColumnElement
from sqlalchemy.sql.selectable import Select
from typing_extensions import Self

###############################################################################
# Type System and Protocols
###############################################################################

# Type variable for model types
TModel = TypeVar("TModel")


# Protocol for models that support soft delete operations
class SoftDeleteModel(Protocol):
    """Protocol for models that have an in_used column for soft deletes."""

    in_used: int


# Type variable for soft delete models
TSoftDeleteModel = TypeVar("TSoftDeleteModel", bound=SoftDeleteModel)

# Type variable for column values
TValue = TypeVar("TValue", str, int, bool, float)


###############################################################################
# Base Mixin for Shared Where Clause Logic
###############################################################################


class WhereClauseMixin(Generic[TModel]):
    """
    Mixin providing shared where clause logic for query builders.

    This eliminates code duplication between QueryBuilder and DeleteBuilder
    by providing common filtering methods.
    """

    # These will be implemented by concrete classes
    _query: Any
    _model: type[TModel]

    ###########################################################################
    # Explicit Type Methods (Clear and Simple)
    ###########################################################################

    def where_str(self, column: Any, value: str) -> Self:
        """Add a string equality condition to the query."""
        condition = cast(ColumnElement[str], column) == value
        self._query = self._query.where(condition)
        return self

    def where_int(self, column: Any, value: int) -> Self:
        """Add an integer equality condition to the query."""
        condition = cast(ColumnElement[int], column) == value
        self._query = self._query.where(condition)
        return self

    def where_bool(self, column: Any, value: bool) -> Self:
        """Add a boolean equality condition to the query."""
        condition = column == value
        self._query = self._query.where(condition)
        return self

    def where_float(self, column: Any, value: float) -> Self:
        """Add a float equality condition to the query."""
        condition = cast(ColumnElement[float], column) == value
        self._query = self._query.where(condition)
        return self

    ###########################################################################
    # Generic Where Method (Elegant and Flexible)
    ###########################################################################

    @overload
    def where(self, column: ColumnElement[str], value: str) -> Self: ...

    @overload
    def where(self, column: ColumnElement[int], value: int) -> Self: ...

    @overload
    def where(self, column: ColumnElement[bool], value: bool) -> Self: ...

    @overload
    def where(self, column: ColumnElement[float], value: float) -> Self: ...

    @overload
    def where(self, column: Any, value: TValue) -> Self: ...

    def where(self, column: Any, value: str | int | bool | float) -> Self:
        """
        Generic where method with automatic type detection.

        Args:
            column: The column to filter on
            value: The value to compare against

        Returns:
            Self for method chaining
        """
        # Delegate to explicit methods based on value type
        if isinstance(value, str):
            return self.where_str(column, value)
        if isinstance(value, int):
            return self.where_int(column, value)
        if isinstance(value, bool):
            return self.where_bool(column, value)
        if isinstance(value, float):
            return self.where_float(column, value)
        # Fallback for custom conditions
        condition = column == value
        self._query = self._query.where(condition)
        return self

    ###########################################################################
    # Advanced Condition Methods
    ###########################################################################

    def where_custom(self, condition: Any) -> Self:
        """Add a custom condition to the query."""
        self._query = self._query.where(condition)
        return self

    def where_in(self, column: Any, values: list[Any]) -> Self:
        """Add an IN condition to the query."""
        condition = column.in_(values)
        self._query = self._query.where(condition)
        return self

    def where_like(self, column: Any, pattern: str) -> Self:
        """Add a LIKE condition to the query."""
        condition = cast(ColumnElement[str], column).like(pattern)
        self._query = self._query.where(condition)
        return self

    def where_gt(self, column: Any, value: int | float) -> Self:
        """Add a greater than condition to the query."""
        condition = column > value
        self._query = self._query.where(condition)
        return self

    def where_lt(self, column: Any, value: int | float) -> Self:
        """Add a less than condition to the query."""
        condition = column < value
        self._query = self._query.where(condition)
        return self

    def where_gte(self, column: Any, value: int | float) -> Self:
        """Add a greater than or equal condition to the query."""
        condition = column >= value
        self._query = self._query.where(condition)
        return self

    def where_lte(self, column: Any, value: int | float) -> Self:
        """Add a less than or equal condition to the query."""
        condition = column <= value
        self._query = self._query.where(condition)
        return self


###############################################################################
# Main QueryBuilder Class with Hybrid API
###############################################################################


class QueryBuilder(WhereClauseMixin[TModel], Generic[TModel]):
    """
    A generic, type-safe query builder for SQLAlchemy/SQLModel.

    Provides both explicit methods (where_str, where_int) and generic methods (where)
    for maximum flexibility while maintaining type safety.
    """

    def __init__(self, model: type[TModel]) -> None:
        """Initialize the query builder with a model type."""
        self._model = model
        self._query = select(model)

    ###########################################################################
    # Soft Delete Methods (Protocol-based Type Safety)
    ###########################################################################

    def active_only(self: "QueryBuilder[TSoftDeleteModel]") -> "QueryBuilder[TSoftDeleteModel]":
        """Filter for active records (requires model with in_used column)."""
        condition = self._model.in_used == 1
        self._query = self._query.where(condition)
        return self

    def deleted_only(self: "QueryBuilder[TSoftDeleteModel]") -> "QueryBuilder[TSoftDeleteModel]":
        """Filter for deleted records (requires model with in_used column)."""
        condition = self._model.in_used == 0
        self._query = self._query.where(condition)
        return self

    ###########################################################################
    # Query Modification Methods
    ###########################################################################

    def order_by(self, column: Any, desc: bool = False) -> Self:
        """Add ordering to the query."""
        order_column = cast(ColumnClause[Any], column)
        if desc:
            self._query = self._query.order_by(order_column.desc())
        else:
            self._query = self._query.order_by(order_column)
        return self

    def limit(self, count: int) -> Self:
        """Add a limit to the query."""
        self._query = self._query.limit(count)
        return self

    def offset(self, count: int) -> Self:
        """Add an offset to the query."""
        self._query = self._query.offset(count)
        return self

    ###########################################################################
    # Build Methods
    ###########################################################################

    def build(self) -> Select[tuple[TModel, ...]]:
        """Build and return the final query."""
        return cast(Select[tuple[TModel, ...]], self._query)

    def build_delete(self) -> Delete:
        """Build a delete query with the current conditions."""
        delete_query = delete(self._model)
        # Extract where conditions from select query
        if hasattr(self._query, "whereclause") and self._query.whereclause is not None:
            delete_query = delete_query.where(self._query.whereclause)
        return delete_query


###############################################################################
# Specialized DeleteBuilder
###############################################################################


class DeleteBuilder(WhereClauseMixin[TModel], Generic[TModel]):
    """A specialized builder for DELETE queries."""

    def __init__(self, model: type[TModel]) -> None:
        """Initialize the delete builder with a model type."""
        self._model = model
        self._query = delete(model)

    def build(self) -> Delete:
        """Build and return the final delete query."""
        return cast(Delete, self._query)


###############################################################################
# Specialized UpdateBuilder
###############################################################################


class UpdateBuilder(WhereClauseMixin[TModel], Generic[TModel]):
    """A specialized builder for UPDATE queries."""

    def __init__(self, model: type[TModel]) -> None:
        """Initialize the update builder with a model type."""
        self._model = model
        self._query = update(model)
        self._values: dict[str, Any] = {}

    ###########################################################################
    # Update-specific Methods
    ###########################################################################

    def set_str(self, column: Any, value: str) -> Self:
        """Set a string column value."""
        self._query = self._query.values({column.key: value})
        return self

    def set_int(self, column: Any, value: int) -> Self:
        """Set an integer column value."""
        self._query = self._query.values({column.key: value})
        return self

    def set_bool(self, column: Any, value: bool) -> Self:
        """Set a boolean column value."""
        self._query = self._query.values({column.key: value})
        return self

    def set_float(self, column: Any, value: float) -> Self:
        """Set a float column value."""
        self._query = self._query.values({column.key: value})
        return self

    @overload
    def set(self, column: ColumnElement[str], value: str) -> Self: ...
    @overload
    def set(self, column: ColumnElement[int], value: int) -> Self: ...
    @overload
    def set(self, column: ColumnElement[bool], value: bool) -> Self: ...
    @overload
    def set(self, column: ColumnElement[float], value: float) -> Self: ...
    @overload
    def set(self, column: Any, value: TValue) -> Self: ...

    def set(self, column: Any, value: str | int | bool | float) -> Self:
        """Generic set method with automatic type detection."""
        if isinstance(value, str):
            return self.set_str(column, value)
        if isinstance(value, int):
            return self.set_int(column, value)
        if isinstance(value, bool):
            return self.set_bool(column, value)
        if isinstance(value, float):
            return self.set_float(column, value)
        # Fallback
        self._query = self._query.values({column.key: value})
        return self

    def set_values(self, **values: Any) -> Self:
        """Set multiple column values at once."""
        self._query = self._query.values(**values)
        return self

    def increment(self, column: Any, amount: int | float = 1) -> Self:
        """Increment a numeric column by the specified amount."""
        self._query = self._query.values({column.key: column + amount})
        return self

    def decrement(self, column: Any, amount: int | float = 1) -> Self:
        """Decrement a numeric column by the specified amount."""
        self._query = self._query.values({column.key: column - amount})
        return self

    def build(self) -> Update:
        """Build and return the final update query."""
        return cast(Update, self._query)


###############################################################################
# Convenience Factory Functions
###############################################################################


def query_builder(model: type[TModel]) -> QueryBuilder[TModel]:
    """Create a QueryBuilder for any model type."""
    return QueryBuilder(model)


def soft_delete_query_builder(model: type[TSoftDeleteModel]) -> QueryBuilder[TSoftDeleteModel]:
    """Create a QueryBuilder for models that support soft delete operations."""
    return QueryBuilder(model)


def delete_builder(model: type[TModel]) -> DeleteBuilder[TModel]:
    """Create a DeleteBuilder for any model type."""
    return DeleteBuilder(model)


def update_builder(model: type[TModel]) -> UpdateBuilder[TModel]:
    """Create an UpdateBuilder for any model type."""
    return UpdateBuilder(model)


###############################################################################
# Convenience Aliases for Different Coding Styles
###############################################################################

# For users who prefer class instantiation
QB = QueryBuilder
DB = DeleteBuilder
UB = UpdateBuilder

# For users who prefer functional style
qb = query_builder
sdb = soft_delete_query_builder
db = delete_builder
ub = update_builder
