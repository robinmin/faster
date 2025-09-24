"""
Simple FastAPI Client Generator

A clean Python class to generate JavaScript/TypeScript API clients
from FastAPI OpenAPI schema.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import importlib.metadata
import re
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from fastapi import FastAPI
    from fastapi.routing import APIRoute
else:
    try:
        from fastapi import FastAPI
        from fastapi.routing import APIRoute
    except ImportError:
        FastAPI = Any
        APIRoute = Any


@dataclass
class ClientConfig:
    """Configuration for client generation"""

    language: Literal["javascript", "typescript"] = "javascript"
    http_client: Literal["fetch", "axios"] = "fetch"
    class_name: str = "ApiClient"
    base_url: str | None = None
    enable_auto_auth: bool = True  # Enable automatic bearer token handling


class ClientGenerator:
    """
    FastAPI Client Code Generator.

    Generates type-safe client code for JavaScript/TypeScript applications
    from FastAPI OpenAPI schemas, supporting both fetch API and axios.

    Features:
    - TypeScript interface generation from OpenAPI schemas
    - Support for both fetch and axios HTTP clients
    - Automatic method naming from operation IDs or paths
    - Proper error handling and response typing
    - Clean, maintainable generated code

    Usage:
        generator = ClientGenerator()

        # From FastAPI app instance
        js_code = generator.generate_from_app(app, ClientConfig(language='javascript'))

        # From OpenAPI schema dict
        ts_code = generator.generate_from_schema(schema, ClientConfig(language='typescript'))
    """

    def generate_from_app(self, app: FastAPI, config: ClientConfig | None = None) -> str:
        """Generate client code from FastAPI app instance (OpenAPI schema only)"""
        if config is None:
            config = ClientConfig()

        # Get OpenAPI schema from FastAPI app
        schema = app.openapi()

        # Extract public endpoints if auto-auth is enabled
        if config.enable_auto_auth:
            public_endpoints: list[str] = []
            for route in app.routes:
                if isinstance(route, APIRoute) and hasattr(route, "tags") and route.tags and "public" in route.tags:
                    path = route.path[1:] if route.path.startswith("/") else route.path
                    endpoint_pattern = f"/{path}"
                    if endpoint_pattern not in public_endpoints:
                        public_endpoints.append(endpoint_pattern)
            schema["x-public-endpoints"] = public_endpoints

        return self.generate_from_schema(schema, config)

    def generate_from_app_all_routes(self, app: FastAPI, config: ClientConfig | None = None) -> str:
        """Generate client code from ALL FastAPI routes (including those excluded from OpenAPI schema)"""
        if config is None:
            config = ClientConfig()

        # Get all routes from FastAPI app, not just OpenAPI schema
        all_routes_schema = self._extract_all_routes_schema(app)
        return self.generate_from_schema(all_routes_schema, config)

    def _extract_all_routes_schema(self, app: FastAPI) -> dict[str, Any]:
        """Extract schema from ALL routes in FastAPI app."""
        paths: dict[str, Any] = {}
        base_schema = app.openapi()
        components = base_schema.get("components", {"schemas": {}})
        public_endpoints: list[str] = []

        for route in app.routes:
            if isinstance(route, APIRoute):
                path = route.path[1:] if route.path.startswith("/") else route.path
                methods = [m.lower() for m in route.methods]

                for method in methods:
                    if method not in ["get", "post", "put", "delete", "patch", "head", "options"]:
                        continue

                    operation = self._create_operation_spec(route, method, path)

                    # Check if route has 'public' tag
                    if hasattr(route, "tags") and route.tags and "public" in route.tags:
                        endpoint_pattern = f"/{path}"
                        if endpoint_pattern not in public_endpoints:
                            public_endpoints.append(endpoint_pattern)
                        operation["tags"] = route.tags

                    if path not in paths:
                        paths[path] = {}
                    paths[path][method] = operation

        return {
            "openapi": "3.0.0",
            "info": base_schema.get("info", {"title": "API", "version": "1.0.0"}),
            "paths": paths,
            "components": components,
            "x-public-endpoints": public_endpoints,  # Store public endpoints in schema
        }

    def _create_operation_spec(self, route: APIRoute, method: str, path: str) -> dict[str, Any]:
        """Create operation spec for route."""
        operation: dict[str, Any] = {
            "responses": {
                "200": {
                    "description": "Successful response",
                    "content": {"application/json": {"schema": {"type": "object"}}},
                }
            }
        }

        operation["operationId"] = self._get_operation_id(route, method, path)

        if "{" in route.path and "}" in route.path:
            operation["parameters"] = self._extract_path_parameters(route.path)

        if method in ["post", "put", "patch"]:
            operation["requestBody"] = {"content": {"application/json": {"schema": {"type": "object"}}}}

        return operation

    def _get_operation_id(self, route: APIRoute, method: str, path: str) -> str:
        """Get operation ID from route or generate one."""
        if hasattr(route, "operation_id") and route.operation_id:
            return route.operation_id

        clean_path = re.sub(r"\{[^}]+\}", "", path).strip("/")
        if clean_path:
            parts = clean_path.split("/")
            # Handle underscores, dots, hyphens, and other special characters for proper camelCase
            processed_parts = []
            for part in parts:
                # Replace dots, hyphens with underscores, then split by underscores
                sanitized_part = part.replace(".", "_").replace("-", "_")
                subparts = sanitized_part.split("_")
                camel_part = "".join(word.capitalize() for word in subparts if word and word.isalnum())
                if camel_part:  # Only add non-empty parts
                    processed_parts.append(camel_part)

            return method + "".join(processed_parts)
        return f"{method}Api"

    def _extract_path_parameters(self, path: str) -> list[dict[str, Any]]:
        """Extract path parameters."""
        parameters: list[dict[str, Any]] = []
        path_params = re.findall(r"\{([^}]+)\}", path)
        for param_name in path_params:
            parameters.append({"name": param_name, "in": "path", "required": True, "schema": {"type": "string"}})
        return parameters

    def generate_from_schema(self, schema: dict[str, Any], config: ClientConfig | None = None) -> str:
        """Generate client code from OpenAPI schema dictionary"""
        if config is None:
            config = ClientConfig()

        self.schema = schema
        self.config = config

        # Generate the complete client
        if config.language == "typescript":
            return self._generate_typescript_client()
        return self._generate_javascript_client()

    def _generate_javascript_client(self) -> str:
        """Generate JavaScript client"""
        header = self._generate_header_comment()
        base_url = self.config.base_url or self._get_base_url()

        if self.config.http_client == "axios":
            base_class = self._js_axios_base(base_url)
            methods = self._generate_axios_methods()
        else:
            base_class = self._js_fetch_base(base_url)
            methods = self._generate_fetch_methods()

        exports = self._js_exports()

        return header + base_class + methods + exports

    def _generate_typescript_client(self) -> str:
        """Generate TypeScript client"""
        header = self._generate_header_comment()
        base_url = self.config.base_url or self._get_base_url()

        # Generate interfaces
        interfaces = self._generate_ts_interfaces()

        if self.config.http_client == "axios":
            imports = "import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';\n\n"
            base_class = self._ts_axios_base(base_url)
            methods = self._generate_axios_methods(typescript=True)
        else:
            imports = ""
            base_class = self._ts_fetch_base(base_url)
            methods = self._generate_fetch_methods(typescript=True)

        exports = f"""
}}

// ====================
// API Definitions End
// ====================

export default {self.config.class_name};
"""

        return header + imports + interfaces + base_class + methods + exports

    def _get_base_url(self) -> str:
        """Extract base URL from schema"""
        servers = self.schema.get("servers", [])
        return servers[0]["url"] if servers else "http://localhost:8000"

    def _generate_header_comment(self) -> str:
        """Generate header comment with generation info"""
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            version = importlib.metadata.version("faster")
        except importlib.metadata.PackageNotFoundError:
            version = "0.1.0"  # Fallback version

        return f"""/*
 * This file is auto-generated. DO NOT EDIT MANUALLY!
 *
 * Generated by: Faster Framework v{version}
 * Generated at: {timestamp}
 * Language: {self.config.language}
 * HTTP Client: {self.config.http_client}
 *
 * Any manual changes will be overwritten on next generation.
 */

"""

    def _generate_method_comment(self, path: str, method: str, summary: str, description: str) -> str:
        """Generate JSDoc comment for a method"""
        comment_lines = ["  /**"]

        if summary:
            comment_lines.append(f"   * {summary}")
        else:
            comment_lines.append(f"   * {method} {path}")

        if description and description != summary:
            comment_lines.append(f"   * {description}")

        comment_lines.append("   */")
        return "\n".join(comment_lines)

    def _js_fetch_base(self, base_url: str) -> str:
        auth_logic = ""
        if self.config.enable_auto_auth:
            auth_logic = """
    // Auto-add Bearer token if not already present and getToken is available
    if (this.getToken && !requestOptions.headers?.Authorization) {
      const token = await this.getToken();
      if (token) {
        requestOptions.headers.Authorization = `Bearer ${token}`;
      }
    }"""

        public_request_method = ""
        if self.config.enable_auto_auth:
            public_request_method = """
  async _makePublicRequest(url, options) {
    const fullUrl = this.baseURL + (url.startsWith('/') ? url : '/' + url);
    const requestOptions = {
      ...this.defaultOptions,
      ...options,
      headers: { ...this.defaultOptions.headers, ...options.headers },
    };

    const response = await fetch(fullUrl, requestOptions);

    if (!response.ok) {
      const error = new Error(`HTTP ${response.status}: ${response.statusText}`);
      error.status = response.status;
      throw error;
    }

    const contentType = response.headers.get('content-type');
    return contentType?.includes('application/json') ? response.json() : response.text();
  }"""

        return rf"""class {self.config.class_name} {{
  constructor(baseURL = '{base_url}', defaultOptions = {{}}) {{
    this.baseURL = baseURL.replace(/\/$/, '');
    this.defaultOptions = {{
      headers: {{ 'Content-Type': 'application/json' }},
      ...defaultOptions
    }};
{
            '''
    // Token retrieval function (can be set by user)
    this.getToken = defaultOptions.getToken || null;'''
            if self.config.enable_auto_auth
            else ""
        }
  }}

  async _makeRequest(url, options) {{
    const fullUrl = this.baseURL + (url.startsWith('/') ? url : '/' + url);
    const requestOptions = {{
      ...this.defaultOptions,
      ...options,
      headers: {{ ...this.defaultOptions.headers, ...options.headers }},
    }};{auth_logic}

    const response = await fetch(fullUrl, requestOptions);

    if (!response.ok) {{
      const error = new Error(`HTTP ${{response.status}}: ${{response.statusText}}`);
      error.status = response.status;
      throw error;
    }}

    const contentType = response.headers.get('content-type');
    return contentType?.includes('application/json') ? response.json() : response.text();
  }}{public_request_method}

  setAuth(token, type = 'Bearer') {{
    this.defaultOptions.headers = {{
      ...this.defaultOptions.headers,
      Authorization: `${{type}} ${{token}}`
    }};
  }}

  setHeaders(headers) {{
    this.defaultOptions.headers = {{ ...this.defaultOptions.headers, ...headers }};
  }}
{
            '''
  setTokenProvider(getTokenFn) {
    this.getToken = getTokenFn;
  }'''
            if self.config.enable_auto_auth
            else ""
        }
"""

    def _js_axios_base(self, base_url: str) -> str:
        auth_interceptor = ""
        if self.config.enable_auto_auth:
            auth_interceptor = """
    // Add request interceptor for automatic authentication
    this.axios.interceptors.request.use(
      async config => {
        // Auto-add Bearer token if not already present and getToken is available
        if (this.getToken && !config.headers?.Authorization) {
          const token = await this.getToken();
          if (token) {
            config.headers.Authorization = `Bearer ${token}`;
          }
        }
        return config;
      },
      error => Promise.reject(error)
    );"""

        public_axios_creation = ""
        if self.config.enable_auto_auth:
            public_axios_creation = r"""
    // Create separate axios instance for public requests (without auth interceptor)
    this.publicAxios = axios.create({
      baseURL: baseURL.replace(/\/$/, ''),
      timeout: 10000,
      headers: { 'Content-Type': 'application/json' },
      ...config,
    });

    this.publicAxios.interceptors.response.use(
      response => response,
      error => {
        const apiError = new Error(error.message);
        apiError.status = error.response?.status || 0;
        throw apiError;
      }
    );"""

        return rf"""class {self.config.class_name} {{
  constructor(baseURL = '{base_url}', config = {{}}) {{
{
            '''
    // Token retrieval function (can be set by user)
    this.getToken = config.getToken || null;'''
            if self.config.enable_auto_auth
            else ""
        }

    this.axios = axios.create({{
      baseURL: baseURL.replace(/\/$/, ''),
      timeout: 10000,
      headers: {{ 'Content-Type': 'application/json' }},
      ...config,
    }});{auth_interceptor}

    this.axios.interceptors.response.use(
      response => response,
      error => {{
        const apiError = new Error(error.message);
        apiError.status = error.response?.status || 0;
        throw apiError;
      }}
    );{public_axios_creation}
  }}

  setAuth(token, type = 'Bearer') {{
    this.axios.defaults.headers.common['Authorization'] = `${{type}} ${{token}}`;
  }}

  setHeaders(headers) {{
    Object.assign(this.axios.defaults.headers.common, headers);
  }}
{
            '''
  setTokenProvider(getTokenFn) {
    this.getToken = getTokenFn;
  }'''
            if self.config.enable_auto_auth
            else ""
        }
"""

    def _ts_fetch_base(self, base_url: str) -> str:
        auth_logic = ""
        if self.config.enable_auto_auth:
            auth_logic = """
    // Auto-add Bearer token if not already present and getToken is available
    if (this.getToken && !requestOptions.headers?.Authorization) {
      const token = await this.getToken();
      if (token) {
        requestOptions.headers.Authorization = `Bearer ${token}`;
      }
    }"""

        public_request_method = ""
        if self.config.enable_auto_auth:
            public_request_method = """
  private async _makePublicRequest<T = any>(url: string, options: RequestInit): Promise<T> {
    const fullUrl = this.baseURL + (url.startsWith('/') ? url : '/' + url);
    const requestOptions: RequestInit = {
      ...this.defaultOptions,
      ...options,
      headers: { ...this.defaultOptions.headers, ...options.headers },
    };

    const response = await fetch(fullUrl, requestOptions);

    if (!response.ok) {
      const error = new Error(`HTTP ${response.status}: ${response.statusText}`) as any;
      error.status = response.status;
      throw error;
    }

    const contentType = response.headers.get('content-type');
    return contentType?.includes('application/json') ? response.json() : response.text();
  }"""

        return rf"""interface RequestOptions {{
  headers?: Record<string, string>;
{"  getToken?: () => string | null;" if self.config.enable_auto_auth else ""}
  [key: string]: any;
}}

export class {self.config.class_name} {{
  private baseURL: string;
  private defaultOptions: RequestOptions;
{"  private getToken: (() => string | null) | null;" if self.config.enable_auto_auth else ""}

  constructor(baseURL: string = '{base_url}', defaultOptions: RequestOptions = {{}}) {{
    this.baseURL = baseURL.replace(/\/$/, '');
    this.defaultOptions = {{
      headers: {{ 'Content-Type': 'application/json' }},
      ...defaultOptions
    }};
{
            '''
    // Token retrieval function (can be set by user)
    this.getToken = defaultOptions.getToken || null;'''
            if self.config.enable_auto_auth
            else ""
        }
  }}

  private async _makeRequest<T = any>(url: string, options: RequestInit): Promise<T> {{
    const fullUrl = this.baseURL + (url.startsWith('/') ? url : '/' + url);
    const requestOptions: RequestInit = {{
      ...this.defaultOptions,
      ...options,
      headers: {{ ...this.defaultOptions.headers, ...options.headers }},
    }};{auth_logic}

    const response = await fetch(fullUrl, requestOptions);

    if (!response.ok) {{
      const error = new Error(`HTTP ${{response.status}}: ${{response.statusText}}`) as any;
      error.status = response.status;
      throw error;
    }}

    const contentType = response.headers.get('content-type');
    return contentType?.includes('application/json') ? response.json() : response.text();
  }}{public_request_method}

  public setAuth(token: string, type: string = 'Bearer'): void {{
    this.defaultOptions.headers = {{
      ...this.defaultOptions.headers,
      Authorization: `${{type}} ${{token}}`
    }};
  }}

  public setHeaders(headers: Record<string, string>): void {{
    this.defaultOptions.headers = {{ ...this.defaultOptions.headers, ...headers }};
  }}
{
            '''
  public setTokenProvider(getTokenFn: () => string | null): void {
    this.getToken = getTokenFn;
  }'''
            if self.config.enable_auto_auth
            else ""
        }
"""

    def _ts_axios_base(self, base_url: str) -> str:
        auth_interceptor = ""
        if self.config.enable_auto_auth:
            auth_interceptor = """
    // Add request interceptor for automatic authentication
    this.axios.interceptors.request.use(
      async config => {
        // Auto-add Bearer token if not already present and getToken is available
        if (this.getToken && !config.headers?.Authorization) {
          const token = await this.getToken();
          if (token) {
            config.headers.Authorization = `Bearer ${token}`;
          }
        }
        return config;
      },
      error => Promise.reject(error)
    );"""

        public_axios_creation = ""
        if self.config.enable_auto_auth:
            public_axios_creation = r"""
    // Create separate axios instance for public requests (without auth interceptor)
    this.publicAxios = axios.create({
      baseURL: baseURL.replace(/\/$/, ''),
      timeout: 10000,
      headers: { 'Content-Type': 'application/json' },
      ...config,
    });

    this.publicAxios.interceptors.response.use(
      response => response,
      error => {
        const apiError = new Error(error.message) as any;
        apiError.status = error.response?.status || 0;
        throw apiError;
      }
    );"""

        return rf"""interface RequestConfig extends AxiosRequestConfig {{
{"  getToken?: () => string | null;" if self.config.enable_auto_auth else ""}
}}

export class {self.config.class_name} {{
  private axios: AxiosInstance;
{"  private publicAxios: AxiosInstance;" if self.config.enable_auto_auth else ""}
{"  private getToken: (() => string | null) | null;" if self.config.enable_auto_auth else ""}

  constructor(baseURL: string = '{base_url}', config: RequestConfig = {{}}) {{
{
            '''
    // Token retrieval function (can be set by user)
    this.getToken = config.getToken || null;'''
            if self.config.enable_auto_auth
            else ""
        }

    this.axios = axios.create({{
      baseURL: baseURL.replace(/\/$/, ''),
      timeout: 10000,
      headers: {{ 'Content-Type': 'application/json' }},
      ...config,
    }});{auth_interceptor}

    this.axios.interceptors.response.use(
      response => response,
      error => {{
        const apiError = new Error(error.message) as any;
        apiError.status = error.response?.status || 0;
        throw apiError;
      }}
    );{public_axios_creation}
  }}

  public setAuth(token: string, type: string = 'Bearer'): void {{
    this.axios.defaults.headers.common['Authorization'] = `${{type}} ${{token}}`;
  }}

  public setHeaders(headers: Record<string, string>): void {{
    Object.assign(this.axios.defaults.headers.common, headers);
  }}
{
            '''
  public setTokenProvider(getTokenFn: () => string | null): void {
    this.getToken = getTokenFn;
  }'''
            if self.config.enable_auto_auth
            else ""
        }
"""

    def _is_public_operation(self, operation: dict[str, Any]) -> bool:
        """Check if operation is public based on tags"""
        tags = operation.get("tags", [])
        return "public" in tags

    def _generate_fetch_methods(self, typescript: bool = False) -> str:
        """Generate methods using fetch API"""
        methods = []
        paths = self.schema.get("paths", {})

        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method.lower() in ["get", "post", "put", "delete", "patch"]:
                    method_code = self._create_fetch_method(path, method, operation, typescript)
                    methods.append(method_code)

        return "".join(methods)

    def _generate_axios_methods(self, typescript: bool = False) -> str:
        """Generate methods using axios"""
        methods = []
        paths = self.schema.get("paths", {})

        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method.lower() in ["get", "post", "put", "delete", "patch"]:
                    method_code = self._create_axios_method(path, method, operation, typescript)
                    methods.append(method_code)

        return "".join(methods)

    def _create_fetch_method(self, path: str, method: str, operation: dict[str, Any], typescript: bool) -> str:
        """Create a single fetch method"""
        method_name = self._get_method_name(path, method, operation)
        params = self._get_parameters(operation)

        # Generate method comment
        summary = operation.get("summary", "")
        description = operation.get("description", "")
        method_comment = self._generate_method_comment(path, method.upper(), summary, description)

        # Build parameter list
        param_list = []
        if params["path_params"]:
            param_list.extend([p["name"] for p in params["path_params"]])
        if params["body_param"]:
            param_list.append("data")
        if params["query_params"]:
            param_list.append("queryParams = {}")
        param_list.append("options = {}")

        if typescript:
            param_str = self._build_ts_params(params, param_list)
            return_type = f": Promise<{self._get_response_type(operation)}>"
        else:
            param_str = ", ".join(param_list)
            return_type = ""

        # Build method body
        url_construction = f"let url = `{path}`;"
        for param in params["path_params"]:
            url_construction = url_construction.replace(f"{{{param['original_name']}}}", f"${{{param['name']}}}")

        query_construction = ""
        if params["query_params"]:
            query_construction = """
    const urlParams = new URLSearchParams();
    Object.entries(queryParams).forEach(([key, value]) => {
      if (value != null) urlParams.append(key, String(value));
    });
    if (urlParams.toString()) url += '?' + urlParams.toString();"""

        body_setup = f"""
    const requestOptions = {{
      ...options,
      method: '{method.upper()}',
      headers: {{ ...options.headers }},"""

        if params["body_param"]:
            body_setup += """
      body: JSON.stringify(data),"""

        body_setup += "\n    };"

        # Determine which request method to use
        is_public = self._is_public_operation(operation)
        request_method = "_makePublicRequest" if is_public and self.config.enable_auto_auth else "_makeRequest"

        return f"""
{method_comment}
  async {method_name}({param_str}){return_type} {{
    {url_construction}{query_construction}{body_setup}
    return this.{request_method}(url, requestOptions);
  }}
"""

    def _create_axios_method(self, path: str, method: str, operation: dict[str, Any], typescript: bool) -> str:
        """Create a single axios method"""
        method_name = self._get_method_name(path, method, operation)
        params = self._get_parameters(operation)

        # Generate method comment
        summary = operation.get("summary", "")
        description = operation.get("description", "")
        method_comment = self._generate_method_comment(path, method.upper(), summary, description)

        # Build parameter list
        param_list = []
        if params["path_params"]:
            param_list.extend([p["name"] for p in params["path_params"]])
        if params["body_param"]:
            param_list.append("data")
        if params["query_params"]:
            param_list.append("queryParams = {}")
        param_list.append("config = {}")

        if typescript:
            param_str = self._build_ts_params(params, param_list, axios=True)
            return_type = f": Promise<{self._get_response_type(operation)}>"
        else:
            param_str = ", ".join(param_list)
            return_type = ""

        # Build method body
        url_construction = f"let url = `{path}`;"
        for param in params["path_params"]:
            url_construction = url_construction.replace(f"{{{param['original_name']}}}", f"${{{param['name']}}}")

        axios_config = f"""
    const axiosConfig = {{
      ...config,
      method: '{method.lower()}',
      url,"""

        if params["query_params"]:
            axios_config += """
      params: queryParams,"""

        if params["body_param"]:
            axios_config += """
      data,"""

        axios_config += "\n    };"

        # Determine which axios instance to use
        is_public = self._is_public_operation(operation)
        axios_instance = "publicAxios" if is_public and self.config.enable_auto_auth else "axios"

        return f"""
{method_comment}
   async {method_name}({param_str}){return_type} {{
     {url_construction}{axios_config}
     const response = await this.{axios_instance}.request(axiosConfig);
     return response.data;
   }}
 """

    def _get_method_name(self, path: str, method: str, operation: dict[str, Any]) -> str:
        """
        Generate a clean method name from path and operation.

        Priority:
        1. Use operationId if available (converted to camelCase)
        2. Generate from path segments (method + path parts)
        3. Fallback to generic name
        """
        # Use operationId if available
        if operation.get("operationId"):
            return self._to_camel_case(operation["operationId"])

        # Generate from path
        clean_path = re.sub(r"\{[^}]+\}", "", path).strip("/")
        if not clean_path:
            # Root path fallback
            return f"{method.lower()}Api"

        parts = [part for part in clean_path.split("/") if part]
        if not parts:
            return f"{method.lower()}Api"

        # Create method name: method + capitalized path segments
        # Handle underscores, dots, hyphens, and other special characters for proper camelCase
        processed_parts = []
        for part in parts:
            # Replace dots, hyphens with underscores, then split by underscores
            sanitized_part = part.replace(".", "_").replace("-", "_")
            subparts = sanitized_part.split("_")
            camel_part = "".join(word.capitalize() for word in subparts if word and word.isalnum())
            if camel_part:  # Only add non-empty parts
                processed_parts.append(camel_part)

        method_name = method.lower() + "".join(processed_parts)

        # Ensure it's a valid identifier
        if not method_name[0].isalpha() and method_name[0] != "_":
            method_name = "api" + method_name

        return method_name

    def _to_camel_case(self, snake_str: str) -> str:
        """Convert snake_case to camelCase"""
        components = snake_str.split("_")
        return components[0] + "".join(word.capitalize() for word in components[1:])

    def _get_parameters(self, operation: dict[str, Any]) -> dict[str, Any]:
        """Extract parameters from operation"""
        path_params = []
        query_params = []
        body_param = None

        # Process parameters
        for param in operation.get("parameters", []):
            param_info = {
                "name": self._to_camel_case(param["name"].replace("-", "_")),
                "original_name": param["name"],
                "required": param.get("required", False),
                "type": self._get_type(param.get("schema", {})),
            }

            if param["in"] == "path":
                path_params.append(param_info)
            elif param["in"] == "query":
                query_params.append(param_info)

        # Check for request body
        if "requestBody" in operation:
            body_param = True

        return {"path_params": path_params, "query_params": query_params, "body_param": body_param}

    def _build_ts_params(self, params: dict[str, Any], param_list: list[str], axios: bool = False) -> str:
        """Build TypeScript parameter string"""
        ts_params = []

        for param in params["path_params"]:
            ts_params.append(f"{param['name']}: {param['type']}")

        if params["body_param"]:
            ts_params.append("data: any")

        if params["query_params"]:
            ts_params.append("queryParams?: Record<string, any>")

        if axios:
            ts_params.append("config?: AxiosRequestConfig")
        else:
            ts_params.append("options?: RequestOptions")

        return ", ".join(ts_params)

    def _get_type(self, schema: dict[str, Any] | None) -> str:
        """
        Convert OpenAPI schema to TypeScript type.

        Handles:
        - Basic types (string, number, boolean)
        - Arrays with item types
        - Objects and references
        - Enums
        - Nullable types
        """
        if not schema or not isinstance(schema, dict):
            return "any"

        schema_type = schema.get("type")
        nullable_raw = schema.get("nullable")
        nullable = isinstance(nullable_raw, bool) and nullable_raw

        # Handle references first (before type checking)
        if "$ref" in schema:
            ref_name = schema["$ref"].split("/")[-1]
            type_str: str = ref_name
        # Handle enums
        elif "enum" in schema:
            enum_values = schema["enum"]
            if all(isinstance(v, str) for v in enum_values):
                type_str = " | ".join(f'"{v}"' for v in enum_values)
            else:
                type_str = " | ".join(str(v) for v in enum_values)
        # Handle arrays
        elif schema_type == "array":
            items = schema.get("items", {})
            item_type = self._get_type(items)
            type_str = f"{item_type}[]"
        # Handle objects
        elif schema_type == "object":
            type_str = "Record<string, any>"
        # Handle basic types
        else:
            type_map: dict[str, str] = {
                "string": "string",
                "integer": "number",
                "number": "number",
                "boolean": "boolean",
            }
            type_str = type_map.get(schema_type, "any") if schema_type else "any"

        # Handle nullable types
        if nullable:
            type_str = f"{type_str} | null"

        return type_str

    def _get_response_type(self, operation: dict[str, Any]) -> str:
        """
        Get the response type for an operation.

        Analyzes the operation's responses to determine the most appropriate return type.
        """
        responses = operation.get("responses", {})

        # Check for successful responses in order of preference
        for status in ["200", "201", "202"]:
            if status in responses:
                response_schema = responses[status]
                content = response_schema.get("content", {})

                # Look for JSON content
                if "application/json" in content:
                    schema = content["application/json"].get("schema")
                    if schema:
                        return self._get_type(schema)

                # Default to any for successful responses
                return "any"

        # No successful responses found
        return "any"

    def _generate_ts_interfaces(self) -> str:
        """
        Generate TypeScript interfaces from OpenAPI schema components.

        Handles:
        - Object schemas with properties
        - Required vs optional fields
        - Complex nested types
        - Schema references
        """
        interfaces = []
        components = self.schema.get("components", {})
        schemas = components.get("schemas", {})

        if not schemas:
            return ""

        for name, schema in schemas.items():
            if not isinstance(schema, dict):
                continue

            # Only generate interfaces for object types
            if schema.get("type") == "object":
                interface = self._generate_single_interface(name, schema)
                if interface:
                    interfaces.append(interface)

        return "\n".join(interfaces)

    def _generate_single_interface(self, name: str, schema: dict[str, Any]) -> str:
        """Generate a single TypeScript interface"""
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        if not properties:
            # Empty interface
            return f"export interface {name} {{\n}}\n"

        props = []
        for prop_name, prop_schema in properties.items():
            optional = "?" if prop_name not in required else ""
            prop_type = self._get_type(prop_schema)

            # Add JSDoc comment if description exists
            description = prop_schema.get("description", "")
            if description:
                props.append(f"  /** {description} */")
            props.append(f"  {prop_name}{optional}: {prop_type};")

        return f"""export interface {name} {{
{chr(10).join(props)}
}}
"""

    def _js_exports(self) -> str:
        """Generate JavaScript exports"""
        return f"""
}}

// ====================
// API Definitions End
// ====================

// Export for different environments
if (typeof module !== 'undefined' && module.exports) {{
  module.exports = {self.config.class_name};
}} else if (typeof window !== 'undefined') {{
  window.{self.config.class_name} = {self.config.class_name};
}}
"""


# # Simple usage example
# if __name__ == "__main__":
#     # Example with mock schema
#     mock_schema = {
#         "paths": {
#             "/users": {
#                 "get": {
#                     "operationId": "get_users",
#                     "parameters": [
#                         {"name": "page", "in": "query", "schema": {"type": "integer"}},
#                         {"name": "limit", "in": "query", "schema": {"type": "integer"}},
#                     ],
#                 },
#                 "post": {
#                     "operationId": "create_user",
#                     "requestBody": {"content": {"application/json": {"schema": {"type": "object"}}}},
#                 },
#             }
#         }
#     }

#     generator = ClientGenerator()

#     # Generate JavaScript with Fetch
#     js_code = generator.generate_from_schema(mock_schema, ClientConfig(language="javascript", http_client="fetch"))
#     print("JavaScript + Fetch:")
#     print(js_code[:500] + "...")

#     # Generate TypeScript with Axios
#     ts_code = generator.generate_from_schema(mock_schema, ClientConfig(language="typescript", http_client="axios"))
#     print("\nTypeScript + Axios:")
#     print(ts_code[:500] + "...")
