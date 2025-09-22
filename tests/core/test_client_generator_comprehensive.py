"""
Comprehensive unit tests for ClientGenerator.

This test suite provides extensive coverage of the ClientGenerator functionality,
including edge cases, error conditions, and integration scenarios.

Tests cover:
- Client code generation for JavaScript and TypeScript
- Support for both fetch and axios HTTP clients
- Method name generation from paths and operationIds
- Type conversion from OpenAPI schemas
- Interface generation for TypeScript
- FastAPI app integration
- Content-Type header generation (critical fix)
- Error handling and edge cases
- Performance and scalability scenarios
"""

from typing import Any
from unittest.mock import Mock, patch

import pytest

from faster.core.client_generator import ClientConfig, ClientGenerator


class TestClientConfig:
    """Comprehensive tests for ClientConfig dataclass"""

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
            language="typescript",
            http_client="axios",
            class_name="MyApiClient",
            base_url="https://api.example.com"
        )
        assert config.language == "typescript"
        assert config.http_client == "axios"
        assert config.class_name == "MyApiClient"
        assert config.base_url == "https://api.example.com"

    def test_config_immutability(self) -> None:
        """Test that config can be safely copied and modified"""
        config1 = ClientConfig(language="typescript")
        config2 = ClientConfig(language="javascript", class_name=config1.class_name)

        # Configs should be independent
        assert config1.language != config2.language
        assert config1.class_name == config2.class_name

    def test_config_validation_literal_types(self) -> None:
        """Test that config accepts only valid literal types"""
        # These should work (valid literals)
        ClientConfig(language="javascript", http_client="fetch")
        ClientConfig(language="typescript", http_client="axios")

        # MyPy should catch invalid literals at compile time,
        # but we can't test runtime validation without type checking


class TestClientGenerator:
    """Comprehensive ClientGenerator functionality tests"""

    @pytest.fixture
    def generator(self) -> ClientGenerator:
        """Create a ClientGenerator instance"""
        return ClientGenerator()

    @pytest.fixture
    def minimal_schema(self) -> dict[str, Any]:
        """Minimal valid OpenAPI schema"""
        return {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {},
        }

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
                "/dev/sys_dict/show": {
                    "post": {
                        "summary": "Show system dictionary entries",
                        "requestBody": {
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/SysDictShowRequest"}}}
                        },
                        "responses": {
                            "200": {
                                "description": "Success",
                                "content": {"application/json": {"schema": {"type": "object"}}},
                            }
                        },
                    }
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
                    "SysDictShowRequest": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string", "nullable": True},
                            "key": {"type": "integer", "nullable": True},
                            "value": {"type": "string", "nullable": True},
                            "in_used_only": {"type": "boolean", "default": False},
                        },
                    },
                }
            },
        }

    @pytest.fixture
    def complex_schema(self) -> dict[str, Any]:
        """Complex schema with edge cases"""
        return {
            "openapi": "3.0.0",
            "info": {"title": "Complex API", "version": "2.0.0"},
            "servers": [
                {"url": "https://api.example.com/v1"},
                {"url": "https://staging-api.example.com/v1"}
            ],
            "paths": {
                "/.well-known/appspecific/com.chrome.devtools.json": {
                    "get": {
                        "summary": "Chrome DevTools integration",
                        "responses": {"200": {"description": "Success"}},
                    }
                },
                "/api/v1.0/user-profile/settings.json": {
                    "post": {
                        "operationId": "update_user_profile_settings",
                        "requestBody": {"content": {"application/json": {"schema": {"type": "object"}}}},
                        "responses": {"200": {"description": "Success"}},
                    }
                },
                "/items/{item_id}/reviews/{review-id}": {
                    "delete": {
                        "parameters": [
                            {"name": "item_id", "in": "path", "required": True, "schema": {"type": "string"}},
                            {"name": "review-id", "in": "path", "required": True, "schema": {"type": "integer"}},
                        ],
                        "responses": {"204": {"description": "Deleted"}},
                    }
                },
            },
            "components": {
                "schemas": {
                    "ComplexType": {
                        "type": "object",
                        "properties": {
                            "enum_field": {"type": "string", "enum": ["active", "inactive", "pending"]},
                            "nullable_field": {"type": "string", "nullable": True},
                            "array_field": {"type": "array", "items": {"type": "string"}},
                            "nested_object": {
                                "type": "object",
                                "properties": {"nested_prop": {"type": "number"}},
                            },
                            "ref_field": {"$ref": "#/components/schemas/SimpleType"},
                        },
                        "required": ["enum_field"],
                    },
                    "SimpleType": {
                        "type": "object",
                        "properties": {"value": {"type": "string"}},
                    },
                }
            },
        }

    # Core Generation Tests
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
        # Note: Both /users and /users/{userId} generate the same method name "getUsers"
        # since path parameters are stripped in method name generation
        assert code.count("getUsers(") >= 1  # Could have multiple getUsers methods
        assert "putUsers(" in code  # PUT /users/{userId} becomes putUsers

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

    def test_generate_from_schema_javascript_axios(
        self, generator: ClientGenerator, sample_schema: dict[str, Any]
    ) -> None:
        """Test JavaScript + axios generation"""
        config = ClientConfig(language="javascript", http_client="axios")
        code = generator.generate_from_schema(sample_schema, config)

        assert "class ApiClient {" in code
        assert "this.axios = axios.create(" in code
        assert "this.axios.request(axiosConfig)" in code

    # Content-Type Header Tests (Critical Fix)
    def test_fetch_client_includes_content_type_header(
        self, generator: ClientGenerator, minimal_schema: dict[str, Any]
    ) -> None:
        """Test that fetch clients include Content-Type: application/json header"""
        config = ClientConfig(language="javascript", http_client="fetch")
        code = generator.generate_from_schema(minimal_schema, config)

        # The critical fix: fetch clients should include Content-Type header
        assert "'Content-Type': 'application/json'" in code
        assert "this.defaultOptions = {" in code
        assert "headers: { 'Content-Type': 'application/json' }," in code

    def test_typescript_fetch_client_includes_content_type_header(
        self, generator: ClientGenerator, minimal_schema: dict[str, Any]
    ) -> None:
        """Test that TypeScript fetch clients include Content-Type: application/json header"""
        config = ClientConfig(language="typescript", http_client="fetch")
        code = generator.generate_from_schema(minimal_schema, config)

        # The critical fix: TypeScript fetch clients should include Content-Type header
        assert "'Content-Type': 'application/json'" in code
        assert "this.defaultOptions = {" in code
        assert "headers: { 'Content-Type': 'application/json' }," in code

    def test_axios_client_includes_content_type_header(
        self, generator: ClientGenerator, minimal_schema: dict[str, Any]
    ) -> None:
        """Test that axios clients include Content-Type: application/json header"""
        config = ClientConfig(language="javascript", http_client="axios")
        code = generator.generate_from_schema(minimal_schema, config)

        # Axios clients should also include Content-Type header
        assert "'Content-Type': 'application/json'" in code

    # Base URL Tests
    def test_get_base_url_from_schema(self, generator: ClientGenerator, sample_schema: dict[str, Any]) -> None:
        """Test base URL extraction from schema"""
        generator.generate_from_schema(sample_schema, ClientConfig())
        assert generator._get_base_url() == "https://api.example.com"

    def test_get_base_url_default(self, generator: ClientGenerator) -> None:
        """Test default base URL when no servers in schema"""
        schema = {"openapi": "3.0.0", "info": {"title": "Test"}}
        generator.generate_from_schema(schema, ClientConfig())
        assert generator._get_base_url() == "http://localhost:8000"

    def test_get_base_url_multiple_servers(self, generator: ClientGenerator, complex_schema: dict[str, Any]) -> None:
        """Test base URL extraction with multiple servers (uses first)"""
        generator.generate_from_schema(complex_schema, ClientConfig())
        assert generator._get_base_url() == "https://api.example.com/v1"

    def test_config_base_url_override(self, generator: ClientGenerator, sample_schema: dict[str, Any]) -> None:
        """Test that config base_url overrides schema servers"""
        config = ClientConfig(base_url="https://custom.api.com")
        code = generator.generate_from_schema(sample_schema, config)

        assert "https://custom.api.com" in code
        assert "https://api.example.com" not in code

    # Method Name Generation Tests
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

    def test_method_name_with_special_characters(self, generator: ClientGenerator) -> None:
        """Test method name generation with dots, hyphens, and special characters"""
        operation: dict[str, Any] = {}

        # Test dots and hyphens in path segments
        name = generator._get_method_name("/.well-known/appspecific/com.chrome.devtools.json", "get", operation)
        assert name == "getWellKnownAppspecificComChromeDevtoolsJson"

        # Test mixed special characters
        name = generator._get_method_name("/api/v1.0/user-profile/settings.json", "post", operation)
        assert name == "postApiV10UserProfileSettingsJson"

    def test_method_name_edge_cases(self, generator: ClientGenerator) -> None:
        """Test method name generation edge cases"""
        operation: dict[str, Any] = {}

        # Empty path parts should be filtered out
        name = generator._get_method_name("/api//users", "get", operation)
        assert name == "getApiUsers"

        # Path parameters should be ignored in name generation
        name = generator._get_method_name("/users/{userId}/posts/{postId}", "get", operation)
        assert name == "getUsersPosts"

    # Parameter Handling Tests
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

    # Type Conversion Tests
    def test_get_type_basic(self, generator: ClientGenerator) -> None:
        """Test basic type conversion"""
        assert generator._get_type({"type": "string"}) == "string"
        assert generator._get_type({"type": "integer"}) == "number"
        assert generator._get_type({"type": "number"}) == "number"
        assert generator._get_type({"type": "boolean"}) == "boolean"
        assert generator._get_type({"type": "unknown"}) == "any"
        assert generator._get_type({}) == "any"
        assert generator._get_type(None) == "any"

    def test_get_type_array(self, generator: ClientGenerator) -> None:
        """Test array type conversion"""
        schema = {"type": "array", "items": {"type": "string"}}
        assert generator._get_type(schema) == "string[]"

        # Nested array
        schema = {"type": "array", "items": {"type": "array", "items": {"type": "number"}}}
        assert generator._get_type(schema) == "number[][]"

    def test_get_type_object(self, generator: ClientGenerator) -> None:
        """Test object type conversion"""
        schema = {"type": "object"}
        assert generator._get_type(schema) == "Record<string, any>"

    def test_get_type_enum(self, generator: ClientGenerator) -> None:
        """Test enum type conversion"""
        schema = {"type": "string", "enum": ["active", "inactive", "pending"]}
        expected = '"active" | "inactive" | "pending"'
        assert generator._get_type(schema) == expected

        # Non-string enum
        int_schema: dict[str, Any] = {"type": "integer", "enum": [1, 2, 3]}
        expected = "1 | 2 | 3"
        assert generator._get_type(int_schema) == expected

    def test_get_type_nullable(self, generator: ClientGenerator) -> None:
        """Test nullable type conversion"""
        schema = {"type": "string", "nullable": True}
        assert generator._get_type(schema) == "string | null"

        # Nullable with complex type
        schema = {"type": "array", "items": {"type": "string"}, "nullable": True}
        assert generator._get_type(schema) == "string[] | null"

    def test_get_type_reference(self, generator: ClientGenerator) -> None:
        """Test reference type conversion"""
        schema = {"$ref": "#/components/schemas/User"}
        assert generator._get_type(schema) == "User"

        # Deep reference path
        schema = {"$ref": "#/components/schemas/nested/DeepType"}
        assert generator._get_type(schema) == "DeepType"

    # TypeScript Interface Generation Tests
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

    def test_generate_ts_interfaces_complex_types(self, generator: ClientGenerator, complex_schema: dict[str, Any]) -> None:
        """Test interface generation with complex types"""
        generator.generate_from_schema(complex_schema, ClientConfig(language="typescript"))
        interfaces = generator._generate_ts_interfaces()

        # Check enum generation
        assert '"active" | "inactive" | "pending"' in interfaces

        # Check nullable types
        assert "| null" in interfaces

        # Check array types
        assert "string[]" in interfaces

        # Check nested objects
        assert "Record<string, any>" in interfaces

    # Response Type Tests
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

    def test_response_type_priority(self, generator: ClientGenerator) -> None:
        """Test response type selection priority (200 > 201 > 202)"""
        operation = {
            "responses": {
                "202": {"content": {"application/json": {"schema": {"type": "string"}}}},
                "200": {"content": {"application/json": {"schema": {"type": "number"}}}},
                "201": {"content": {"application/json": {"schema": {"type": "boolean"}}}},
            }
        }

        response_type = generator._get_response_type(operation)
        assert response_type == "number"  # Should pick 200 first

    # Utility Method Tests
    def test_to_camel_case(self, generator: ClientGenerator) -> None:
        """Test camelCase conversion"""
        assert generator._to_camel_case("snake_case") == "snakeCase"
        assert generator._to_camel_case("already_camel") == "alreadyCamel"
        assert generator._to_camel_case("single") == "single"
        assert generator._to_camel_case("") == ""
        assert generator._to_camel_case("multiple_under_scores") == "multipleUnderScores"

    # Configuration and Validation Tests
    def test_config_validation(self, generator: ClientGenerator, sample_schema: dict[str, Any]) -> None:
        """Test that different configs produce valid code"""
        configs = [
            ClientConfig(language="javascript", http_client="fetch"),
            ClientConfig(language="javascript", http_client="axios"),
            ClientConfig(language="typescript", http_client="fetch"),
            ClientConfig(language="typescript", http_client="axios"),
        ]

        for config in configs:
            code = generator.generate_from_schema(sample_schema, config)
            assert isinstance(code, str)
            assert len(code) > 0

            # All configs should include class definition
            assert config.class_name in code

    def test_custom_class_name(self, generator: ClientGenerator, minimal_schema: dict[str, Any]) -> None:
        """Test custom class name configuration"""
        config = ClientConfig(class_name="MyCustomClient")
        code = generator.generate_from_schema(minimal_schema, config)

        assert "class MyCustomClient {" in code
        assert "window.MyCustomClient = MyCustomClient" in code

    # Edge Cases and Error Handling Tests
    def test_empty_schema_handling(self, generator: ClientGenerator) -> None:
        """Test handling of minimal schema"""
        minimal_schema = {"openapi": "3.0.0", "info": {"title": "Test", "version": "1.0.0"}, "paths": {}}

        config = ClientConfig(language="javascript", http_client="fetch")
        code = generator.generate_from_schema(minimal_schema, config)

        assert isinstance(code, str)
        assert "class ApiClient {" in code
        # Should still generate basic class structure even with no endpoints

    def test_missing_schema_components(self, generator: ClientGenerator) -> None:
        """Test handling of schema without components"""
        schema = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {
                "/test": {
                    "get": {
                        "responses": {"200": {"description": "Success"}}
                    }
                }
            }
        }

        code = generator.generate_from_schema(schema, ClientConfig(language="typescript"))
        assert isinstance(code, str)
        assert "class ApiClient" in code

    def test_malformed_operation_handling(self, generator: ClientGenerator) -> None:
        """Test handling of malformed operations"""
        schema: dict[str, Any] = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {
                "/test": {
                    "get": {}  # Empty operation
                }
            }
        }

        # Should not raise exception
        code = generator.generate_from_schema(schema, ClientConfig())
        assert isinstance(code, str)

    # Header and Comment Generation Tests
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

    def test_method_comments_with_summary_and_description(self, generator: ClientGenerator) -> None:
        """Test method comment generation with summary and description"""
        summary = "Get user by ID"
        description = "Retrieve a specific user by their unique identifier"

        comment = generator._generate_method_comment("/users/{id}", "GET", summary, description)

        assert "/**" in comment
        assert summary in comment
        assert description in comment
        assert "*/" in comment

    # FastAPI Integration Tests (without requiring FastAPI import)
    def test_extract_all_routes_schema_structure(self, generator: ClientGenerator) -> None:
        """Test _extract_all_routes_schema produces valid structure"""
        # Mock FastAPI app structure
        mock_route = Mock()
        mock_route.path = "/test"
        mock_route.methods = ["GET", "POST"]

        mock_app = Mock()
        mock_app.routes = [mock_route]
        mock_app.openapi.return_value = {
            "info": {"title": "Test", "version": "1.0.0"},
            "components": {"schemas": {}}
        }

        # Mock the _create_operation_spec method
        with patch.object(generator, '_create_operation_spec', return_value={
            "responses": {"200": {"description": "Success"}}
        }):
            schema = generator._extract_all_routes_schema(mock_app)

        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema
        assert "components" in schema

    def test_get_operation_id_generation(self, generator: ClientGenerator) -> None:
        """Test operation ID generation for routes"""
        # Mock route without operation_id
        mock_route = Mock()
        mock_route.operation_id = None

        op_id = generator._get_operation_id(mock_route, "post", "/dev/sys_dict/show")
        assert op_id == "postDevSysDictShow"

        op_id = generator._get_operation_id(mock_route, "get", "/.well-known/appspecific/com.chrome.devtools.json")
        assert op_id == "getWellKnownAppspecificComChromeDevtoolsJson"

    def test_extract_path_parameters(self, generator: ClientGenerator) -> None:
        """Test path parameter extraction"""
        path = "/users/{userId}/posts/{postId}"
        params = generator._extract_path_parameters(path)

        assert len(params) == 2
        assert params[0]["name"] == "userId"
        assert params[1]["name"] == "postId"
        assert all(p["in"] == "path" for p in params)
        assert all(p["required"] is True for p in params)

    # Performance and Scalability Tests
    def test_large_schema_handling(self, generator: ClientGenerator) -> None:
        """Test handling of large schemas with many endpoints"""
        # Create a schema with many endpoints
        paths = {}
        for i in range(100):
            paths[f"/endpoint_{i}"] = {
                "get": {
                    "operationId": f"get_endpoint_{i}",
                    "responses": {"200": {"description": "Success"}}
                }
            }

        large_schema = {
            "openapi": "3.0.0",
            "info": {"title": "Large API", "version": "1.0.0"},
            "paths": paths
        }

        code = generator.generate_from_schema(large_schema, ClientConfig())
        assert isinstance(code, str)
        assert len(code) > 1000  # Should generate substantial code

        # Should contain methods for all endpoints
        for i in range(0, 100, 10):  # Sample check every 10th endpoint
            assert f"getEndpoint{i}" in code

    def test_deeply_nested_schema_types(self, generator: ClientGenerator) -> None:
        """Test handling of deeply nested schema types"""
        nested_schema = {
            "openapi": "3.0.0",
            "info": {"title": "Nested API", "version": "1.0.0"},
            "paths": {},
            "components": {
                "schemas": {
                    "Level1": {
                        "type": "object",
                        "properties": {
                            "level2": {"$ref": "#/components/schemas/Level2"}
                        }
                    },
                    "Level2": {
                        "type": "object",
                        "properties": {
                            "level3": {"type": "array", "items": {"$ref": "#/components/schemas/Level3"}}
                        }
                    },
                    "Level3": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "string", "nullable": True}
                        }
                    }
                }
            }
        }

        generator.generate_from_schema(nested_schema, ClientConfig(language="typescript"))
        interfaces = generator._generate_ts_interfaces()

        assert "export interface Level1" in interfaces
        assert "export interface Level2" in interfaces
        assert "export interface Level3" in interfaces
        assert "Level2" in interfaces  # Reference type
        assert "Level3[]" in interfaces  # Array of references
        assert "string | null" in interfaces  # Nullable type

    # Integration Tests
    def test_end_to_end_javascript_fetch(self, generator: ClientGenerator, sample_schema: dict[str, Any]) -> None:
        """Test complete JavaScript + fetch generation"""
        config = ClientConfig(
            language="javascript",
            http_client="fetch",
            class_name="TestClient",
            base_url="https://test.api.com"
        )

        code = generator.generate_from_schema(sample_schema, config)

        # Verify all major components
        assert "class TestClient {" in code
        assert "https://test.api.com" in code
        assert "'Content-Type': 'application/json'" in code  # Critical fix
        assert "async _makeRequest(" in code
        assert "fetch(fullUrl, requestOptions)" in code
        assert "setAuth(" in code
        assert "setHeaders(" in code
        assert "getUsers(" in code
        assert "createUser(" in code
        assert "API Definitions End" in code
        assert "window.TestClient = TestClient" in code

    def test_end_to_end_typescript_axios(self, generator: ClientGenerator, sample_schema: dict[str, Any]) -> None:
        """Test complete TypeScript + axios generation"""
        config = ClientConfig(
            language="typescript",
            http_client="axios",
            class_name="AxiosClient",
            base_url="https://axios.api.com"
        )

        code = generator.generate_from_schema(sample_schema, config)

        # Verify all major components
        assert "import axios" in code
        assert "export class AxiosClient {" in code
        assert "https://axios.api.com" in code
        assert "'Content-Type': 'application/json'" in code
        assert "private axios: AxiosInstance" in code
        assert "this.axios.request(" in code
        assert "export interface User {" in code
        assert "export interface UserCreate {" in code
        assert "async getUsers(" in code
        assert ": Promise<" in code  # Return type annotations
        assert "export default AxiosClient" in code
