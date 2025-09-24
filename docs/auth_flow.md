# Authentication Flow Documentation

> **Note**: This document supersedes `auth_sequence.md` which contained basic sequence diagrams. All authentication flows, including comprehensive sequence diagrams, are now documented here.

## Overview

The Faster framework implements a comprehensive authentication system using Supabase Auth with a hybrid frontend/backend integration. The system supports multiple authentication methods including email/password, OAuth providers (Google, GitHub), and advanced features. Password operations and token refresh are handled directly by Supabase Auth server, while user management and session events are processed through the FastAPI backend.

## Architecture Components

### Frontend (JavaScript/Alpine.js)
- **Location**: `faster/resources/dev-admin.html`
- **Responsibilities**:
  - User interface for authentication forms
  - Supabase client integration
  - Form validation and error handling
  - Authentication state management

### Backend (FastAPI)
- **Location**: `faster/core/auth/routers.py`
- **Responsibilities**:
  - Authentication event handling and callbacks
  - User session management and blacklisting
  - Account management and administrative operations
  - User profile and role management

**Note:** Password operations (change/reset) are now handled directly by Supabase Auth server via frontend client.

### Supabase Auth Events
The system handles the following Supabase authentication events:

| Event | Description | Endpoint |
|-------|-------------|----------|
| `INITIAL_SESSION` | Emitted when Supabase client initializes | `/auth/notification/INITIAL_SESSION` |
| `SIGNED_IN` | User successfully signs in | `/auth/callback/SIGNED_IN` |
| `SIGNED_OUT` | User signs out | `/auth/callback/SIGNED_OUT` |
| `TOKEN_REFRESHED` | Access token is refreshed | *(Handled by Supabase client only)* |
| `USER_UPDATED` | User profile is updated | `/auth/callback/USER_UPDATED` or `/auth/notification/USER_UPDATED` |
| `PASSWORD_RECOVERY` | Password recovery initiated | `/auth/notification/PASSWORD_RECOVERY` |

## Authentication Flows

### 1. User Registration Flow (Email/Password)

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant S as Supabase
    participant B as Backend

    U->>F: Enter email/password/name
    F->>F: Validate form (email regex, password strength, name requirements)
    F->>S: supabase.auth.signUp()
    S->>S: Create user account, send confirmation email
    S->>F: SIGNED_IN event + session (if auto-confirm enabled)
    alt Email Confirmation Required
        S->>U: Send confirmation email
        U->>U: Click confirmation link
        S->>F: SIGNED_IN event + session
    end
    F->>B: POST /auth/callback/SIGNED_IN
    B->>B: Process registration, create user profile
    B->>F: Success response
    F->>F: Update UI, navigate to onboarding/dashboard
```

**Key Points:**
- Form validation includes email regex, password strength, and name requirements
- Supabase handles user creation and email confirmation
- Backend processes the sign-in event and creates additional user profile data
- For developer users, available roles are cached during registration
- Supports both auto-confirmation and email confirmation flows

### 2. Email/Password Login Flow

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant S as Supabase
    participant B as Backend

    U->>F: Enter email/password
    F->>F: Validate form (email regex, password requirements)
    F->>S: supabase.auth.signInWithPassword()
    S->>S: Validate credentials
    S->>F: SIGNED_IN event + session
    F->>B: POST /auth/callback/SIGNED_IN
    B->>B: Process sign-in, update user info
    B->>F: Success response
    F->>F: Update UI, navigate to dashboard
```

**Key Points:**
- Form validation includes email regex and password strength requirements
- Backend removes token from blacklist and updates user database info
- For developer users, available roles are cached

### 3. OAuth Login Flow (Google/GitHub)

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant S as Supabase
    participant O as OAuth Server<br/>(Google/GitHub)
    participant B as Backend

    U->>F: Click OAuth provider button
    F->>S: supabase.auth.signInWithOAuth()
    S->>F: Redirect to OAuth provider URL
    F->>O: Redirect to OAuth server
    O->>O: User authentication & consent
    U->>O: Enter credentials & grant permissions
    O->>S: Redirect back with authorization code
    S->>O: Exchange code for access token
    O->>S: Return access token & user profile
    S->>F: Redirect back to app with session
    S->>F: SIGNED_IN event + session
    F->>B: POST /auth/callback/SIGNED_IN
    B->>B: Process OAuth sign-in, create/update user profile
    B->>F: Success response
    F->>F: Update UI, navigate to dashboard
```

**Key Points:**
- Uses OAuth 2.0 authorization code flow
- Supports Google and GitHub providers
- Supabase handles OAuth redirect and token exchange
- Backend processes the sign-in event and manages user profile data
- Same backend processing as email/password login

### 4. Password Reset Flow

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant S as Supabase
    participant E as Email Service

    U->>F: Click "Forgot Password"
    U->>F: Enter email address
    F->>S: supabase.auth.resetPasswordForEmail()
    S->>E: Send password reset email
    E->>U: Password reset email with link
    U->>U: Click reset link in email
    S->>F: Redirect to app with recovery token
    S->>F: PASSWORD_RECOVERY event
    F->>F: Show password reset form
    U->>F: Enter new password
    F->>S: supabase.auth.updateUser({password: newPassword})
    S->>S: Update password in auth database
    S->>F: USER_UPDATED event
    F->>F: Show success message, redirect to login
```

**Key Points:**
- Frontend directly calls Supabase Auth server for password reset
- Email contains reset link that redirects back to the app
- Password update happens directly with Supabase using recovery token
- No backend server involvement in the password reset process
- Uses Supabase's built-in password reset functionality

### 5. Password Change Flow (Authenticated User)

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant S as Supabase

    U->>F: Open password change modal
    U->>F: Enter current + new password
    F->>S: supabase.auth.updateUser({password: newPassword})
    S->>S: Validate current session & update password
    S->>F: USER_UPDATED event
    F->>F: Show success message, close modal
```

**Key Points:**
- Frontend directly calls Supabase Auth server for password changes
- Requires active authenticated session
- Supabase handles password validation and update
- No backend server involvement for password changes

### 6. Logout Flow

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant S as Supabase
    participant B as Backend

    U->>F: Click logout button
    F->>S: supabase.auth.signOut()
    S->>F: SIGNED_OUT event
    F->>B: POST /auth/callback/SIGNED_OUT
    B->>B: Process logout, blacklist token
    B->>F: Success response
    F->>F: Clear local state, redirect to login
```

**Key Points:**
- Backend adds token to blacklist for security
- Clears saved page navigation state
- Redirects to authentication view

### 7. Token Refresh Flow

```mermaid
sequenceDiagram
    participant F as Frontend
    participant S as Supabase

    S->>S: Token expires, auto-refresh triggered
    S->>S: Exchange refresh token for new access token
    S->>F: TOKEN_REFRESHED event with new session
    F->>F: Update local session storage
    F->>F: Continue with refreshed session
```

**Key Points:**
- Automatic process handled entirely by Supabase client
- No user interaction or backend server involvement
- Frontend receives new session data automatically
- Maintains session continuity transparently

### 8. UserDeactivation Flow

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant B as Backend
    participant S as Supabase

    U->>F: Click deactivate account
    U->>F: Confirm with password
    F->>B: POST /auth/deactivate
    B->>B: Validate password, deactivate account
    B->>B: Process logout (blacklist token)
    B->>F: Success response
    F->>F: Redirect to login, show message
```

**Key Points:**
- Requires password confirmation
- Performs comprehensive account deactivation
- Automatic logout after deactivation

## API Endpoints Reference

### Authenticated Callback Endpoints (`/auth/callback/{event}`)
These endpoints require authentication and handle events during active sessions:

- **POST** `/auth/callback/SIGNED_IN` - Process successful sign-in
- **POST** `/auth/callback/SIGNED_OUT` - Process sign-out
- **POST** `/auth/callback/USER_UPDATED` - Process profile updates

**Note:** Token refresh is now handled automatically by Supabase client without backend involvement.

### Public Notification Endpoints (`/auth/notification/{event}`)
These endpoints are public and handle events that occur without active sessions:

- **POST** `/auth/notification/INITIAL_SESSION` - Initial session setup
- **POST** `/auth/notification/PASSWORD_RECOVERY` - Password recovery initiated
- **POST** `/auth/notification/USER_UPDATED` - Password reset completion

### Password Management Endpoints

- **POST** `/auth/password/reset/initiate` - Initiate password reset (public, legacy)
- **POST** `/auth/password/reset/confirm` - Confirm password reset (public, legacy)

**Note:** Password changes and resets are now handled directly by Supabase Auth server via frontend Supabase JS client. Backend endpoints are maintained for legacy support but are not actively used in current flows.

### Account Management Endpoints

- **GET** `/auth/profile` - Get user profile (authenticated)
- **POST** `/auth/deactivate` - Deactivate account (authenticated)

### Administrative Endpoints

- **POST** `/auth/users/{user_id}/ban` - Ban user (admin)
- **POST** `/auth/users/{user_id}/unban` - Unban user (admin)
- **POST** `/auth/users/{user_id}/roles/adjust` - Adjust user roles (admin)
- **GET** `/auth/users/{user_id}/basic` - Get user basic info (admin)

## Security Features

### Token Blacklisting
- Tokens are blacklisted on logout for security
- Refreshed tokens are removed from blacklist
- Prevents use of old tokens

### Session Management
- Automatic token refresh handled by Supabase client
- Session validation on app initialization
- Proper cleanup on logout

### Password Security
- Strong password requirements for sign-up
- Current password verification for changes
- Secure password reset flow

### Role-Based Access Control (RBAC)
- Dynamic role assignment
- Tag-based endpoint protection
- Administrative user management

## Error Handling

### Frontend Error Handling
- Form validation with user-friendly messages
- Toast notifications for auth events
- Loading states during operations
- Automatic retry for failed requests

### Backend Error Handling
- Comprehensive logging of auth events
- Graceful handling of Supabase failures
- Proper error responses to frontend
- Background task processing for reliability

## Event Logging

All authentication events are logged to the database with the following information:
- Event type and name
- User ID (when available)
- Timestamp
- Event source (supabase/user_action/admin_action)
- Additional payload data

This provides comprehensive audit trails for security and debugging purposes.