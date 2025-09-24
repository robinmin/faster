## Prompt 2

-------------------

### Reduce raw call on `.auth.getSession`
#### Background
In the source code of frontend in file @faster/resources/dev-admin.html, we designed a dedigate class `AuthService` to act as the unique bridge to access SUpabase Auth. And that's the only way talk to Supbase Auth.

But in previous interactions with LLM, this rule has been breached. For example, I saw a few call on `.auth.getSession` (supabase.auth.getSession or _supabaseClient.auth.getSession).

#### Solution
According to the latest document of Supabase JS via MCP Context7, `.auth.getSession` is not very safe as it didn't verify the token with Supabase Auth(For example, fake toke or expiered token and etc.)

The proper way may be : alway's call `.auth.getUser` at the first time,=. If everything is okay, then we can call `.auth.getSession` from the second time for a better performance (to avoid  to check with Supabase Auth erverytime). In case of failures to verify with Supabase Auth after call `.auth.getUser` , we can cleanup the localStorage to prevent miss leading in next time.

#### Goal
- Add a dedicate meethod `getUserInfo` into class `AuthService`. This newe added method will help us to call `.auth.getUser` or `.auth.getSession` properly with well structured design for error orr exceeption handling.
- Use this new added method to replace all invalid call to `.auth.getUser` or `.auth.getSession`.
- Make sure the page diplay logic: if current session/token is valid, show page Onboarding to the new user or Page Sys Health to the existing user. If current session/token is invalid, show page login to the user.
- Use MCP playwright to access the frontend via http://127.0.0.1:8000/dev/admin. Ensure every function is works well, if any issue or errors/warnings in web console, fix all of them.

-----

Your previous task is brokeen, you need to continue your job. but two things need to clarify:
- **Playwright Config**: When using Playwright for browser automation, ensure add all of the following options to avoid Google "This browser may not be secure" error:
  --disable-blink-features=AutomationControlled
  --disable-web-security
  --disable-features=VizDisplayCompositor
  --disable-dev-shm-usage
  --no-sandbox
  --disable-extensions

- As class `AuthService` is embedded into HTML file, any `Fallback to direct call if AuthService not available` is unnecessary, remove them all.

#### Refactory Frontend structured

it's time for us to do a comprehensive code review on the frontend source code and
  refactory it.
