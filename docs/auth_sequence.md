## Sequence Diagram with Supabase Auth

### 1, User Registration Flow

Shows how new and existing users are handled differently during Google OAuth registration

```mermaid
sequenceDiagram
    participant User as User
    participant WebApp as Web App<br/>(with Supabase JS)
    participant Supabase as Supabase Auth
    participant Google as Google OAuth
    participant FastAPI as FastAPI Backend

    Note over User,FastAPI: User Registration Flow with Google OAuth

    User->>WebApp: 1. Click "Sign Up with Google"
    WebApp->>Supabase: 2. signInWithOAuth({provider: 'google'})
    Supabase-->>WebApp: 3. Return Google OAuth URL
    WebApp->>Google: 4. Redirect to Google OAuth

    Note over Google: User enters credentials<br/>or selects account
    User->>Google: 5. Enter credentials/select account
    Google-->>User: 6. Show consent screen (first time)
    User->>Google: 7. Grant permissions

    Google->>WebApp: 8. Redirect with auth code
    WebApp->>Supabase: 9. Auto-handle auth callback
    Supabase->>Google: 10. Exchange code for access token
    Google-->>Supabase: 11. Return access token & user profile

    alt New User
        Note over Supabase: Create new user account<br/>in auth.users table
        Supabase->>Supabase: 12a. Create user record
        Supabase-->>WebApp: 13a. Auth event: SIGNED_IN + session
        WebApp-->>User: 14a. Welcome! Complete profile setup

        opt Profile Setup
            User->>WebApp: 15a. Fill additional profile info
            WebApp->>FastAPI: 16a. Update user profile
            FastAPI->>Supabase: 17a. Insert/update profile data
            Supabase-->>FastAPI: 18a. Confirm update
            FastAPI-->>WebApp: 19a. Profile updated
        end
    else Existing User
        Supabase-->>WebApp: 13b. Auth event: SIGNED_IN + session
        WebApp-->>User: 14b. Welcome back! Redirect to dashboard
    end
```

Client side code for user registration flow (React/Vue/vanilla JS):

```javascript
// Registration is identical to login with OAuth
const { data, error } = await supabase.auth.signInWithOAuth({
  provider: "google",
  options: {
    redirectTo: "http://localhost:3000/onboarding", // Different redirect for new users
  },
});
// Listen for auth state to handle new vs returning users
supabase.auth.onAuthStateChange(async (event, session) => {
  if (event === "SIGNED_IN") {
    // Check if user needs onboarding
    const { data: profile } = await supabase
      .from("profiles")
      .select("*")
      .eq("id", session.user.id)
      .single();

    if (!profile) {
      // New user - redirect to onboarding
      router.push("/onboarding");
    } else {
      // Existing user - redirect to dashboard
      router.push("/dashboard");
    }
  }
});
```

### 2, User Login Flow

Shows how new and existing users are handled differently during Google OAuth login

```mermaid
sequenceDiagram
    participant User as User
    participant WebApp as Web App<br/>(with Supabase JS)
    participant Supabase as Supabase Auth
    participant Google as Google OAuth
    participant FastAPI as FastAPI Backend

    User->>WebApp: 1. Click "Login with Google"
    WebApp->>Supabase: 2. signInWithOAuth({provider: 'google'})
    Supabase-->>WebApp: 3. Return Google OAuth URL
    WebApp->>Google: 4. Redirect to Google OAuth

    Note over Google: User enters credentials
    User->>Google: 5. Enter Google credentials
    Google-->>User: 6. Show consent screen
    User->>Google: 7. Grant permissions

    Google->>WebApp: 8. Redirect with auth code (to callback URL)
    WebApp->>Supabase: 9. Auto-handle auth callback
    Supabase->>Google: 10. Exchange code for access token
    Google-->>Supabase: 11. Return access token & user info
    Supabase-->>WebApp: 12. Auth state change event + session

    Note over WebApp: Session automatically stored<br/>in localStorage/sessionStorage
    WebApp-->>User: 13. Login successful, redirect to dashboard

    Note over WebApp,FastAPI: For protected API calls
    WebApp->>FastAPI: 14. API request with JWT token
    FastAPI->>Supabase: 15. Verify JWT token
    Supabase-->>FastAPI: 16. Return user info if valid
    FastAPI-->>WebApp: 17. Return protected data
```

Client side code for user login flow (React/Vue/vanilla JS):

```javascript
import { createClient } from "@supabase/supabase-js";

const supabase = createClient("your-url", "your-anon-key");

// Login with Google
async function loginWithGoogle() {
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: "google",
    options: {
      redirectTo: "http://localhost:3000/dashboard",
    },
  });
}

// Listen for auth changes
supabase.auth.onAuthStateChange((event, session) => {
  if (event === "SIGNED_IN") {
    // User is logged in, session contains JWT
    console.log("User logged in:", session.user);
  }
});
```

### 3, User Logout Flow

Show to logout of Supabase and FastAPI

```mermaid
sequenceDiagram
    participant User as User
    participant WebApp as Web App<br/>(with Supabase JS)
    participant Supabase as Supabase Auth
    participant FastAPI as FastAPI Backend

    Note over User,FastAPI: User Logout Flow

    User->>WebApp: 1. Click "Logout"
    WebApp->>Supabase: 2. signOut()
    Supabase->>Supabase: 3. Invalidate session/tokens
    Supabase-->>WebApp: 4. Auth event: SIGNED_OUT

    Note over WebApp: Clear local session data<br/>Remove tokens from storage
    WebApp->>WebApp: 5. Clear app state & redirect
    WebApp-->>User: 6. Redirect to login page

    Note over WebApp,FastAPI: Subsequent API calls will fail
    WebApp->>FastAPI: 7. API request (no valid token)
    FastAPI-->>WebApp: 8. 401 Unauthorized
```

Client-side code for handling auth state changes (React/Vue/vanilla JS):

```javascript
// Simple logout
async function logout() {
  const { error } = await supabase.auth.signOut();
  if (!error) {
    // Supabase automatically clears local storage
    // Redirect to login page
    router.push("/login");
  }
}
```
