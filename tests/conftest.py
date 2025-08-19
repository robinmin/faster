# import pytest
# from httpx import AsyncClient
# from sqlmodel import create_engine
# from testcontainers.postgres import PostgresContainer
# from testcontainers.redis import RedisContainer


# @pytest.fixture(scope="session")
# async def test_db():
#     with PostgresContainer("postgres:15") as postgres:
#         yield postgres.get_connection_url()


# @pytest.fixture
# async def client(test_db):
#     # 创建测试客户端
#     async with AsyncClient(app=app, base_url="http://test") as ac:
#         yield ac
