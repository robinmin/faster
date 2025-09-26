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


### Adapt with cloudflare D1
#### Background
My application is working with local SQLite3 database very well. As we will deploy my FastAPI application to cloudflare worker. If we can adapt our application to use cloudflare D1 as our database, it will be a great.
Unfortunatly, cloudflare D1 is not support all of the SQLite3 features, for example, we can not use some way to replace the connection string with cloudflare D1.so we need to find a way to adapt our application to use cloudflare D1 as our database.

For this application, we already dedicated a file @faster/core/database.py to define how to interact with real database layer(So far, we have class `DatabaseManager` and `BaseRepository`).

If we can provide some padding orr adapter, we can adapt our application to use cloudflare D1 as our database. It will help to avoid to modify these repository classes -- they will automatically and seaml adapt with local SQLite3, cloudflare D1 and postgreSQL as well.

#### Possible Solutions
We can define a new format of connection string for cloudflare D1, for example: `d1+aiosqlite://<database_id>`, and we can use it to define environment variable `DATABASE_URL` in our application.
In class `DatabaseManager`, we can do some special check on the connection string to determine if it's a cloudflare D1 connection string. If not, we can just do nothing else. But if it is, we can do some special initialization for cloudflare D1. and etc.

Of course, we also need to modify the `BaseRepository` class to support cloudflare D1.

In case of any latest document for cloudflare D1, you can use MCP Context7 to get the latest document. In case of any existing, matured open source python library for it, you also can use it.

#### Goal
- Change file @faster/core/database.py only, to enable us to use cloudflare D1 as our database. No need to change any other repository class.
- Show me your solution first, after the confirmation with me and get every things clarified, and then we can modify the `BaseRepository` class to support cloudflare D1.
- You also need to update relevant unit tests for file @faster/core/database.py to ensure that our application can work with cloudflare D1.
- Make sure both `make lint` and `make test` pass.
