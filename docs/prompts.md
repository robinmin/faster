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


### User information

Function login in file @faster/core/auth/routers.py is just a dummpy so far. By design it at least do the following works(Of course not all implemented in this function, but just call the right one to implement it):

- Get JWT from from request and validate it with remote Supabase Auth server. If invalid, redirect to login page or return error.
- If JWT token is valid, remove current JWT token from blacklist(call blacklist_delete in redisex.py).
- If JWT token is valid, get user profile from Supabase and store it in the session.
- For the first time register user, redirect to onboarding page.
- For the existing user, Redirecting to the appropriate page(based on the user's authentication status)

## Your tasks:
- Design a set of tables to store all user informations responsed from Supabase Auth API. Define all of them in file @faster/core/auth/schemas.py (The style and naming conventions should be consistent with what I've done in file @faster/core/models.py)

- implement functions in file @faster/core/auth/repositories.py to interact with database if necessary.
- implement functions in file @faster/core/auth/services.py to define the key business logic for above functions.
- call these functions defined in file @faster/core/auth/services.py to implement login function in file @faster/core/auth/routers.py.

Here comes a sample of Supabase Auth returned user information(via Google OAuth).
```json
{
  "id": "61332569-ce63-4876-a207-9f376d89696b",
  "aud": "authenticated",
  "role": "authenticated",
  "email": "minlongbing@gmail.com",
  "email_confirmed_at": "2025-07-23T22:37:38.463723Z",
  "phone": "",
  "confirmed_at": "2025-07-23T22:37:38.463723Z",
  "last_sign_in_at": "2025-09-04T06:19:32.749423Z",
  "app_metadata": {
    "provider": "google",
    "providers": [
      "google"
    ]
  },
  "user_metadata": {
    "avatar_url": "https://lh3.googleusercontent.com/a/ACg8ocKBNPXQ9hZ-8ndFwNyOXF8-NdoMo9DBRy1uzzHVbF5vOO5Yp8LR=s96-c",
    "email": "minlongbing@gmail.com",
    "email_verified": true,
    "full_name": "Robin Min",
    "iss": "https://accounts.google.com",
    "name": "Robin Min",
    "phone_verified": false,
    "picture": "https://lh3.googleusercontent.com/a/ACg8ocKBNPXQ9hZ-8ndFwNyOXF8-NdoMo9DBRy1uzzHVbF5vOO5Yp8LR=s96-c",
    "provider_id": "111535814728599577599",
    "sub": "111535814728599577599"
  },
  "identities": [
    {
      "identity_id": "728d865e-ac9b-46b6-a62f-740c1f77b112",
      "id": "111535814728599577599",
      "user_id": "61332569-ce63-4876-a207-9f376d89696b",
      "identity_data": {
        "avatar_url": "https://lh3.googleusercontent.com/a/ACg8ocKBNPXQ9hZ-8ndFwNyOXF8-NdoMo9DBRy1uzzHVbF5vOO5Yp8LR=s96-c",
        "email": "xxxx@gmail.com",
        "email_verified": true,
        "full_name": "Robin Min",
        "iss": "https://accounts.google.com",
        "name": "Robin Min",
        "phone_verified": false,
        "picture": "https://lh3.googleusercontent.com/a/ACg8ocKBNPXQ9hZ-8ndFwNyOXF8-NdoMo9DBRy1uzzHVbF5vOO5Yp8LR=s96-c",
        "provider_id": "111535814728599577599",
        "sub": "111535814728599577599"
      },
      "provider": "google",
      "last_sign_in_at": "2025-07-23T22:37:38.451537Z",
      "created_at": "2025-07-23T22:37:38.451601Z",
      "updated_at": "2025-09-04T06:19:32.704958Z",
      "email": "xxxx@gmail.com"
    }
  ],
  "created_at": "2025-07-23T22:37:38.426611Z",
  "updated_at": "2025-09-04T06:19:32.792465Z",
  "is_anonymous": false
}
```

I need you to generate a composed model class UserInfo in @faster/core/auth/models.py to contain all of these information, and a method `get_user_inf(user_id : str) -> UserInfo` in file @faster/core/auth/repositories.py. The key function of this method is load informations in relevant tables(AUTH_USER, AUTH_USER_METADATA, AUTH_USER_IDENTITY, and etc -- which defined in file @faster/core/auth/schemas.py) and compose these information into a UserInfo instance and return it.

DO NOT FEMEMBER to following the rules of this projict defined in file @docs/AGENTS.md

########################################################################################
Current implementaion on endpint /login in file @faster/core/auth/routers.py is wrong be another agent, as he/she against the responsbility of each file. For example, it access the Supabase Auth in @faster/core/auth/repositories.py.

Here are the basic responsbility for module @faster/core/auth:
- @faster/core/auth/models.py : define non-database related entities, no business logic here
- @faster/core/auth/schemas.py : define database related entities, no business logic here
- @faster/core/auth/auth_proxy.py : Proxy layer to interact with Supabase Auth, all access to Supabase Auth must go through with this file.
- @faster/core/auth/repositories.py : Proxy layter to access local database, all access ti local database must go through with this file.
- @faster/core/auth/services.py : combinate business logic here with support of @faster/core/auth/auth_proxy.py and @faster/core/auth/repositories.py
- @faster/core/auth/routers.py : define RESTful API endpoints here.
- @faster/core/auth/middlewares.py : define middlewares
- @@faster/core/auth/utilities.py : define utilities

Please follow abouve responsbility, help to refactory file @faster/core/auth/repositories.py. Please majorly focus on this file. Of course, you can do some relavant adjustment with other files if necessary.

#################

## Background
After several rounds with multiple LLM/Agents, my @faster/core/auth module is becoming more and more messy. We need to do a set of refactoring to simplify this redundant and someplace overdesigned code and some other place messy.

Before you start to change anything, you should understand my project rules you must obey in file @docs/AGENTS.md.

## Requirements

My FastAPI based application to use Supabase Auth as the authentication provider. This module is responsible for interacting with Supabase Auth and local database, providing authentication and authorization services. Here comes each file's responsibility:
- @faster/core/auth/models.py : Define non-database related entities, no business logic here
- @faster/core/auth/schemas.py : Define database related entities, no business logic here
- @faster/core/auth/auth_proxy.py : Proxy layer to interact with Supabase Auth, all access to Supabase Auth must go through with this file.
- @faster/core/auth/repositories.py : Proxy layer to access local database, all access to local database must go through with this file.
- @faster/core/auth/services.py : Combine business logic here with support of @faster/core/auth/auth_proxy.py and @faster/core/auth/repositories.py
- @faster/core/auth/routers.py : Define RESTful API endpoints here.
- @faster/core/auth/middlewares.py : Define middlewares
- @faster/core/auth/utilities.py : Define utilities

The core requirements is quite simple: Work with Supabase Auth and store data into local database.

## Current Issues
- Duplicate table definition: for example, class UserIdentityData vs class UserIdentity in @faster/core/auth/schemas.py
- Confusing naming: class UserProfile vs class UserProfileData(Original is the same, I already changed on as well)
- Code logic is also messy.

## Goals
- Refactor this module, make it easy to understand and maintain and use. You should focus on improving the code structure and readability.
- Majorly, you should focusing on the following files, if necessary, you can do some change on other as well:
  - @faster/core/auth/repositories.py : only this file can interact with local database
  - @faster/core/auth/services.py
  - @faster/core/auth/models.py
  - @faster/core/auth/schemas.py
  - @faster/core/auth/auth_proxy.py : only this file can interact with Supabase Auth API
- All code should pass ryff, mypy and pyright, by the end of the work, we should make all unit test pass(In case any design change, unit test should be updated accordingly, and make sure all unit test pass)


## Fix repository test
As we lready had some enhancement on @faster/core/database.py, @faster/core/builders.py, @faster/core/repositories.py and @faster/core/auth/repositories.py, we'd better to do the following things:
- Fix the lint errors generated by command 'make lint';
- Adjust the way to test database: when we test database access, we'd better to adjust the settings as in memory SQLite to avoid to mock database itself. That means to change as Settings.database_url as `sqlite+aiosqlite:///:memory:`. Of source, if you are try to testing something in class DatabaseManager or somewhere else for some partucular purpose with enought reason, you can decide which way is your real needs.
- Enhance @tests/core/test_builders.py due to above all amendments;
- Enhance @tests/core/test_repositories.py due to above all amendments;
- Enhance @tests/core/test_auth_repositories.py due to above all amendments;


## New Database access layer
#### Backgroud
Based on our previous conversation, it looks like there is some design issue in my application. By designing, I create two files to enpower client user to have a simple and concistance way to access database. The original designs are:
- @faster/core/database.py: Class DatabaseManager managge all database connecttion, sesion and transaction related things. Class BaseRepository provide a base class for all repository classes.
- @faster/core/builders.py: Provide 3 classes QueryBuilder/DeleteBuilder/UpdateBuilder to help deeveloper to build up database access.

#### Current Issue
It looks like current solution combinding so may sqlalchemy things with another sqlmodel related things together. It implement so may place in old-sqlalchemy style and occur so many issues by linters(ruff, mypy and basedpyright).

#### Core Goal
- Your need to review @faster/core/database.py carefully, and find enhancement points and plan if any.

- create another abstract database access layer in SQLModel way into file @faster/core/builders2.py. Of course, you can refer to @faster/core/builders.py for reference, but just reference. No need to replicate it.

- That's the first step, after my comfirrmation, then we will try to use this new database access layer to refactory current soruce code.

- In case you want to enhance @faster/core/database.py, you need to disscuss with me.

- All generated code must pass linters check(including ruff, muypy and basedpyright).


## Refactory auth_proxy

#### Background
As we already, refined these utilities(authenticate_request_and_get_user_id, extract_bearer_token_from_request, extract_token_from_multiple_sources, fetch_user_id_from_token), other parts will not bothered with JWT token and user id and etc. It time to review and enhance @faster/core/auth/auth_proxy.py.

The orginal design purpose for this file is to provide a simple and consistent way for client users to access Supabase Auth as a proxy.

#### Current issue
- Still remining some unnecessary token related things here.
- Chaotic and redeundent model defined in @faster/core/auth/models.py. We should go this way:
- Chaotic and redeundent methods related to above models.
#### Goal
- Redefine models in @faster/core/auth/models.py:
  - keep SupabaseUser but rename it as UserProfileData(which inhireted from supabase_auth.types.User) as the representative model for the full information of the user.
  - remove current model definitions: UserProfileData, UserIdentityData, AppMetadata, UserMetadata, UserInfo
- Redeine methods related to above models:
  - get_user_by_id in @faster/core/auth/auth_proxy.py: load user profile information from Supabase Auth with new UserProfileData model.
  - get_user_info in @faster/core/auth/repositories.py: load user profile information from local database with new UserProfileData model.
  - set_user_info in @faster/core/auth/repositories.py: save user profile information to local database with new UserProfileData model.
- All refined code must pass linters(ruff,mypy and basedpyright)
- One code ready, we need to adjust unit test code, all pass with certain coverage rate


### Enhance get_user_by_id

A few things to enhance:

- In file @faster/core/auth/auth_proxy.py, adjust get_user_by_id's method signature to:
```
async def get_user_by_id(self, user_id: str, from_cache: bool = True) -> UserProfileData | None:
```
That means, we just keep this method very simple, get user information from Supabase Auth directly, no cache.

- In file @faster/core/auth/services.py, we enhance the logic for method `get_user_by_id` in this sequence:
  - First, try to load user information from redis directly(call get_user_profile). If success, directly return;
  - Then try to call get_user_info defined in @faster/core/auth/repositories.py to get data from local database. If success, update cache(call set_user_profile) then return
  - At last, try to call self._auth_client.get_user_by_id to load data from Supabase Auth. If success, update local database(set_user_info) and update cache(call set_user_profile) then return

- Evaluate current change's impact on the rest of the whole application with your suggestion list



## inconsistency issue fix on tag2role_get / tag2role_set

#### Background
- I already found one inconsistent design: the mapping between tag to roles should be called via `sysmap_get(str(MapCategory.TAG_ROLE), 'tag_1')` instead of using `tag2role_get` to get back. Of course, it should be call via `sysmap_set(str(MapCategory.TAG_ROLE), 'tag_1', 'role_xxx')` to set information instead of via `tag2role_set`.
- I already comment out tag2role_get / tag2role_set for further verification and deletion.

#### Your goal
- Find out these relevant code, to replace tag2role_get / tag2role_set by sysmap_get/sysmap_set with `MapCategory.TAG_ROLE`
- Remove unit test cases for tag2role_get / tag2role_set
- For the other unit test cases related to tag2role_get / tag2role_set, try to replace them by sysmap_get/sysmap_set
- make sure both `make lint` and `make test` all pass


A few further enhancements:
- As all these mapping stored in table SYS_MAP, so, we'd better to simplify the singnature as:
```python
async def sysmap_set(category: str, mapping: dict[str, str]) -> bool:
async def sysmap_get(category: str, left: str | None = None) -> dict[str, str]:
```
- Also, adjust the client code and unit tests, pass all of them



## enhance tag_role mapping with lazy initialization
Enhance the following things:
- In class AuthService(in file @faster/core/auth/services.py), add a instance variable _tag_role_cached : dict[str, str] with lazy initialization.
- In AuthService.get_roles_by_tags, check self._tag_role_cached already initialized or not. In case of not, call `sysmap_get(str(MapCategory.TAG_ROLE))` to load them all, and cache in self._tag_role_cached
- Use this `self._tag_role_cached` to get back the roles related to give tags.
- Adjust the relevant code and unit tests, make sure all pass `make lint` and `make test`.

## Simplify the startup mechanism on create_app
For function `create_app` in file @faster/core/bootstrap.py, as we already has Plugin mechanism, for anyone ,who want to control the startup and shutdown lifecricle, he or she can inhireted a new class from BasePlugin to customize a new plugin to do so. It allows us the reduce the parameters `startup_handler` and `shutdown_handler` to unify the startup-shutdown mechnism. So, help to:

- Reduce the parameters `startup_handler` and `shutdown_handler` from `create_app`, and adjust relevant code
- Adjust the client code and relevant unit tests to make sure all of them pass `make lint` and `make test`.


## Refactory supabase.auth.onAuthStateChange handler

#### Background
So far, we have the mechanism to response the `supabase.auth.onAuthStateChange` events:
  - When received event 'SIGNED_IN', call '/auth/login' API;
  - When received event 'SIGNED_OUT', call '/auth/logout' API;
It's very limited and hard to extend for other events going forward. In the backeend, we need more and more API to response these eevents. It's unnecessary.

#### Your Goal
- Add a new interface '/auth/notification/{event}' (function on_notification in file @faster/core/auth/routers.py) to receive all events centrally. It at least to support events:
  - INITIAL_SESSION: Emitted right after the Supabase client is constructed and the initial session from storage is loaded.
  - SIGNED_IN:
    - Emitted each time a user session is confirmed or re-established, including on user sign in and when refocusing a tab.
    - Avoid making assumptions as to when this event is fired, this may occur even when the user is already signed in. Instead, check the user object attached to the event to see if a new user has signed in and update your application's UI.
    - This event can fire very frequently depending on the number of tabs open in your application.
  - SIGNED_OUT:
    - Emitted when the user signs out. This can be after:
      - A call to supabase.auth.signOut().
      - After the user's session has expired for any reason:
        - User has signed out on another device.
        - The session has reached its timebox limit or inactivity timeout.
        - User has signed in on another device with single session per user enabled.
        - Check the User Sessions docs for more information.
    - Use this to clean up any local storage your application has associated with the user.
  - TOKEN_REFRESHED:
    - Emitted each time a new access and refresh token are fetched for the signed in user.
    - It's best practice and highly recommended to extract the access token (JWT) and store it in memory for further use in your application.
      - Avoid frequent calls to supabase.auth.getSession() for the same purpose.
    - There is a background process that keeps track of when the session should be refreshed so you will always receive valid tokens by listening to this event.
    - The frequency of this event is related to the JWT expiry limit configured on your project.
  - USER_UPDATED: Emitted each time the supabase.auth.updateUser() method finishes successfully. Listen to it to update your application's UI based on new profile information.
  - PASSWORD_RECOVERY:
    - Emitted instead of the SIGNED_IN event when the user lands on a page that includes a password recovery link in the URL.
    - Use it to show a UI to the user where they can reset their password.
- In on_notification, you need to call existing functions prioritoly. If you need any new function, you can add non-utility function into @faster/core/auth/services.py, and add utility function into @faster/core/auth/utilities.py.
- Of course, in on_notification, you need to cover current logic of login/logout logic (blacklist operation, and use background task to update user information and etc)
- At the front end, you need to refactory function handleAuthStateChange to handle above events, also. Do not forget to bring Bearer token, as server side relay on it to identify who is the current user.
- Prepare to retire login/logout interface at both backend and frontend.
- get `make lint` and `make test` all pass, before end of this refactory.


I noticeed that, when server side received /notification/INITIAL_SESSION request without any Bearer token. It's fare enough in that time, client still can not find any valid token. So let's do the following enhancement:

- Rename current function from:
```python
@router.post("/notification/{event}", include_in_schema=False, response_model=None)
async def on_notification(
    event: str,
    request: Request,
    background_tasks: BackgroundTasks,
    user: UserProfileData | None = Depends(get_current_user),
) -> AppResponseDict:
```

to:

```python
@router.post("/callback/{event}", include_in_schema=False, response_model=None)
async def on_callback(
    event: str,
    request: Request,
    background_tasks: BackgroundTasks,
    user: UserProfileData | None = Depends(get_current_user),
) -> AppResponseDict:
```

- Add a new endpoint like this:
```python
@router.post("/notification/{event}", include_in_schema=False, response_model=None, tags=["public"])
async def on_notification(
    event: str,
    request: Request,
    background_tasks: BackgroundTasks,
) -> AppResponseDict:
```

- Add just logic on both server side and client side: For the events we can find the valid access token/ particular user, we call "/callback/{event}" to process, for the others, we should call "/notification/{event}". That means INITIAL_SESSION should go to "/notification/{event}"

- Add just all relevant code, including their tests, make sure all pass `make lint` and `make test`.

- use MCP playwright to have frontend tests.


Your previous task is interupted, please continue it. The original task is: As I tried, the Menu navigation is not working propriate: 'Dashboard' is okay, but the
others(including 'Profile' and 'Onboarding' is not right. Try again deeply to figure out the issues and fix them all if any with MCP playwright.
robin


## fix frontend
My frontend web application has been broken by another LLM. This web application is defined in file @faster/resources/dev-admin.html. You can use MCP playwright to access it via http://127.0.0.1:8000/dev/admin.

Currently, it is stucked at the loading page, help to find the root cause and fix it. Meanwhile, there also have some web console errors, you need to fix all of them too.


supabase.js:1 Multiple GoTrueClient instances detected in the same browser context. It is not an error, but this should be avoided as it may produce undefined behavior when used concurrently under the same storage key.

- The theme toggle is still not working properly. Try to fix it.
- Meanwhile, after I refresh the web page, I noticed some web console warning like this, figure out what happend and whether need to fix. If yes, fix it.


### Wrong type on sys:map:role

By design, one tag should be mapped to multiple roles, or you can say, in sys_map, one left value can be mapped to many right values. That's say: in sysmap_get/sysmap_set in file @faster/core/redisex.py, we used hash to implement it was totally wrong(hgetall/hget/hset). We should asjust the key from 'sys:map:{category}' to 'sys:map:{category}:{left_value}', them use set to store all their right values(sadd/smembers)

- Help to re-implement sysmap_get/sysmap_set.
- Adjust the relevant code in other files.
- adjust and fix the unit tests.
- make sure all code will pass both `make lint` and `make test`.


## Enhance the client's centralized API call to server side.

#### Curreent issue
The call to '/dev/app_state' is not work well, as it forget to bring access token/Bearer token. The root cause is we do not have a cemtralized API proxy in the client with verylimited white list. Only the APIs in the white list do not need to bring the token when call them. Here comes the white list so far:
- /auth/notification/{event}
- /.well-known/appspecific/com.chrome.devtools.json
- /dev/admin
- /dev/settings
- /custom

#### Your goal
- Re-implement a API service/proxy to centralized manage all APIs with pre-defined white list.
- Use MCP playwright to access it via http://127.0.0.1:8000/dev/admin to verify you change is work properly.


One another issue in @faster/resources/dev-admin.html : Despite we already got the thing done to retrieve back the data from server side on URL
'/dev/app_state', but fogot the use this response data to render the the virtual page  'App State'. We need to show the 'data' part of the response data at the place of the box currently shown 'No App State Data
No application state data available at the moment.'.

Help to design a way to show them well,
as the components of the 'data' part is very dynamicly, we shoudl design it more genericly.

Fix this one.


Let's do some change on page 'App State' in file @faster/resources/dev-admin.html:
- Replace current section of 'No Data State' with a mockup-code daisy UI componeent to show the 'data' part of the response data of request '/dev/app_state'


### Refactory AuthPlugin
#### Backeend
As of today, the auth module is working as expect. It's time for us to do some refactory work to enhance the code quality and the extendability for further works.

#### Current Issues
- AuthService instance has been create multiple times
- Some key authentication related data's preparation is not very concistance/duplicated:
  - make_route_finder in file @faster/core/auth/middlewares.py vs get_all_endpoints in file @faster/core/utilities.py
- Some mission critical data used unnecessary redis cache: for example:
  - store tag_role mapping in redis
  - store JWKS in redis
- Some internal used data cached in app.state or request.state, may be migrated into AuthService or AuthService's component for example AuthProxy, should make a better cohesion and performance.

#### Solution & Goal
- Make class AuthService inhireted from interface BasePlugin. It will make class AuthService as singleton. and add responsibility to implement three methods: `setup`, `teardown`, `check_health`.
- Of course, as AuthService is a plugin now, we also need to enhance its `__init__` method for lazy intialization. That means you also need to adjust to @faster/core/bootstrap.py to setup AuthService as a plugin, and use get_instance in @faster/core/routers.py to call methods in stead of create another instance.
- In setup, we use `settings` arguments to prepare to create real things. and trigger to call `check_health`.
- We treat `check_health` to refresh data. It will give us a extral benifit google forward to refresh data on the fly.
- In case of anything need to clean up, we need to put them all in `teardown`.
- Add a set of method to collect router information(mix both make_route_finder in file @faster/core/auth/middlewares.py and get_all_endpoints in file @faster/core/utilities.py), filter router information(as we've done in make_route_finder), and show in log(as we've done in check_all_resources in @faster/core/bootstrap.py). Use these new define methods replace current one, help to centralized the operations on these router information. Do not forget to lear the way from function make_route_finder in @faster/core/auth/middlewares.py. we also need to get rid of it, for the same reason.
- Get rid of to store tag_role information in redis, but just add a dict variable on class make_route_finder. Of course, we also need to add some helper methods to open a way to inject the mapping data from outside on both class AuthService and class AuthMiddleware(It is prepared out side of auth module.)
- For the same reason, add another dict containter to cache JWKS information in AuthProxy.
- Adjust the function of Settings.auth_enabled: As AuthService already be re-defined the core component, we can not disable it really now. But we can use is as a option in method AuthMiddleware.dispatch to bypass the authorization checking, for example for debugging or something like that.

This task will be implement two steps: 1, Clarification and enhance the requirment itself. 2, Implement them all and make sure the data quality with tools `make lint` and `make test` all pass. Let's begin the first step.


A few things need to be fixed or comfirmed:
- As instance variable _instance and class method get_instance already defined on fater class AuthService, do we realy need to implement it again? If yes, keep it. If no, remove them.
- in faster/core/auth/routers.py, no global `auth_service` will be better, help to adjustment it.
- As we already make class AuthService as a singletone, do we still need to attach router information on `app.state` as `app.state.endpoints`?  You nedd to re-evaluate it. In case of not, we need to change the relevant code properiate.
- As we already centralize all router information related things into class AuthService, you'd better to concider whether we still need function get_all_endpoints aand its relevant utilities functions or not. Do some cleanup and enhancement work on it.


Let's focus on how to refactory and simplify class AuthMiddleware. Here comes some point I found. Your need to comfirm or reject them one by one. Meanwhile, you need to do a full code review on it to find any potential issues I just missed. Here comes mine:
- we do need a place to inject `tag_role` mapping into module auth, but it must not be to add a new proxy call `set_tag_role_mapping` on class AuthMiddleware. It cannot help to do this, but just add a new method. That's it. It need to be remove and we need to find a place outside of module auth to call `AuthService.set_tag_role_mapping`.
- As `_is_allowed_path` is just defined and call both only once, and with very simple logic here. I suggest merge it to `_handle_allowed_path`, and rename `_handle_allowed_path` as `_check_allowed_path`.
- For the same reason, it looks like no need to create a seperate method `_is_public_endpoint` to check it. just apply the logic directly. It will be more clear.


- As we've done these dramatic refactory on @faster/core/auth/middlewares.py and @faster/core/auth/services.py. You'd better to re-generate a set of full comprtehensive unit tests for both of them in @tests/core/test_auth_middlewares.py and @tests/core/test_auth_services.py.

- For these existing unit tests, you need to evalueate them one by one to decide to keep it or drop it.

- Make sure `make lint` and `make test` all pass before you finish this task.


## Enhance Sys Health

### Background
As we already enhance the plugin mechanism and transfer class AuthService as another core plugin. We need to leverage these enhancements to referctory '/health' again, and add an additional menu item and virtual page 'Sys Health'.

### Tasks
- Based on current plugin solution, enhance '/health' (function check_health in file @faster/core/routers.py), and its dependencies(for example, check_all_resources and etc).

- I already find a issue for the initial plugin status in the application log like this:
```
15 13:59:15.236 [info    ] =========================================================
15 13:59:15.237 [info    ]      We are running 'faster' - 0.0.1 on development in DEBUG mode.
15 13:59:15.237 [info    ]      DB      : {'master': True, 'replica': False}
15 13:59:15.238 [info    ]      Redis   : {'provider': 'upstash', 'connected': True, 'ping': True, 'error': None}
15 13:59:15.239 [info    ]      Sentry  : {'status': True, 'configured': True, 'initialized': True}
15 13:59:15.239 [info    ]      Auth    : {}
15 13:59:15.239 [debug   ] =========================================================
```
There must be some ready to caused that Auth plugin's status shown nothing. Find the root cause and fix it.

- In @faster/resources/dev-admin.html, add a new menu item 'Sys Health', and a new added virtual page 'Sys Health'. Click the menu item, the navigate the user to this new virtual page.
- In virtual page 'Sys Health',use a well design solution to show the status of thse plugin(All data come from the response data's `data` attribute from '/health').

- Enhance the relevant unit tests, make sure both `make lint` and `make test` pass.
- Use MCP playwright to access frontend via `http://127.0.0.1:8000/dev/admin` to verify every functionalities are working well. In case of any web console errors/warnings, fix all of them if possible.

### enahnce virtual page 'Profile'
As we already add some new endpoints as shown bellow, we need to do some enhancements on virtual page 'Profile'. Use the following endpints:
- @router.post("/password/change", include_in_schema=False, response_model=None)
- @router.post("/password/reset/initiate", include_in_schema=False, response_model=None, tags=["public"])
- @router.post("/password/reset/confirm", include_in_schema=False, response_model=None, tags=["public"])
- @router.post("/deactivate", include_in_schema=False, response_model=None, tags=["admin"])
- @router.post("/account/delete", include_in_schema=False, response_model=None, tags=["admin"])

As these are very critical operation, so we need add a comfirmation action before to do the real work.

### Add new  virtual page 'User Management'
- add a new menu item 'User Mangement' and a new virtual page 'User Mangement'.
- Design a virtual page 'User Mangement' and implement it. As this is a simple management tool for administrator/developer, we do not want to involve to list users and pickup particurlar user and etc. Our operation all based on a inputed user id, and then based it to do the further operations.
- It should involve the following endpoints:
  - @router.post("/users/{target_user_id}/ban", include_in_schema=False, response_model=None, tags=["admin"])
  - @router.post("/users/{target_user_id}/unban", include_in_schema=False, response_model=None, tags=["admin"])
  - @router.post("/users/{target_user_id}/roles/grant", include_in_schema=False, response_model=None, tags=["admin"])
  - @router.post("/users/{target_user_id}/roles/revoke", include_in_schema=False, response_model=None, tags=["admin"])
  - @router.get("/users/{target_user_id}/roles", include_in_schema=False, response_model=None, tags=["admin"])

As these are very critical operation, so we need add a comfirmation action before to do the real work.


After both of these two requirements, you need to use playwright to verify each function points are working as expect or not. In case of any issue or web console errors, you also need to fix all of them.


## Enhance User Management Page

#### Current situations
 According to the frontend definition in file @faster/resources/dev-admin.html and web view, we need to show the user's basic information in virtual page 'User Management' once user inputed a valid UUID format 'Target User ID'.
Currently, we only show User ID and Roles. Email and Status fields always invalid.

#### Enhancements/Goal
- Adjust the URL endpoint from '/users/{target_user_id}/roles' to '/users/{target_user_id}/basic', and rename function `get_user_roles` to `get_user_basic_info`. And change the response of '/users/{target_user_id}/basic' to include email and status fields.
- At the client side, do the corresponding changes to show email and status fields properly.
- Adjust the UI layout: show 'View Roles' just after 'Target User ID' and before the action buttons.
- Rename 'View Roles' to 'View Basic Info'. Before we checked the user's basic information, hide all action buttons to preventing invalid operations.
- Show 'Ban User' or 'Unban User' based on user's status.
- Once user click on button 'Ban User' or 'Unban User', popup a confirmation dialog to confirm the action.
- Merge button 'Grant Role' with button 'Revoke Role' as button 'Adjust Roles'.
- Once user click on button 'Adjust Roles', show a full list of available roles(available_roles, which already response to client by Supabase event SIGNED_IN) with checkboxes. Check on the role that the user already has.
- One user must at least one role. Once user uncheck all roles we need to show a warning message `Please select at least one role` to prevent invalid operations.
- On the otherhand, we also need to check the same logic at the backend instead of relying on client side's checking.
- At the server side in file @faster/core/auth/routers.py, merge endpoint `/users/{target_user_id}/roles/grant` and `/users/{target_user_id}/roles/revoke` into `/users/{target_user_id}/roles/adjust`. Also merge function `grant_roles` and `revoke_roles` into `adjust_roles`.
- Implement above enhancements and run frontend and backend tests to ensure everything works as expected.


## Remove deactivate_account

#### Backgroud
As we can see in file @faster/core/auth/repositories.py, both `deactivate_account` and c are do soft deletion on user tables, it's duplicated.
#### Goal
We need to concepturely remove the 'delete account' things and do some adjustmeent:
- In @faster/core/auth/repositories.py, remove current `deactivate_account`, and reename `deactivate_account` as a new `deactivate_account`.
- In @faster/core/auth/services.py, delete method `delete_account`
- In @faster/core/auth/routers.py, delete endpint `/account/delete` and method `delete_account`
- In unit tests, we also need to do the same adjustment: remove `delete_account` related unit test case. And as we changed the core of `deactivate_account`, we also need to enhance and add its unit tests.
- In the fronend in faster/resources/dev-admin.html, we also need to concepturely remove the 'delete account' things.
- Finnaly, rename `deactivate_account` as `deactivate`.
- make sure both `make lint` and `make test` all pass. You also need to user playwright the verify the frontend via http://127.0.0.1:8000/dev/admin and fix all web console errors and warnings if any.

### Add log_event
For the following critical user actions, add `log_event` to store user behavior into database:
- /onboarding
- /dashboard
- /profile
- /password/change
- /password/reset/initiate
- /password/reset/confirm
- /deactivate
- /users/{target_user_id}/ban
- /users/{target_user_id}/unban
- /users/{target_user_id}/roles/adjust
- /users/{target_user_id}/basic

After you added these change, make sure `make lint` and `make test` all pass

### Adjust page 'User Management'
- In file @faster/resources/dev-admin.html, change button 'View Basic Info' to a icon button. And put this icon button on the right side of the input field 'Target User ID/Email' wuthin the sameline. You'd better choose a proper icon to represent this search user action.

- Implement this request, and use playwright to verify the frontend via http://127.0.0.1:8000/dev/admin(use Google OAuth user). In case of any issue or web console errors, fix them all.


## Implement class RouterInfo and refactory to use it

### Background & current status
To implement my dynamic RBAC, I need to prepare data to find out for a specified request URL which roles we allow them to access. We stored the tag-role mapping in the database and redis already, then the last work is to find out whitch request path is using for the current request. We implement this check in @faster/core/auth/middlewares.py 's dispatch method. For a better performance, we cached the mapping.

So far, we already get everythong working very well. You can refer to the following methods in @faster/core/auth/services.py for the details:
- collect_router_info
- create_route_finder
- find_route
- log_router_info
- set_tag_role_mapping
- get_tag_role_mapping
- get_roles_by_tags
- clear_tag_role_cache
- is_tag_role_cache_initialized

The real issue is class AuthService already becomes very huge, so we need to do some refactory work to move all these relevants things out of class AuthService.

### Goal
To implement this rafactory work, you need to split into four steps:
- 1, Based on current solution and your best practice, implement class RouterInfo in @faster/core/auth/services.py
- 2, Pair with me to do code review. After complete the code review, then you can use this new added class to replace current solution.
- 3, Generate seperate unit tests for class RouterInfo. And adjust relevant existing unit tests.
- 4, Make sure both `make lint` and `make test` all pass

#### A few things need to be enhanced:
- Merge `set_debug_mode` with `collect_router_info` to reduce methods number -- add an extra parameter `is_debug` on `collect_router_info` 's parameter list.
- Change `self._route_cache` 's type frrom `dict[str, dict[str, Any]]` to `dict[str, RouterItem]`. RouterItem represent all inforrmation items for a particular request. and the key of the dict is euqal to the value of `method` + ` ` + `path_template`.
- Rename methods:
  - `collect_router_info` -> `refresh_data`, need to use cached `tag_role_mapping` to figure out the roles allow to access by tags.
- Remove method `is_tag_role_cache_initialized`, use the raw logic if necessary
- Remove method `get_cache_stats`

If you have any optimizing options, you also can tell me.


#### Additional Enhancements:
- As you marked in docstring, try to comment out AuthService.collect_router_info and AuthService.log_router_info, and replace with AuthService.refresh_data in the places call to both of them.
- To avoid the unnecessary complexity, try to remove these one-line proxy call methods in AuthService with `self._router_info`, especially called within AuthService itself.
- For RouterInfo.create_route_finder._find_route's return type, replace `dict[str, Any] | None` with `RouterItem | None`
- try to evaluate whether we need to keep RouterItem.path_params or not. If yes, tell me why; If not, remove it and all relevant places.


#### The 3rd enhancement
- Enhance RouterInfo.refresh_data: use `all_tag_data = await sysmap_get(str(MapCategory.TAG_ROLE))` to update tag_role mapping before the loop, instead of using cached `self._tag_role_cache`. This will help to reduce the dependency on external. After this change, we no longer need to refresh data outside of this class, for example in AuthService.check_health or refresh_status in file @faster/core/bootstrap.py.
- try to comment out RouterInfo.set_tag_role_mapping and RouterInfo.get_tag_role_mapping, because we will manage the cache internally. Adjust the places  downstream of the code.
- For RouterInfo.create_route_finder._find_route, adjust its return value' type to `str | None`, it will return the cache key to search from the cached RouterItem dict(like `cache_key = f"{method!s} {route.path}"`). Hope this can leverage both of their strength for lru_cache feature and the cached dict for better performance. (In case you have any better idea, we can discuss)
- 3, Adjust relevant existing unit tests, and make sure both `make lint` and `make test` all pass

#### Cleanup work
- remove AuthService.is_tag_role_cache_initialized -- define a simple proxy and only used in unit tests.
- remove AuthService.clear_tag_role_cache -- define a simple proxy and only used in unit tests.
- replace RouterInfo.clear_tag_role_cache and RouterInfo.clear_route_cache with new added RouterInfo.reset_cache
- Merge AuthService.create_route_finder's function into AuthService.refresh_data, and remove unnecessary AuthService.create_route_finder.
- Adjust relevant existing unit tests, and make sure both `make lint` and `make test` all pass


#### Enhancement padding
- I've adjusted method's signature to `async def check_access(self, user_roles: set[str], allowed_roles: set[str]) -> bool` for both class AuthService and RouterInfo. Help to adjust the places downstream of the code and it's unit tests.
- Due to above change, we no longer need RouterInfo.get_roles_by_tags, as it's the only place to call this method. Remove itself and its unit tests.
- make sure both `make lint` and `make test` all pass


### Adjust RBAC page
We need to enhance the virtual page 'RBAC' in fle @faster/resources/dev-admin.html for the following points:
- Show the endpoints sorted by Path + Method by default.
- SHow the different role in different background color instead of the same.
- Adjust the logic of 'Access Leveel': If the endpoint has a 'public' tag, it belong to the 'Public' group in green background. If the endpoints has no any tag, it belong to 'Unknown' in red background color; The rest belongs to 'Restricted' in yellow background color as you already done.
- HTTP method may not need background color. But each tag has different background color will help use identify the tag quickly. shift them.
- For the backend, make sure both `make lint` and `make test` all pass
- For the frontend, you can use playwright to verify the frontend via http://127.0.0.1:8000/dev/admin(use Google OAuth user). In case of any issue or web console errors, fix them all.

### Add Metadata Page
- In file @faster/resources/dev-admin.html, add a new page for metadata management -- 'Metadata'. It contains two parts: Sys Dict and Sys Map.
- In the Sys Dict section, there is a dropdown list to represent the `category`, a `key` input field, and a `value` input field. If any of them with values, the values will be used to filter the following table. After the row to show the filters, we use a Table component to show the content of SYS_DICT under particular category. (Only category, key, value and in_used will be shown.) There also have buttons to manage the data.
-For the Sys Map section, almost the same as Sys Dict, except one thing the source of category:
  - Sys Dict category: .get_sys_dict(category="dict_category") ## so far blank, will be added later.
  - Sys Map category: .get_sys_map(category="map_category") ## so far blank, will be added later.

- In the backeend in file @faster/core/routers.py, at least add the following endpoints:
  - `/sys_dict/show` : show the content in sys_dict by category
  - `/sys_dict/adjust` : maintain the content in sys_dict by category(support add, soft delete and update existing items)
  - `/sys_map/show` : show the content in sys_map by category
  - `/sys_map/adjust` : maintain the content in sys_map by category(support add, soft delete and update existing items)
  - there are four existing repository methods for your use in the @faster/core/services.py: get_sys_dict/set_sys_dict/get_sys_map/set_sys_map

- For the backend, add or enhance unit tests, and make sure both `make lint` and `make test` all pass
- For the frontend, you can use playwright to verify the frontend via http://127.0.0.1:8000/dev/admin(use Google OAuth user). In case of any issue or web console errors, fix them all.

#### bug fix on Metadata page
When I try to run the application, I encounter the following errors:
- call `/dev/sys_dict/show` without Bearer token
- call `/dev/sys_map/show` without Bearer token
- call to non existing endpoint `/auth/metadata`

Here comes the log for your reference:
```
18 23:08:23.281 [error   ] [101b2ce4] [auth] Authentication error: Route not found :/auth/metadata
18 23:08:23.316 [info    ] 127.0.0.1:63472 - "GET /auth/metadata HTTP/1.1" 404
18 23:08:23.328 [debug   ] [ad7e12d7] No Authorization header found in request
18 23:08:23.329 [error   ] [ad7e12d7] [auth] Authentication error: Invalid token or already logged out: /dev/sys_dict/show
18 23:08:23.348 [info    ] 127.0.0.1:63472 - "GET /dev/sys_dict/show HTTP/1.1" 401
18 23:08:23.349 [debug   ] [b093197f] No Authorization header found in request
18 23:08:23.349 [error   ] [b093197f] [auth] Authentication error: Invalid token or already logged out: /dev/sys_map/show
18 23:08:23.370 [info    ] 127.0.0.1:63474 - "GET /dev/sys_map/show HTTP/1.1" 401
```

Fix them all, and make sure both `make lint` and `make test` all pass.For the frontend, you can use playwright to verify the frontend via http://127.0.0.1:8000/dev/admin(use Google OAuth user). In case of any issue or web console errors, fix them all.
