"""
Unit tests for ClientGenerator.

Tests cover:
- Client code generation for JavaScript and TypeScript
- Support for both fetch and axios HTTP clients
- Method name generation from paths and operationIds
- Type conversion from OpenAPI schemas
- Interface generation for TypeScript
- Error handling and edge cases
"""

from typing import Any

import pytest

from faster.core.client_generator import ClientConfig, ClientGenerator


class TestClientConfig:
    """Test ClientConfig dataclass"""

    def test_default_config(self) -> None:
        """Test default configuration values"""
        config = ClientConfig()
        assert config.language == "javascript"
        assert config.http_client == "fetch"
        assert config.class_name == "ApiClient"
        assert config.base_url is None

    def test_custom_config(self) -> None:
        """Test custom configuration values"""
        config = ClientConfig(
            language="typescript", http_client="axios", class_name="MyApiClient", base_url="https://api.example.com"
        )
        assert config.language == "typescript"
        assert config.http_client == "axios"
        assert config.class_name == "MyApiClient"
        assert config.base_url == "https://api.example.com"


class TestClientGenerator:
    """Test ClientGenerator functionality"""

    @pytest.fixture
    def generator(self) -> ClientGenerator:
        """Create a ClientGenerator instance"""
        return ClientGenerator()

    @pytest.fixture
    def sample_schema(self) -> dict[str, Any]:
        """Sample OpenAPI schema for testing"""
        return {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "servers": [{"url": "https://api.example.com"}],
            "paths": {
                "/users": {
                    "get": {
                        "operationId": "get_users",
                        "summary": "Get all users",
                        "parameters": [
                            {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
                            {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 10}},
                        ],
                        "responses": {
                            "200": {
                                "description": "Success",
                                "content": {
                                    "application/json": {
                                        "schema": {"type": "array", "items": {"$ref": "#/components/schemas/User"}}
                                    }
                                },
                            }
                        },
                    },
                    "post": {
                        "operationId": "create_user",
                        "summary": "Create a new user",
                        "requestBody": {
                            "required": True,
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/UserCreate"}}},
                        },
                        "responses": {
                            "201": {
                                "description": "Created",
                                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/User"}}},
                            }
                        },
                    },
                },
                "/users/{userId}": {
                    "get": {
                        "summary": "Get user by ID",
                        "parameters": [
                            {"name": "userId", "in": "path", "required": True, "schema": {"type": "string"}}
                        ],
                        "responses": {
                            "200": {
                                "description": "Success",
                                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/User"}}},
                            }
                        },
                    },
                    "put": {
                        "summary": "Update user",
                        "parameters": [
                            {"name": "userId", "in": "path", "required": True, "schema": {"type": "string"}}
                        ],
                        "requestBody": {
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/UserUpdate"}}}
                        },
                        "responses": {
                            "200": {
                                "description": "Updated",
                                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/User"}}},
                            }
                        },
                    },
                },
            },
            "components": {
                "schemas": {
                    "User": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "email": {"type": "string"},
                            "name": {"type": "string"},
                            "created_at": {"type": "string", "format": "date-time"},
                        },
                        "required": ["id", "email"],
                    },
                    "UserCreate": {
                        "type": "object",
                        "properties": {
                            "email": {"type": "string"},
                            "name": {"type": "string"},
                            "password": {"type": "string"},
                        },
                        "required": ["email", "password"],
                    },
                    "UserUpdate": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}, "email": {"type": "string"}},
                    },
                }
            },
        }

    def test_generate_from_schema_javascript_fetch(
        self, generator: ClientGenerator, sample_schema: dict[str, Any]
    ) -> None:
        """Test JavaScript + fetch generation"""
        config = ClientConfig(language="javascript", http_client="fetch")
        code = generator.generate_from_schema(sample_schema, config)

        assert "class ApiClient {" in code
        assert "async _makeRequest(url, options)" in code
        assert "fetch(fullUrl, requestOptions)" in code
        assert "getUsers(" in code
        assert "createUser(" in code
        assert "getUsers(" in code  # Second getUsers method for /users/{userId}
        assert "putUsers(" in code

    def test_generate_from_schema_typescript_fetch(
        self, generator: ClientGenerator, sample_schema: dict[str, Any]
    ) -> None:
        """Test TypeScript + fetch generation"""
        config = ClientConfig(language="typescript", http_client="fetch")
        code = generator.generate_from_schema(sample_schema, config)

        assert "export class ApiClient {" in code
        assert "private async _makeRequest<T = any>(url: string, options: RequestInit): Promise<T>" in code
        assert "export interface User {" in code
        assert "export interface UserCreate {" in code
        assert "getUsers(" in code
        assert "createUser(" in code

    def test_generate_from_schema_typescript_axios(
        self, generator: ClientGenerator, sample_schema: dict[str, Any]
    ) -> None:
        """Test TypeScript + axios generation"""
        config = ClientConfig(language="typescript", http_client="axios")
        code = generator.generate_from_schema(sample_schema, config)

        assert "import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';" in code
        assert "private axios: AxiosInstance;" in code
        assert "this.axios.request(axiosConfig)" in code

    def test_get_base_url_from_schema(self, generator: ClientGenerator, sample_schema: dict[str, Any]) -> None:
        """Test base URL extraction from schema"""
        generator.generate_from_schema(sample_schema, ClientConfig())
        assert generator._get_base_url() == "https://api.example.com"

    def test_get_base_url_default(self, generator: ClientGenerator) -> None:
        """Test default base URL when no servers in schema"""
        schema = {"openapi": "3.0.0", "info": {"title": "Test"}}
        generator.generate_from_schema(schema, ClientConfig())
        assert generator._get_base_url() == "http://localhost:8000"

    def test_method_name_from_operation_id(self, generator: ClientGenerator) -> None:
        """Test method name generation from operationId"""
        operation: dict[str, Any] = {"operationId": "get_user_profile"}
        name = generator._get_method_name("/users/profile", "get", operation)
        assert name == "getUserProfile"

    def test_method_name_from_path(self, generator: ClientGenerator) -> None:
        """Test method name generation from path when no operationId"""
        operation: dict[str, Any] = {}
        name = generator._get_method_name("/users/profile", "get", operation)
        assert name == "getUsersProfile"

    def test_method_name_root_path(self, generator: ClientGenerator) -> None:
        """Test method name for root path"""
        operation: dict[str, Any] = {}
        name = generator._get_method_name("/", "get", operation)
        assert name == "getApi"

    def test_method_name_with_underscores(self, generator: ClientGenerator) -> None:
        """Test method name generation with underscores in path segments"""
        operation: dict[str, Any] = {}

        # Test sys_dict/show path
        name = generator._get_method_name("/dev/sys_dict/show", "post", operation)
        assert name == "postDevSysDictShow"

        # Test sys_map/adjust path
        name = generator._get_method_name("/dev/sys_map/adjust", "post", operation)
        assert name == "postDevSysMapAdjust"

        # Test multiple underscores
        name = generator._get_method_name("/api/user_profile/update_settings", "put", operation)
        assert name == "putApiUserProfileUpdateSettings"

        # Test dots and hyphens in path segments
        name = generator._get_method_name("/.well-known/appspecific/com.chrome.devtools.json", "get", operation)
        assert name == "getWellKnownAppspecificComChromeDevtoolsJson"

        # Test mixed special characters
        name = generator._get_method_name("/api/v1.0/user-profile/settings.json", "post", operation)
        assert name == "postApiV10UserProfileSettingsJson"

    def test_to_camel_case(self, generator: ClientGenerator) -> None:
        """Test camelCase conversion"""
        assert generator._to_camel_case("snake_case") == "snakeCase"
        assert generator._to_camel_case("already_camel") == "alreadyCamel"
        assert generator._to_camel_case("single") == "single"
        assert generator._to_camel_case("") == ""

    def test_get_type_basic(self, generator: ClientGenerator) -> None:
        """Test basic type conversion"""
        assert generator._get_type({"type": "string"}) == "string"
        assert generator._get_type({"type": "integer"}) == "number"
        assert generator._get_type({"type": "boolean"}) == "boolean"
        assert generator._get_type({"type": "unknown"}) == "any"
        assert generator._get_type({}) == "any"
        assert generator._get_type(None) == "any"

    def test_get_type_array(self, generator: ClientGenerator) -> None:
        """Test array type conversion"""
        schema = {"type": "array", "items": {"type": "string"}}
        assert generator._get_type(schema) == "string[]"

    def test_get_type_object(self, generator: ClientGenerator) -> None:
        """Test object type conversion"""
        schema = {"type": "object"}
        assert generator._get_type(schema) == "Record<string, any>"

    def test_get_type_enum(self, generator: ClientGenerator) -> None:
        """Test enum type conversion"""
        schema = {"type": "string", "enum": ["active", "inactive", "pending"]}
        expected = '"active" | "inactive" | "pending"'
        assert generator._get_type(schema) == expected

    def test_get_type_nullable(self, generator: ClientGenerator) -> None:
        """Test nullable type conversion"""
        schema = {"type": "string", "nullable": True}
        assert generator._get_type(schema) == "string | null"

    def test_get_type_reference(self, generator: ClientGenerator) -> None:
        """Test reference type conversion"""
        schema = {"$ref": "#/components/schemas/User"}
        assert generator._get_type(schema) == "User"

    def test_get_parameters_path_and_query(self, generator: ClientGenerator) -> None:
        """Test parameter extraction with path and query params"""
        operation = {
            "parameters": [
                {"name": "userId", "in": "path", "required": True, "schema": {"type": "string"}},
                {"name": "includeDetails", "in": "query", "required": False, "schema": {"type": "boolean"}},
            ]
        }

        params = generator._get_parameters(operation)
        assert len(params["path_params"]) == 1
        assert len(params["query_params"]) == 1
        assert params["body_param"] is None

        path_param = params["path_params"][0]
        assert path_param["name"] == "userId"
        assert path_param["required"] is True
        assert path_param["type"] == "string"

    def test_get_parameters_with_body(self, generator: ClientGenerator) -> None:
        """Test parameter extraction with request body"""
        operation = {"requestBody": {"content": {"application/json": {"schema": {"type": "object"}}}}}

        params = generator._get_parameters(operation)
        assert params["body_param"] is True
        assert len(params["path_params"]) == 0
        assert len(params["query_params"]) == 0

    def test_generate_ts_interfaces(self, generator: ClientGenerator, sample_schema: dict[str, Any]) -> None:
        """Test TypeScript interface generation"""
        generator.generate_from_schema(sample_schema, ClientConfig(language="typescript"))
        interfaces = generator._generate_ts_interfaces()

        assert "export interface User {" in interfaces
        assert "export interface UserCreate {" in interfaces
        assert "export interface UserUpdate {" in interfaces

        # Check required vs optional fields
        assert "id: string;" in interfaces  # required
        assert "name?: string;" in interfaces  # optional

    def test_generate_ts_interfaces_empty(self, generator: ClientGenerator) -> None:
        """Test interface generation with no schemas"""
        schema: dict[str, Any] = {"openapi": "3.0.0", "components": {}}
        generator.generate_from_schema(schema, ClientConfig(language="typescript"))
        interfaces = generator._generate_ts_interfaces()
        assert interfaces == ""

    def test_response_type_extraction(self, generator: ClientGenerator) -> None:
        """Test response type extraction from operation"""
        operation = {
            "responses": {
                "200": {"content": {"application/json": {"schema": {"type": "array", "items": {"type": "string"}}}}}
            }
        }

        response_type = generator._get_response_type(operation)
        assert response_type == "string[]"

    def test_response_type_fallback(self, generator: ClientGenerator) -> None:
        """Test response type fallback when no schema"""
        operation = {"responses": {"200": {"description": "Success"}}}

        response_type = generator._get_response_type(operation)
        assert response_type == "any"

    def test_config_validation(self, generator: ClientGenerator, sample_schema: dict[str, Any]) -> None:
        """Test that invalid config raises no errors"""
        # These should not raise exceptions
        config1 = ClientConfig(language="javascript", http_client="fetch")
        code1 = generator.generate_from_schema(sample_schema, config1)
        assert isinstance(code1, str)
        assert len(code1) > 0

        config2 = ClientConfig(language="typescript", http_client="axios")
        code2 = generator.generate_from_schema(sample_schema, config2)
        assert isinstance(code2, str)
        assert len(code2) > 0

    def test_empty_schema_handling(self, generator: ClientGenerator) -> None:
        """Test handling of minimal schema"""
        minimal_schema = {"openapi": "3.0.0", "info": {"title": "Test", "version": "1.0.0"}, "paths": {}}

        config = ClientConfig(language="javascript", http_client="fetch")
        code = generator.generate_from_schema(minimal_schema, config)

        assert isinstance(code, str)
        assert "class ApiClient {" in code
        # Should still generate basic class structure even with no endpoints

    def test_complex_path_parameters(self, generator: ClientGenerator) -> None:
        """Test handling of complex path parameters"""
        operation = {
            "parameters": [
                {"name": "user_id", "in": "path", "required": True, "schema": {"type": "string"}},
                {"name": "post-id", "in": "path", "required": True, "schema": {"type": "integer"}},
            ]
        }

        params = generator._get_parameters(operation)
        assert len(params["path_params"]) == 2

        # Check parameter name conversion
        names = [p["name"] for p in params["path_params"]]
        assert "userId" in names  # snake_case to camelCase
        assert "postId" in names  # kebab-case to camelCase

    def test_generated_code_includes_header_comments(
        self, generator: ClientGenerator, sample_schema: dict[str, Any]
    ) -> None:
        """Test that generated code includes header comments with generation info"""
        code = generator.generate_from_schema(sample_schema, ClientConfig(language="javascript"))

        # Check for header comment markers
        assert "/*" in code
        assert "This file is auto-generated. DO NOT EDIT MANUALLY!" in code
        assert "Generated by: Faster Framework v" in code
        assert "Generated at:" in code
        assert "Language: javascript" in code
        assert "HTTP Client: fetch" in code
        assert "Any manual changes will be overwritten" in code

    def test_generated_code_includes_api_comments(
        self, generator: ClientGenerator, sample_schema: dict[str, Any]
    ) -> None:
        """Test that generated code includes API method comments"""
        code = generator.generate_from_schema(sample_schema, ClientConfig(language="javascript"))

        # Check for JSDoc comments
        assert "/**" in code
        assert "*/" in code

    def test_generated_code_includes_end_marker(
        self, generator: ClientGenerator, sample_schema: dict[str, Any]
    ) -> None:
        """Test that generated code includes end marker comments"""
        code = generator.generate_from_schema(sample_schema, ClientConfig(language="javascript"))

        # Check for end marker
        assert "API Definitions End" in code
