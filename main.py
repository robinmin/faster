#!/usr/bin/env python3

from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from faster.core.bootstrap import create_app, run_app
from faster.core.redis import redis_mgr

# Create the application
app = create_app()


# Add a custom route
@app.get("/custom", tags=["public"])
async def custom_endpoint(
    # redis: Annotated[RedisManager, Depends(get_redis)],
) -> dict[str, str]:
    try:
        result = await redis_mgr.ping()
        if result:
            return {"message": "Custom endpoint - Redis is connected!"}
        return {"message": "Custom endpoint - Redis is not connected."}
    except Exception:
        return {"message": "Custom endpoint - Redis is not connected or unavailable."}


# Add custom middleware
@app.middleware("http")
async def custom_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    response = await call_next(request)
    response.headers["X-Custom-Header"] = "value"
    return response


# Run the application
if __name__ == "__main__":
    run_app(app)
