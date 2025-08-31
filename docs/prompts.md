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
