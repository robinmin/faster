# SQLAlchemy 2.1+ Async API Cheatsheet

## Setup & Configuration

```python
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, selectinload
from sqlalchemy import select, insert, update, delete, func, text, ForeignKey
from typing import Optional, Sequence
from collections.abc import AsyncGenerator

# Engine setup
engine: AsyncEngine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost/db",
    echo=True  # Set to False in production
)

# Session factory
async_session_factory = async_sessionmaker[AsyncSession](
    engine,
    expire_on_commit=False
)

# Base class for models
class Base(DeclarativeBase):
    pass

# Example model
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    email: Mapped[str | None] = mapped_column(default=None)
    age: Mapped[int | None] = mapped_column(default=None)
```

## Basic CRUD Operations

### SELECT Queries

| SQL | SQLAlchemy 2.1+ Async |
|-----|------------------------|
| `SELECT * FROM users` | `await session.scalars(select(User))` |
| `SELECT id, name FROM users` | `result = await session.execute(select(User.id, User.name))` |
| `SELECT * FROM users WHERE id = 1` | `await session.scalar(select(User).where(User.id == 1))` |
| `SELECT * FROM users WHERE name = 'John'` | `await session.scalars(select(User).where(User.name == 'John'))` |
| `SELECT * FROM users LIMIT 10` | `await session.scalars(select(User).limit(10))` |
| `SELECT * FROM users ORDER BY name` | `await session.scalars(select(User).order_by(User.name))` |
| `SELECT * FROM users ORDER BY name DESC` | `await session.scalars(select(User).order_by(User.name.desc()))` |

**Important:** `session.execute()` is NOT deprecated - mypy warnings are about the return type. Use proper type annotations!

```python
from sqlalchemy import Result, Row

async def get_users() -> Sequence[User]:
    async with async_session_factory() as session:
        # Get all users - returns ScalarResult[User]
        result = await session.scalars(select(User))
        users: Sequence[User] = result.all()

        # Get single user by ID - returns User | None
        user: User | None = await session.scalar(select(User).where(User.id == 1))

        # Get users with conditions
        adult_users_result = await session.scalars(
            select(User).where(User.age >= 18)
        )
        adult_users: Sequence[User] = adult_users_result.all()

        return users

async def get_user_data_tuples() -> Sequence[Row[tuple[int, str]]]:
    """Example of properly typed multi-column select."""
    async with async_session_factory() as session:
        # For multi-column selects, use execute() with proper typing
        result: Result[tuple[int, str]] = await session.execute(
            select(User.id, User.name)
        )
        rows: Sequence[Row[tuple[int, str]]] = result.all()
        return rows
```

### INSERT Operations

| SQL | SQLAlchemy 2.1+ Async |
|-----|------------------------|
| `INSERT INTO users (name, email) VALUES ('John', 'john@email.com')` | `session.add(User(name='John', email='john@email.com'))` |
| `INSERT INTO users (name, email) VALUES ('John', 'john@email.com') RETURNING id` | Use `session.add()` then `session.flush()` |

```python
async def create_user(name: str, email: str) -> User:
    async with async_session_factory() as session:
        # Single insert
        new_user = User(name=name, email=email)
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)  # Get generated ID
        return new_user

async def bulk_insert_users(users_data: list[dict[str, str | int | None]]) -> int:
    """Bulk insert returning number of rows inserted."""
    async with async_session_factory() as session:
        # Bulk insert using insert() statement
        result = await session.execute(
            insert(User),
            users_data  # [{"name": "John", "email": "john@email.com"}, ...]
        )
        await session.commit()
        return result.rowcount  # Number of rows inserted

async def insert_and_get_ids(users_data: list[dict[str, str]]) -> list[int]:
    """Bulk insert returning the inserted IDs (PostgreSQL specific)."""
    async with async_session_factory() as session:
        # PostgreSQL RETURNING clause
        result = await session.execute(
            insert(User).returning(User.id),
            users_data
        )
        await session.commit()
        # Extract IDs from result
        return [row[0] for row in result.fetchall()]

async def upsert_user(name: str, email: str) -> tuple[User, bool]:
    """Insert or update, returns (user, was_created)."""
    async with async_session_factory() as session:
        # Try to get existing user first
        existing_user: User | None = await session.scalar(
            select(User).where(User.email == email)
        )

        if existing_user:
            existing_user.name = name
            await session.commit()
            return existing_user, False
        else:
            new_user = User(name=name, email=email)
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)
            return new_user, True
```

### UPDATE Operations

| SQL | SQLAlchemy 2.1+ Async |
|-----|------------------------|
| `UPDATE users SET name = 'Jane' WHERE id = 1` | `await session.execute(update(User).where(User.id == 1).values(name='Jane'))` |
| `UPDATE users SET age = age + 1` | `await session.execute(update(User).values(age=User.age + 1))` |

```python
async def update_user(user_id: int, name: str) -> int:
    """Returns number of rows affected."""
    async with async_session_factory() as session:
        # Method 1: Using update() statement - preferred for bulk updates
        result = await session.execute(
            update(User).where(User.id == user_id).values(name=name)
        )
        await session.commit()
        return result.rowcount  # Number of rows affected

async def update_user_orm(user_id: int, name: str) -> User | None:
    async with async_session_factory() as session:
        # Method 2: ORM style - better for single record with complex logic
        user: User | None = await session.scalar(
            select(User).where(User.id == user_id)
        )
        if user:
            user.name = name
            await session.commit()
            return user
        return None

async def bulk_update_users(min_age: int, new_status: str) -> int:
    """Bulk update with row count."""
    async with async_session_factory() as session:
        result = await session.execute(
            update(User)
            .where(User.age >= min_age)
            .values(status=new_status)
        )
        await session.commit()
        return result.rowcount
```

### DELETE Operations

| SQL | SQLAlchemy 2.1+ Async |
|-----|------------------------|
| `DELETE FROM users WHERE id = 1` | `await session.execute(delete(User).where(User.id == 1))` |
| `DELETE FROM users WHERE age < 18` | `await session.execute(delete(User).where(User.age < 18))` |

```python
async def delete_user(user_id: int) -> int:
    """Delete user and return number of rows affected."""
    async with async_session_factory() as session:
        # Method 1: Using delete() statement - preferred for bulk deletes
        result = await session.execute(delete(User).where(User.id == user_id))
        await session.commit()
        return result.rowcount  # 0 if user not found, 1 if deleted

async def delete_user_orm(user_id: int) -> bool:
    """ORM style delete - returns whether user was found and deleted."""
    async with async_session_factory() as session:
        # Method 2: ORM style - returns whether user was found and deleted
        user: User | None = await session.scalar(
            select(User).where(User.id == user_id)
        )
        if user:
            await session.delete(user)
            await session.commit()
            return True
        return False

async def delete_inactive_users(days_inactive: int) -> int:
    """Bulk delete with row count."""
    from datetime import datetime, timedelta

    async with async_session_factory() as session:
        cutoff_date = datetime.now() - timedelta(days=days_inactive)
        result = await session.execute(
            delete(User).where(User.last_login < cutoff_date)
        )
        await session.commit()
        return result.rowcount

async def delete_and_return_deleted(user_ids: list[int]) -> list[User]:
    """Delete users and return what was deleted (PostgreSQL specific)."""
    async with async_session_factory() as session:
        # PostgreSQL RETURNING clause
        result = await session.execute(
            delete(User)
            .where(User.id.in_(user_ids))
            .returning(User.id, User.name, User.email)
        )
        await session.commit()

        # Convert results to User objects (partial)
        deleted_users = []
        for row in result.fetchall():
            user = User(id=row[0], name=row[1], email=row[2])
            deleted_users.append(user)

        return deleted_users
```

## Advanced Queries

### Filtering & Conditions

| SQL | SQLAlchemy 2.1+ Async |
|-----|------------------------|
| `WHERE name = 'John' AND age > 18` | `.where(User.name == 'John', User.age > 18)` |
| `WHERE name = 'John' OR name = 'Jane'` | `.where((User.name == 'John') | (User.name == 'Jane'))` |
| `WHERE name IN ('John', 'Jane')` | `.where(User.name.in_(['John', 'Jane']))` |
| `WHERE name LIKE '%john%'` | `.where(User.name.ilike('%john%'))` |
| `WHERE age IS NULL` | `.where(User.age.is_(None))` |
| `WHERE age IS NOT NULL` | `.where(User.age.is_not(None))` |

### Aggregations & Functions

| SQL | SQLAlchemy 2.1+ Async |
|-----|------------------------|
| `SELECT COUNT(*) FROM users` | `await session.scalar(select(func.count(User.id)))` |
| `SELECT COUNT(DISTINCT name) FROM users` | `await session.scalar(select(func.count(User.name.distinct())))` |
| `SELECT AVG(age) FROM users` | `await session.scalar(select(func.avg(User.age)))` |
| `SELECT MAX(age), MIN(age) FROM users` | `await session.execute(select(func.max(User.age), func.min(User.age)))` |

```python
async def get_user_stats() -> dict[str, int | float | None]:
    async with async_session_factory() as session:
        # Count users - scalar() for single values
        count: int | None = await session.scalar(select(func.count(User.id)))

        # Average age - returns float | None
        avg_age: float | None = await session.scalar(select(func.avg(User.age)))

        # Multiple aggregations - use execute() for multiple columns
        result: Result[tuple[int, float | None, int | None]] = await session.execute(
            select(
                func.count(User.id).label('total_users'),
                func.avg(User.age).label('avg_age'),
                func.max(User.age).label('max_age')
            )
        )
        stats_row: Row[tuple[int, float | None, int | None]] | None = result.first()

        return {
            'count': count or 0,
            'avg_age': avg_age,
            'stats': stats_row._asdict() if stats_row else None,
        }
```

### GROUP BY & HAVING

| SQL | SQLAlchemy 2.1+ Async |
|-----|------------------------|
| `SELECT age, COUNT(*) FROM users GROUP BY age` | `select(User.age, func.count()).group_by(User.age)` |
| `SELECT age, COUNT(*) FROM users GROUP BY age HAVING COUNT(*) > 1` | `select(User.age, func.count()).group_by(User.age).having(func.count() > 1)` |

```python
async def get_age_distribution() -> Sequence[Row[tuple[int | None, int]]]:
    async with async_session_factory() as session:
        result: Result[tuple[int | None, int]] = await session.execute(
            select(User.age, func.count().label('count'))
            .group_by(User.age)
            .having(func.count() > 1)
        )
        return result.all()
```

## Relationships & Joins

```python
from sqlalchemy.orm import relationship

# Model with relationships
class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    # Relationship
    user: Mapped["User"] = relationship(back_populates="posts")

# Add to User model (update the User class above)
# User.posts: Mapped[list["Post"]] = relationship(back_populates="user")
```

### JOIN Operations

| SQL | SQLAlchemy 2.1+ Async |
|-----|------------------------|
| `SELECT * FROM users u JOIN posts p ON u.id = p.user_id` | `select(User).join(Post)` |
| `SELECT * FROM users u LEFT JOIN posts p ON u.id = p.user_id` | `select(User).outerjoin(Post)` |

```python
async def get_users_with_posts() -> Sequence[User]:
    async with async_session_factory() as session:
        # Eager loading with selectinload
        result = await session.scalars(
            select(User).options(selectinload(User.posts))
        )
        return result.all()

async def get_users_and_posts_join() -> Sequence[Row[tuple[User, Post]]]:
    async with async_session_factory() as session:
        # Explicit join - returns tuples of (User, Post)
        result: Result[tuple[User, Post]] = await session.execute(
            select(User, Post).join(Post)
        )
        return result.all()
```

## Getting Row Counts and Affected Rows

### Key Properties and Methods

```python
from sqlalchemy import CursorResult

async def demonstrate_row_counts() -> None:
    async with async_session_factory() as session:
        # INSERT - bulk insert with row count
        result: CursorResult[Any] = await session.execute(
            insert(User),
            [{"name": f"User{i}", "email": f"user{i}@example.com"} for i in range(5)]
        )
        print(f"Inserted {result.rowcount} rows")

        # UPDATE - with row count
        result = await session.execute(
            update(User).where(User.name.like("User%")).values(status="active")
        )
        print(f"Updated {result.rowcount} rows")

        # DELETE - with row count
        result = await session.execute(
            delete(User).where(User.status == "inactive")
        )
        print(f"Deleted {result.rowcount} rows")

        await session.commit()

# For PostgreSQL - get inserted/updated/deleted data back
async def postgres_returning_examples() -> None:
    async with async_session_factory() as session:
        # INSERT with RETURNING
        result = await session.execute(
            insert(User)
            .values(name="John", email="john@example.com")
            .returning(User.id, User.name)
        )
        new_row = result.fetchone()
        if new_row:
            print(f"Created user ID: {new_row[0]}, Name: {new_row[1]}")

        # UPDATE with RETURNING
        result = await session.execute(
            update(User)
            .where(User.name == "John")
            .values(name="John Updated")
            .returning(User.id, User.name)
        )
        updated_rows = result.fetchall()
        print(f"Updated {len(updated_rows)} users")

        # DELETE with RETURNING
        result = await session.execute(
            delete(User)
            .where(User.name.like("%test%"))
            .returning(User.id, User.name)
        )
        deleted_rows = result.fetchall()
        print(f"Deleted users: {[row[1] for row in deleted_rows]}")

        await session.commit()

# Check if operation affected any rows
async def conditional_operations() -> bool:
    async with async_session_factory() as session:
        # Try to update, check if anything was actually updated
        result = await session.execute(
            update(User)
            .where(User.id == 999)  # Probably doesn't exist
            .values(name="Updated")
        )

        if result.rowcount == 0:
            print("No user found to update")
            return False
        else:
            print(f"Updated {result.rowcount} user(s)")
            await session.commit()
            return True
```

## Raw SQL & Transactions

### Raw SQL

```python
async def execute_raw_sql() -> Sequence[Row[Any]]:
    async with async_session_factory() as session:
        # Raw SQL query - execute() is the correct method for raw SQL
        result: Result[Any] = await session.execute(
            text("SELECT * FROM users WHERE age > :age"),
            {"age": 18}
        )
        return result.fetchall()

async def execute_raw_insert() -> None:
    async with async_session_factory() as session:
        # Raw SQL insert - execute() is correct here
        await session.execute(
            text("INSERT INTO users (name, email) VALUES (:name, :email)"),
            {"name": "John", "email": "john@email.com"}
        )
        await session.commit()
```

### Transactions

```python
async def transaction_example() -> None:
    async with async_session_factory() as session:
        try:
            # Multiple operations in transaction
            user = User(name="John", email="john@email.com")
            session.add(user)
            await session.flush()  # Get user.id without committing

            post = Post(title="My Post", user_id=user.id)
            session.add(post)

            await session.commit()  # Commit all changes
        except Exception:
            await session.rollback()  # Rollback on error
            raise

# Using begin() for explicit transaction control
async def explicit_transaction() -> User:
    async with async_session_factory.begin() as session:
        # Auto-commits on success, auto-rollbacks on exception
        user = User(name="Jane", email="jane@email.com")
        session.add(user)
        await session.flush()  # Ensure we have the ID
        # No need to call commit() or rollback()
        return user
```

## Common Patterns & Best Practices

### Session Context Managers

```python
# Recommended pattern
async def get_user_by_id(user_id: int) -> User | None:
    async with async_session_factory() as session:
        return await session.scalar(select(User).where(User.id == user_id))

# For multiple operations
async def create_user_with_posts(
    name: str,
    email: str,
    post_titles: list[str]
) -> User:
    async with async_session_factory.begin() as session:
        user = User(name=name, email=email)
        session.add(user)
        await session.flush()  # Get user ID

        for title in post_titles:
            post = Post(title=title, user_id=user.id)
            session.add(post)

        # Auto-commits
        return user
```

### Error Handling

```python
from sqlalchemy.exc import IntegrityError, NoResultFound

async def safe_create_user(name: str, email: str) -> User:
    try:
        async with async_session_factory.begin() as session:
            user = User(name=name, email=email)
            session.add(user)
            await session.flush()  # Ensure we get the ID
            return user
    except IntegrityError as e:
        # Handle duplicate key, etc.
        raise ValueError("User with this email already exists") from e

async def get_user_or_404(user_id: int) -> User:
    async with async_session_factory() as session:
        user: User | None = await session.scalar(
            select(User).where(User.id == user_id)
        )
        if not user:
            raise NoResultFound(f"User {user_id} not found")
        return user
```

### Pagination

```python
from dataclasses import dataclass

@dataclass
class PaginatedResult:
    users: Sequence[User]
    total: int
    page: int
    per_page: int
    pages: int

async def get_users_paginated(page: int = 1, per_page: int = 10) -> PaginatedResult:
    async with async_session_factory() as session:
        offset = (page - 1) * per_page

        # Get users for current page
        users_result = await session.scalars(
            select(User)
            .order_by(User.id)
            .offset(offset)
            .limit(per_page)
        )
        users: Sequence[User] = users_result.all()

        # Get total count
        total: int | None = await session.scalar(select(func.count(User.id)))
        total_count = total or 0

        return PaginatedResult(
            users=users,
            total=total_count,
            page=page,
            per_page=per_page,
            pages=(total_count + per_page - 1) // per_page
        )
```

## Key Points for ruff/mypy Compliance

1. **`session.execute()` is NOT deprecated** - mypy warnings are about return types
2. **Use proper type annotations** for `Result`, `Row`, and return types
3. **Import from `collections.abc`** instead of `typing` for `Sequence`, `AsyncGenerator`
4. **Use `str | None`** instead of `Optional[str]` (modern union syntax)
5. **Add `from __future__ import annotations`** for forward references
6. **Type your session factory properly**: `async_sessionmaker[AsyncSession]`

## Method Usage Guidelines

**Use `session.scalars()`** when:
- Selecting ORM objects: `select(User)`
- You want a `ScalarResult[Model]` that you can iterate over
- Working with single-column results

**Use `session.scalar()`** when:
- Getting a single value: `func.count()`, `func.avg()`, etc.
- Getting a single object: `select(User).where(...).limit(1)`
- Returns `T | None`

**Use `session.execute()`** when:
- Multi-column selects: `select(User.id, User.name)`
- Raw SQL with `text()`
- Bulk operations: `insert()`, `update()`, `delete()`
- Complex queries where you need the full `Result` object
- Returns `Result[tuple[...]]` for multi-column, `Result[Any]` for raw SQL

## Key Differences from SQLAlchemy 1.x

1. **Always use `select()` for queries** instead of `session.query()`
2. **Use `session.scalars()`** for single column results
3. **Use `session.execute()`** for multiple columns or complex queries
4. **Use `session.scalar()`** for single row, single column results
5. **All database operations are async** and need `await`
6. **Use `selectinload()` and `joinedload()`** for eager loading relationships
7. **Explicit session management** with context managers is recommended
8. **Proper type annotations** are essential for mypy compliance
