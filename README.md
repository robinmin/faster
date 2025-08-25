# Faster Framework

A modern, fast, and production-ready Python web framework built on top of FastAPI with batteries included.

## Overview

Faster is a comprehensive web framework that provides a solid foundation for building scalable web applications. It includes pre-configured components for database management, Redis integration, authentication, logging, and more, allowing developers to focus on business logic rather than infrastructure setup.

## Key Features

- **FastAPI Core**: Built on top of FastAPI for high performance and async support
- **Database Integration**: SQLModel/SQLAlchemy with connection pooling and migration support
- **Redis Management**: Multi-provider Redis support with pub/sub capabilities
- **Authentication**: JWT-based authentication system
- **Configuration Management**: Environment-based configuration with Pydantic Settings
- **Logging**: Structured logging with multiple output formats
- **Error Handling**: Comprehensive exception handling mechanisms
- **Testing**: Ready-to-use test setup with pytest
- **Deployment Ready**: Production-ready server configuration

## Recent Improvements

### Redis Pub/Sub Functionality

Added full support for Redis publish/subscribe patterns with the following features:

1. **Publish Method**: Send messages to Redis channels
2. **Subscribe Method**: Subscribe to Redis channels and receive messages
3. **Pub/Sub Object**: Returns a Redis PubSub object for managing subscriptions
4. **Error Handling**: Proper error wrapping and logging for pub/sub operations
5. **Complete Test Coverage**: Unit tests for all pub/sub functionality

### Test Suite Enhancements

Fixed and enhanced the test suite with:

1. **Redis Test Fixes**: Resolved issues with Redis client behavior for `nx`/`xx` conditions
2. **Error Recovery Testing**: Fixed RedisSafeContext to properly handle default values
3. **Comprehensive Pub/Sub Tests**: Added 4 new test cases for publish/subscribe functionality
4. **Integration Testing**: Verified all components work together correctly

## Project Structure

```
faster/
├── faster/
│   ├── core/
│   │   ├── auth/           # Authentication system
│   │   ├── bootstrap.py    # Application initialization
│   │   ├── config.py       # Configuration management
│   │   ├── database.py     # Database integration
│   │   ├── redis.py        # Redis client with pub/sub
│   │   ├── logging.py      # Structured logging
│   │   └── ...             # Other core components
│   └── __init__.py
├── tests/
│   └── core/               # Unit tests for core components
├── main.py                 # Application entry point
├── pyproject.toml          # Project dependencies and configuration
├── requirements.txt        # Dependency list
└── alembic.ini            # Database migration configuration
```

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Redis server (for Redis functionality)
- PostgreSQL or SQLite (for database functionality)

### Installation

1. Clone the repository:

   ```bash
   git clone <repository-url>
   cd faster
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

### Running the Application

```bash
# Development mode
chmod u+x ./main.py
./main.py

# Or with make tool
make run

# Or production mode with uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Configuration

The application is configured through environment variables. Key configuration options include:

- **Database**: `DATABASE_URL`
- **Redis**: `REDIS_URL`, `REDIS_PROVIDER`
- **Security**: `JWT_SECRET_KEY`, `AUTH_ENABLED`
- **Server**: `HOST`, `PORT`, `WORKERS`

See `.env.example` for a complete list of configuration options.

## Core Components

### Redis Integration

The Redis manager provides:

1. **Multi-provider Support**: Local Redis, Upstash, and Fake Redis for testing
2. **Pub/Sub Functionality**: Publish messages and subscribe to channels
3. **Error Recovery**: Decorators and context managers for graceful error handling
4. **Health Checks**: Connection status monitoring

Example usage:

```python
from faster.core.redis import get_redis

@app.get("/publish")
async def publish_message(redis: RedisClient = Depends(get_redis)):
    await redis.publish("channel", "Hello, World!")
    return {"message": "Published!"}
```

### Authentication

JWT-based authentication system with:

1. **Token Generation**: Secure token creation and validation
2. **Middleware**: Automatic token verification
3. **Role-based Access**: Flexible permission system

### Database

SQLModel/SQLAlchemy integration with:

1. **Connection Pooling**: Efficient database connection management
2. **Migration Support**: Alembic integration for schema changes
3. **Async Operations**: Full async support for database operations

## Linting and Formatting

Run the test suite with pytest:

```bash
# Automatically fix linting errors with ruff
make autofix

# Lint the code with ruff & mypy
make lint
```

## Testing

Run the test suite with pytest:

```bash
# Run all tests
make test
```

## Next Steps

### Short-term Goals

1. **Enhanced Documentation**: Create detailed API documentation
2. **Example Applications**: Build sample applications showcasing framework features
3. **Performance Monitoring**: Integrate Prometheus for metrics collection
4. **Caching Layer**: Implement Redis-based caching for improved performance

### Medium-term Goals

1. **Event Bus**: Expand event-driven architecture capabilities
2. **Task Queue**: Enhance Celery integration for background tasks
3. **Rate Limiting**: Add request rate limiting middleware
4. **API Documentation**: Auto-generated OpenAPI documentation

### Long-term Goals

1. **Plugin System**: Create an extensible plugin architecture
2. **Microservices Support**: Add service discovery and communication patterns
3. **Cloud Deployment**: Kubernetes deployment configurations
4. **Admin Interface**: Built-in administrative dashboard

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- FastAPI for the excellent web framework foundation
- Redis for the in-memory data structure store
- SQLAlchemy for database abstraction
- All other open-source projects that make this framework possible
