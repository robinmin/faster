from typing import Any

from fastapi import FastAPI, Request
from fastapi.routing import APIRoute


def is_api_call(request: Request) -> bool:
    """Check if the request is an API call by checking the Accept header."""

    accept_header = request.headers.get("accept")
    return (accept_header and "application/json" in accept_header) or False


def get_all_endpoints(app: FastAPI) -> list[dict[str, Any]]:
    """
    Return a list of all endpoints with method, path, tags, and function name.
    Includes routes defined via decorators and normal route registration.
    """
    endpoints = []

    for route in app.routes:
        if isinstance(route, APIRoute):
            endpoint_info = {
                "path": route.path,
                "methods": list(route.methods),  # set -> list
                "tags": route.tags or [],
                "name": route.name,  # function name
                "endpoint_func": route.endpoint.__name__,  # actual function name
            }
            endpoints.append(endpoint_info)

    return endpoints


def get_current_endpoint(request: Request, endpoints: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    Return the endpoint info for the current request.

    Args:
        request: FastAPI Request object
        endpoints: List returned by get_all_endpoints

    Returns:
        The matching endpoint dict or None if not found
    """
    request_path = request.url.path
    request_method = request.method.upper()

    # TODO: We enabled HEAD method support here, need to check if it's necessary to balance the convinence and security
    for ep in endpoints:
        if request_path == ep.get("path") and (request_method == "HEAD" or request_method in ep.get("methods", [])):
            return ep

    return None
