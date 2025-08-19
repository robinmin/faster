#!/usr/bin/env python3

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request, Response

from faster.core.bootstrap import create_app, run_app
from faster.core.redis import RedisManager, get_redis

# Create the application
app = create_app()


# Add a custom route
@app.get("/custom")
async def custom_endpoint(
    redis: Annotated[RedisManager, Depends(get_redis)],
) -> dict[str, str]:
    await redis.ping()
    return {"message": "Custom endpoint - Redis is connected!"}


# Add custom middleware
@app.middleware("http")
async def custom_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    response = await call_next(request)
    response.headers["X-Custom-Header"] = "value"
    return response


# Run the application
if __name__ == "__main__":
    run_app(app)
