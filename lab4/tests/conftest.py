import pytest
from testcontainers.mongodb import MongoDbContainer
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi.testclient import TestClient

MONGO_IMAGE = "mongo:7"


@pytest.fixture(scope="session")
def mongo_container():
    with MongoDbContainer(MONGO_IMAGE) as mongo:
        yield mongo


@pytest.fixture(scope="session")
def mongo_url(mongo_container):
    return mongo_container.get_connection_url()


@pytest.fixture(autouse=True)
def clean_collections(mongo_url):
    yield
    from pymongo import MongoClient
    c = MongoClient(mongo_url)
    c["real_estate"].users.drop()
    c["real_estate"].properties.drop()
    c.close()


@pytest.fixture
def auth_client(mongo_url):
    import auth_service.main as m

    original_startup = m.app.router.on_startup[:]
    original_shutdown = m.app.router.on_shutdown[:]
    m.app.router.on_startup.clear()
    m.app.router.on_shutdown.clear()

    async def _startup():
        m.client = AsyncIOMotorClient(mongo_url)
        m.db = m.client["real_estate"]
        await m.db.users.create_index("login", unique=True)

    async def _shutdown():
        if m.client:
            m.client.close()

    m.app.router.on_startup.append(_startup)
    m.app.router.on_shutdown.append(_shutdown)

    with TestClient(m.app) as client:
        yield client

    m.app.router.on_startup.clear()
    m.app.router.on_shutdown.clear()
    m.app.router.on_startup.extend(original_startup)
    m.app.router.on_shutdown.extend(original_shutdown)


@pytest.fixture
def prop_client_with_override(mongo_url):
    import property_service.main as m
    from property_service.main import get_current_user

    original_startup = m.app.router.on_startup[:]
    original_shutdown = m.app.router.on_shutdown[:]
    m.app.router.on_startup.clear()
    m.app.router.on_shutdown.clear()

    async def _startup():
        m.client = AsyncIOMotorClient(mongo_url)
        m.db = m.client["real_estate"]
        await m.db.properties.create_index("owner_id")
        await m.db.properties.create_index("city")

    async def _shutdown():
        if m.client:
            m.client.close()

    m.app.router.on_startup.append(_startup)
    m.app.router.on_shutdown.append(_shutdown)
    m.app.dependency_overrides.clear()

    with TestClient(m.app) as client:
        yield client

    m.app.dependency_overrides.clear()
    m.app.router.on_startup.clear()
    m.app.router.on_shutdown.clear()
    m.app.router.on_startup.extend(original_startup)
    m.app.router.on_shutdown.extend(original_shutdown)
