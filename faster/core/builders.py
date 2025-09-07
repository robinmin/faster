"""
Query builders for type-safe database operations.

This module provides query builders with fluent interfaces for building
SQLAlchemy queries with proper type safety and simple APIs.

Example usage:
    from faster.core.builders import qb, ub, db

    # Simple and clean approach
    users = (qb(User)
             .where(User.name, "John")
             .where(User.age, 25)
             .active_only()
             .build())

    # Update operations
    update_query = (ub(User)
                   .set(User.name, "Updated Name")
                   .where(User.id, 123)
                   .build())

    # Delete operations
    delete_query = (db(User)
                   .where(User.status, "inactive")
                   .build())
"""

from typing import Any, Generic, Protocol, TypeVar, cast

from sqlalchemy import delete, select, update
from sqlalchemy.sql.dml import Delete, Update
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
TValue = TypeVar("TValue")


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
    # Core Where Method - Simple and Flexible
    ###########################################################################

    def where(self, column: Any, value: Any) -> Self:
        """
        Add an equality condition to the query.

        Args:
            column: The column to filter on
            value: The value to compare against

        Returns:
            Self for method chaining
        """
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
        if not values:
            raise ValueError("Values list cannot be empty for IN condition")
        condition = column.in_(values)
        self._query = self._query.where(condition)
        return self

    def where_like(self, column: Any, pattern: str) -> Self:
        """Add a LIKE condition to the query."""
        condition = column.like(pattern)
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

    Provides a clean, fluent interface for building SELECT queries with
    proper type safety and method chaining.

    Example:
        query = qb(User).where(User.name, "John").where(User.age, 25).build()
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
        if desc:
            self._query = self._query.order_by(column.desc())
        else:
            self._query = self._query.order_by(column)
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

    def set(self, column: Any, value: Any) -> Self:
        """Set a column value.

        Args:
            column: The column to set
            value: The value to set

        Returns:
            Self for method chaining
        """
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


def qb(model: type[TModel]) -> QueryBuilder[TModel]:
    """Create a QueryBuilder for any model type."""
    return QueryBuilder(model)


def db(model: type[TModel]) -> DeleteBuilder[TModel]:
    """Create a DeleteBuilder for any model type."""
    return DeleteBuilder(model)


def ub(model: type[TModel]) -> UpdateBuilder[TModel]:
    """Create an UpdateBuilder for any model type."""
    return UpdateBuilder(model)


# Backward compatibility aliases
query_builder = qb
delete_builder = db
update_builder = ub
