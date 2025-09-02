## Prompts

This doc will contains all relevant prompts I used with LLM for this project.
[TOC]

### 1, Generate SPA DevAdmin page

#### Purpose

For a better development expierence, I need a simple and single file application for my daily development works.

#### requirement deatails

- This single file application is a HTML file dev-admin.html, which contains the raw source code of JS, CSS and HTML directly instead of with any build tool like webpack or anything else. Simple code, simple maintainaince, simple like.
- Technical stacks:
  - Raw / vanila JS
  - HTMX as the mechanism to interact with server side
  - import sophisticated external JS/CSS and SVG based icon library via CDN URL.
  - recommend to use tailwind CSS as the CSS framework.
  - Use supabase-js to do all authentication works and then work with our backend server.
- Funitionalities:
  - when user not login, show 3 type login ways: Google OAuth, Github OAuth link and user/pssword;
  - After user login, show action links at the top-right cornor; The ceter part always show the content related to current action(Current actions includes: dashboard, profile and logout, so far).
- Backeend Server URLs:
  - GET /auth/login: notification place after user login with Supabase Auth
  - GET /auth/logout: notification place after user logout with Supabase Auth
  - GET /auth/onboarding: the first page once user login
  - GET /auth/profile: show current user's profile information

#### Steps & Strategy

- You should always work in two-step strategy: After understand the requirements, you should work out a solid plan first. In case of any unclarification, you shoudl comfirm with me.
- After all clarification done, with my order to start the generate the source code.

#### I got from Claude.ai

```markdown
# Development Admin Application - Detailed Requirements

## Technical Specifications

### **File Structure**

- Single HTML file: `dev-admin.html`
- All code embedded (no external files except CDN resources)
- No build tools (webpack, etc.) - raw/vanilla approach

### **Technology Stack**

- **Frontend**: Vanilla JavaScript (no frameworks)
- **HTTP Client**: HTMX for server interactions
- **CSS Framework**: Tailwind CSS
- **UI Components**: DaisyUI (Tailwind-based component library)
- **Icons**: Lucide Icons (SVG-based, CDN)
- **Authentication**: Supabase-js client library
- **CDN Resources**: All external libraries via CDN URLs
- **Sentry Integration**

## Authentication System

### **Login Methods (3 options)**

1. **Google OAuth** (via Supabase Auth)
2. **GitHub OAuth** (via Supabase Auth)
3. **Email/Password** (via Supabase Auth)

### **Authentication Flow**

1. Check Supabase auth state on page load
2. Show login UI if unauthenticated
3. On successful login:
   - Notify backend: `GET /auth/login`
   - Load initial content: `GET /auth/onboarding`
4. On logout:
   - Clear Supabase session
   - Notify backend: `GET /auth/logout`

## User Interface Design

### **Unauthenticated State**

- Login form with 3 authentication options
- Clean, centered layout
- Error handling for failed logins

### **Authenticated State**

- **Top-right corner**: Action menu/links
- **Center area**: Dynamic content based on current action
- **Navigation**: HTMX-powered content loading (no page refresh)

### **Available Actions**

1. **Dashboard** - main landing area
2. **Profile** - user information display (read-only)
3. **Logout** - session termination

## Backend Integration

### **Server Configuration**

- **Base URL**: `http://127.0.0.1:8000` (configurable for later deployment)
- **Protocol**: HTTP GET requests via HTMX

### **API Endpoints**

- `GET /auth/login` - Notification after user login
- `GET /auth/logout` - Notification after user logout
- `GET /auth/onboarding` - First page content after login
- `GET /auth/profile` - User profile information display
## Error Handling & UX

### **Error UI Components (DaisyUI)**

- **Toast notifications** - Authentication errors, network issues
- **Alert boxes** - Form validation, system messages
- **Loading states** - Button spinners, skeleton screens
- **Inline messages** - Field-level validation errors

### **Error Scenarios**

- Authentication failures
- Network connectivity issues
- Backend server errors
- Form validation errors
- Session expiration

## Development Approach

### **Implementation Strategy**

1. **Two-step process**: Plan first, then code generation
2. **Clarification phase**: Resolve requirements before coding
3. **Single artifact**: Complete working application in one file

### **Code Organization**

- **HTML**: Semantic structure with DaisyUI components
- **CSS**: Embedded `<style>` section with Tailwind classes
- **JavaScript**: Embedded `<script>` section with modular functions
- **Dependencies**: CDN imports in `<head>` section

## Configuration Requirements

### **Supabase Setup**

- Project URL and anon key (user-provided)
- OAuth provider configuration (Google, GitHub)
- Authentication policies and settings

### **Customization Points**

- Backend server URL (currently localhost:8000)
- Supabase credentials
- UI theme and styling preferences
- Additional authentication providers (future)

## Quality Standards

- **Responsive design** - Mobile and desktop compatible
- **Accessibility** - Proper ARIA labels and keyboard navigation
- **Error resilience** - Graceful handling of failure scenarios
- **Clean architecture** - Modular, maintainable vanilla JavaScript
- **Production ready** - No development dependencies or build steps

---

_This specification serves as the complete requirements document for the dev-admin.html single-file application._
```

Here comes my dev-admin one page application with some issue(For some unknow reason, it will stuck after DOMContentLoaded evnet has been fired). I need you:
- Keep the current technical stack:
  - Pure JS can run in all of the main stream web browser directly instead of via any code transformation;
  - Use Tailwind CSS + DaisyUI as the CSS framework and UI component library;
  - Lucide Icons as the major icon library;
  - HTMX as the major interaction mechanism with backend server and frontend dynamic controller;
  - Supabase JS as the bridge to implement authentication via SUpabase Auth with Google OAuth, Github OAuth and email/password login(All of these three ways are setup in Supabase Auth);
  - Sentry JS SDK to capature potential error handling, exception handling, event capture or performance monitoring;
- Key requirments:
  - Before user login, show login page;
  - Once user login or detect there is some active session, show dashboard page;
  - Once user logout or detect there is no active session, show login page again and clean up the session data;
- Your goal:
  - Refer to this upload prototype implement it seperately without any bugs or potential issues.
  - Focus on stability and maintainability, ensure I can add more modules(virtual pages) conviently, easily and quickly;

###################################################################################################

### 2, Full Prompt: Convert SQL DDL → SQLModel Models
```markdown
## **Convert SQL DDL → SQLModel Models**

You are an expert Python and SQL developer. Your task is to convert a SQL table definition (DDL) into Python SQLModel models suitable for FastAPI applications. Follow these rules strictly:
### **1. Naming Conventions**

* Keep database column names as in the original DDL:
  * `C_` → char/varchar/text
  * `N_` → integer/number
  * `D_` → date/datetime/timestamp
* Python attributes should use **clean snake\_case** (e.g., `in_used`, `created_at`) for readability.
* Table names should keep the original DDL table name.

### **2. Common Base Class**
* Define a base class called `MyBase` for all models.
* Include the following mandatory fields in `MyBase`:

  * `in_used: int` → `N_IN_USED`, default 0
  * `created_at: datetime` → `D_CREATED_AT`, default current timestamp
  * `updated_at: datetime` → `D_UPDATED_AT`, auto-updated on row change
  * `deleted_at: datetime | None` → `D_DELETED_AT`, nullable
* Inherit from `MyBase` if the table has these common fields; otherwise, inherit directly from `SQLModel`.
* Use `Mapped[...]` for all column type annotations.
* Use `mapped_column(...)` instead of `Field(sa_column=Column(...))`.
* Include defaults and server defaults in `mapped_column(...)`.
* Use `table=True` for SQLModel table classes.
* Use `Mapped[OtherModel] = relationship(...)` in typed style if foreign keys exist.


### **3. Primary Keys**
* Use `primary_key=True` and `autoincrement=True` in `mapped_column`.
* Do **not** set `server_default` for primary keys.

### **4. Unique Constraints & Indexes**
* Keep using `__table_args__` for `Index` and `UniqueConstraint`.
* Single-column indexes can also use `index=True` on the column if no custom name is needed.

### **5. Default Values**

* Python-side defaults: `default=...`
* Database-side defaults: `server_default=...`
* Use `onupdate=func.now()` for `updated_at` fields.
* Use `mapped_column(DateTime, server_default=func.now(), onupdate=func.now())` for `created_at`/`updated_at`.
* Annotate nullable columns as `Mapped[type | None]`.
### **6. Typing / MyPy Compliance**
* Ensure MyPy / Pyright type safety for column expressions.
* All generated classes and columns should pass strict type checks.

### **7. Cross-Dialect Compatibility**
* Autoincrement fields should work in:
  * MySQL (`AUTO_INCREMENT`)
  * SQLite (`AUTOINCREMENT`)
  * PostgreSQL (`SERIAL`)
  * SQL Server (`IDENTITY`)
* And other dialects adapt as needed.

### **8. Comments**
* Include a brief docstring for each class explaining the table purpose.
* Include comments for indexes, unique constraints, or special behaviors if applicable.

### **9. Output**
For each table in the DDL:

* Generate a SQLModel class with proper `Mapped[]` types and `mapped_column(...)` assignments.
* Include `__tablename__` and `__table_args__` if constraints or indexes exist.
* Include base class (`MyBase`) if applicable.
* The generated code should be fully compatible with SQLAlchemy 2.0 typing, SQLModel, and FastAPI, with no MyPy/pyright complaints.

### **10. Example Usage**
**Input SQL DDL:**
  ```sql
  create table if not exists SYS_MAP (
      N_ID integer primary key autoincrement,
      C_CATEGORY varchar(64) not null,
      C_LEFT varchar(64) not null,
      C_RIGHT varchar(64) not null,
      N_ORDER integer not null default 0,
      IN_USED tinyint not null default 0,
      CREATED_AT datetime default current_timestamp,
      UPDATED_AT datetime default current_timestamp on update current_timestamp,
      constraint UK_SYS_MAP_CATEGORY_LEFT_RIGHT unique (C_CATEGORY, C_LEFT, C_RIGHT)
  );
  ```

**Output Python SQLModel code (assuming `MyBase` is defined elsewhere):**
  ```python
  class SysMap(MyBase, table=True):
      """
      System mapping table
      - Maps C_LEFT to C_RIGHT within a category.
      - Unique constraint ensures no duplicate triplets.
      """

      __tablename__ = "sys_map"
      __table_args__ = (
          UniqueConstraint("C_CATEGORY", "C_LEFT", "C_RIGHT", name="uk_sys_map_category_left_right"),
          Index("idx_sys_map_category", "C_CATEGORY"),
      )

      id: Mapped[int] = mapped_column("N_ID", Integer, primary_key=True, autoincrement=True)
      category: Mapped[str] = mapped_column("C_CATEGORY", String(64), nullable=False)
      left_value: Mapped[str] = mapped_column("C_LEFT", String(64), nullable=False)
      right_value: Mapped[str] = mapped_column("C_RIGHT", String(64), nullable=False)
      order: Mapped[int] = mapped_column("N_ORDER", Integer, nullable=False, server_default="0", default=0)
  ```

Convert **any given SQL DDL** into **MyPy-safe, cross-dialect, FastAPI-ready SQLModel Python code** following the above rules.

```

### 3, Plugin Mechanism
Let's create a plugin mechanism to extend the functionality of the system. We will split it in three steeps to finish it:
1, Clarify the requirement and draft out the proposal.
2, Define the plugin interface and implement class PluginManager in file @faster/core/plugins.py
3, Apply this plugin interface to existing resources, for example, database, redis supabase auth and etc.

In my view, this plugin at least need to response to the following events:
- on_setup: The real lazy initialization
- on_teardown: The cleanup event
- on_refresh: The refresh event

The PluginManager class contains one plugin map(for example dict[str, object]) and one plugin list(for example list[object]) to keep the order of plugins. Initialize and refresh the plugins in the normal order, and teardown the plugins in the reverse order. And PluginManager need another function to register plugin.

Okay, let's start with the first step.

===============
Aditional things need to be done:

1, It's still a little bit strange for the interface name. Let's do some changes on BasePlugin:
- on_setup -> setup
- on_teardown -> teardown
- on_check_health -> check_health

All the sub-classes need to apply these naming changes.

2, To keep the consistancy and readbility, PluginManager is also a class implementing BasePlugin interface. That means we need to rename the member functions:
- setup_all -> setup
- teardown_all -> teardown
- check_health_all -> check_health

3, The reason we keep the __init__ method simple is to implement lazy initialization( actually in setup method). Another reason to implement
PluginManager is to reduce these global variables. We will step by step to reduce these global variables(for example db_mgr, redis_mgr and etc). So, do not create instance and register plugins on the global scope. Attach  PluginManager's instance to app.state then we can access it from anywhere without any global variables burden.
