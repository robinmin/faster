# 🚀 Faster Framework - Claude Code Instructions

[![Framework](https://img.shields.io/badge/Framework-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![Type Safety](https://img.shields.io/badge/Type_Safety-SQLModel-blue.svg)](https://sqlmodel.tiangolo.com/)
[![Database](https://img.shields.io/badge/Database-PostgreSQL-336791.svg)](https://www.postgresql.org/)

## Quick Navigation
- [🎯 Purpose & Overview](#-purpose--overview)
- [⚡ Quick Reference](#-quick-reference)
- [🔧 Core Tasks](#-core-tasks)
- [📐 Architecture Principles](#-architecture-principles)
- [🗄️ Database Patterns](#%EF%B8%8F-database-patterns)
- [🔒 Security & Authentication](#-security--authentication)
- [🧪 Testing Guidelines](#-testing-guidelines)
- [⚙️ MCP Integration](#%EF%B8%8F-mcp-integration)
- [📝 Code Quality Standards](#-code-quality-standards)

---

## 🎯 Purpose & Overview

**Faster** is a tiny web framework providing a solid foundation for building scalable web applications based on FastAPI. It eliminates infrastructure setup complexity, allowing developers to focus on business logic.

### 🌟 Key Features
- **🚄 FastAPI Core**: High performance async web framework
- **🗄️ Database Integration**: SQLModel/SQLAlchemy with connection pooling
- **⚡ Redis Management**: Multi-provider support with pub/sub capabilities
- **🔐 Authentication**: Supabase Auth integration
- **🔑 Authorizations**: Dynamic RBAC(based on endpoints tag and tag_role/user_role mapping)
- **🧩 Plugin Mechanisms**: Extendable plugin system for custom functionality
- **⚙️ Configuration**: Environment-based with Pydantic Settings
- **📊 Logging**: Structured logging with multiple formats
- **🛡️ Error Handling**: Comprehensive exception mechanisms
- **🧪 Testing**: Production-ready pytest setup
- **🚀 Deployment**: Production-ready server configuration

[↑ Back to Top](#quick-navigation)

---

## ⚡ Quick Reference

### Essential Commands
```bash
make run          # Start development server
make test         # Run test suite
make lint         # Code quality checks
make autofix      # Auto-fix linting issues
```

### Key Principles (YAGNI + DRY + KISS + SRP)
- ✅ Single responsibility per module
- ✅ Business logic in services only
- ✅ Thin repositories (data access only)
- ✅ Async/await for I/O operations
- ✅ Strict type hints everywhere

[↑ Back to Top](#quick-navigation)

---

## ⚙️ MCP Integration

**🤖 AI-Powered Development**: Always use Context7 MCP tools for:
- 📚 Library documentation lookup
- 🔧 Code generation assistance
- ⚙️ Configuration setup guidance
- 📖 API reference queries

> **Auto-Activation**: Context7 tools are automatically used without explicit requests for library/API documentation needs.

[↑ Back to Top](#quick-navigation)

---

## 🔧 Core Tasks

**🛠️ Makefile-Driven Workflow**: All project operations use the `make` tool for consistency and automation.

### 🚀 Development Commands
```bash
make run                            # Run the FastAPI application
make autofix                        # Automatically fix linting errors
make lint                           # Lint the code
make test                           # Run tests
```

### 🗄️ Database Management
```bash
make db-upgrade                     # Apply all database migrations
make db-migrate m="description"     # Create new migration (e.g., make db-migrate m="create users table")
make db-downgrade                   # Downgrade database by one revision
make db-version                     # Show current database revision
```

### 🧹 Maintenance
```bash
make clean                          # Clean up build artifacts and cached files
make lock                           # Update the lock file
```

> **💡 Pro Tip**: Always run `make autofix` before committing to ensure code quality standards.

[↑ Back to Top](#quick-navigation)

---

## 📐 Architecture Principles

### 🎯 Core Design Philosophy

**SOLID + Clean Architecture**: Following Domain-Driven Responsibility Patterns (DRP)

#### 🏗️ Key Principles (YAGNI + DRY + KISS + SRP)
- **🎯 YAGNI** (Occam's Razor): Remove code for non-existent requirements
- **🔄 DRY** (Don't repeat yourself): Eliminate redundant session handling patterns
- **💎 KISS**: Simplify method signatures and implementations
- **📦 SRP**: Each method does one thing clearly

#### ⚡ Development Standards
- ✅ **Single responsibility** per module
- ✅ **Type hints everywhere** (strict typing)
- ✅ **Async/await** for I/O-bound operations
- ✅ ** Strict linter compliance** (ruff, mypy, basedpyright)
- ❌ **No `# type: ignore`** comments (solve the root cause)

### 🏛️ Module Responsibility Structure (DRP)

| Module | Responsibility | What Goes Here |
|--------|---------------|----------------|
| **📄 models.py** | Non-database entities | Pydantic models, DTOs |
| **🗄️ schemas.py** | Database entities | SQLModel classes |
| **📚 repositories.py** | Data access layer | CRUD operations only |
| **⚙️ services.py** | Business logic | Orchestration & rules |
| **🌐 routers.py** | API endpoints | Request/response handling |
| **🔧 middlewares.py** | Request processing | Cross-cutting concerns |
| **🛠️ utilities.py** | Pure functions | Helper & utility functions |

> **🎨 Architecture Goal**: Thin layers with clear boundaries - fat services, thin the rest, and provide utilities maximum possible reusability

[↑ Back to Top](#quick-navigation)

---

## 🗄️ Database Patterns

### 📊 Access Patterns (repositories.py)

#### 🔧 Technology Stack Priority
1. **🥇 SQLModel** - Primary choice for database access
2. **🥈 SQLAlchemy** - Fallback only when SQLModel unsupported

#### 💾 Session Management
- **🔄 `get_transaction()`** - Auto-managed transactions
- **🔓 `get_session()`** - Manual transaction control
- **⚡ `DatabaseManager.execute_raw_query()`** - Raw SQL execution

#### 🛡️ Data Safety Rules
- **🚫 No Hard Deletes** - Always use soft deletes
- **📝 Soft Delete Pattern**: `in_used=0` + `deleted_at` timestamp
- **⏰ Update Tracking**: Always update `updated_at` on modifications

### 🏗️ Schema Definition (schemas.py)

#### 📋 Naming Conventions
**Database Field Pattern**: `{TYPE_PREFIX}_{FIELD_NAME}`

| Type | Prefix | Example |
|------|--------|---------|
| **🔤 String** | `C_` | `C_USERNAME` |
| **🔢 Number** | `N_` | `N_AGE` |
| **✅ Boolean** | `B_` | `B_ACTIVE` |
| **📅 Date/Time** | `D_` | `D_CREATED_AT` |

#### 💻 Implementation Example
```python
# ✅ Correct Schema Definition
class User(MyBase, table=True):
    username: str = Field(
        max_length=64, sa_column_kwargs={"name": "C_USERNAME"}
    )
    age: int = Field(
        sa_column_kwargs={"name": "N_AGE"}
    )
    is_active: bool = Field(
        default=True, sa_column_kwargs={"name": "B_ACTIVE"}
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column_kwargs={"name": "D_CREATED_AT"}
    )
```

#### ⚠️ Schema Rules
- ✅ **Inherit from `MyBase`** always
- ✅ **Separate member variables** from DB field names
- ✅ **Use UPPERCASE snake_case** for DB fields
- ❌ **Avoid TEXT fields** when possible

[↑ Back to Top](#quick-navigation)

---

## 🔒 Security & Authentication

### 🔐 Authentication Flow Architecture
```
External Auth ➜ Proxy Layer ➜ Repositories ➜ Services ➜ Routers
```

**🏗️ Layer Responsibilities**:
- **🌐 Proxy Layer**: All external auth service access
- **📚 Repositories**: All database access
- **⚙️ Services**: Authentication business logic
- **🔌 Routers**: Endpoint definitions

### 🔄 Upsert Patterns

#### 📄 Single Records
1. **Query** for existing record
2. **Update** if exists, **Insert** if not
3. **Soft delete** instead of hard delete

#### 📚 Collection Records
1. **Soft delete** all existing records (`in_used=0`)
2. **Insert** new collection
3. **Update** `updated_at` timestamps

> **🛡️ Security Rule**: Never use hard deletes - always maintain audit trails.

[↑ Back to Top](#quick-navigation)

---

## 📝 Code Quality Standards

### 🔍 Linting & Type Checking
**🎯 Zero Tolerance Policy**: All code must pass without exceptions

```bash
# Required Checks
ruff check .        # Code style & best practices
mypy .             # Static type checking
basedpyright .     # Additional type analysis
```

#### ⚠️ Quality Rules
- ✅ **PEP 8 compliance** mandatory
- ✅ **Type hints** for all functions/variables
- ❌ **No `# type: ignore`** (fix root cause instead)
- ✅ **Follow project style guides**

### 📊 Logging Standards

#### 🎯 Logging Philosophy: "Signal vs Noise"
- **✅ Log**: Errors, warnings, important business events
- **❌ Avoid**: Excessive logging in normal flows
- **📝 Context**: Include troubleshooting information

#### 📈 Log Levels
- **🔴 ERROR**: System failures, exceptions
- **🟡 WARNING**: Recoverable issues, deprecations
- **🔵 INFO**: Important business events
- **🟢 DEBUG**: Development debugging (sparingly)

[↑ Back to Top](#quick-navigation)

---

## 🧪 Testing Guidelines

### 🎯 Testing Philosophy: Test-Driven Development (TDD)
- **pytest**: For backend testing
- **pytest-playwright**: For frontend testing
- **pytest-httpx**: For HTTP requests/RESTful API testing
- **Test DB**: Instead of mocking, use in-memory URI 'sqlite+aiosqlite:///:memory:' for testing
- **Test Redis**: Instead of mocking, use provider-'fake' for testing

#### 🔄 TDD Workflow
1. **🔴 Red**: Write failing test first
2. **🟢 Green**: Write minimal code to pass
3. **🔵 Refactor**: Improve code quality

### 🏗️ Testing Architecture

#### 🛠️ Framework & Tools
- **🧪 Framework**: pytest
- **📊 Coverage Target**: 80%+ for business logic
- **📁 Structure**: `tests/` mirrors `app/` structure

#### 🔧 Testing Patterns
```python
# ✅ Correct Test Structure
def test_service_method():
    # Arrange
    user = UserFactory()

    # Act
    result = user_service.process(user)

    # Assert
    assert result.is_valid
```

#### 🏗️ Test Organization
- **🔧 Fixtures**: DB setup/teardown with pytest
- **🎭 Mocking**: External services (APIs, storage)
- **📋 Requirements**: All tests pass before commits

> **🎯 Testing Goal**: High confidence in business logic through comprehensive test coverage.

[↑ Back to Top](#quick-navigation)
