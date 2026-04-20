import os
import pytest
import asyncpg
import psycopg2
from testcontainers.postgres import PostgresContainer
from fastapi.testclient import TestClient

POSTGRES_IMAGE = "postgres:14"


@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer(POSTGRES_IMAGE) as pg:
        yield pg


@pytest.fixture(scope="session")
def asyncpg_dsn(pg_container):
    raw = pg_container.get_connection_url()
    return raw.replace("psycopg2", "asyncpg").replace("+asyncpg", "")


@pytest.fixture(scope="session", autouse=True)
def apply_schema(pg_container, asyncpg_dsn):
    import asyncio
    schema_path = os.path.join(os.path.dirname(__file__), "..", "db", "schema.sql")
    with open(schema_path) as f:
        sql = f.read()
    sql = "\n".join(line for line in sql.splitlines() if not line.strip().startswith("\\c"))

    async def _run():
        conn = await asyncpg.connect(asyncpg_dsn)
        await conn.execute(sql)
        await conn.close()

    asyncio.run(_run())


def _psycopg2_dsn(pg_container):
    raw = pg_container.get_connection_url()
    return raw.replace("postgresql+psycopg2://", "postgresql://")


@pytest.fixture(autouse=True)
def clean_tables(pg_container):
    yield
    dsn = _psycopg2_dsn(pg_container)
    with psycopg2.connect(dsn) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("TRUNCATE viewings, properties, users RESTART IDENTITY CASCADE")


@pytest.fixture
def auth_client(asyncpg_dsn):
    import auth_service.main as m

    original_startup = m.app.router.on_startup[:]
    original_shutdown = m.app.router.on_shutdown[:]

    m.app.router.on_startup.clear()
    m.app.router.on_shutdown.clear()

    async def _startup():
        m.pool = await asyncpg.create_pool(asyncpg_dsn, min_size=1, max_size=5)

    async def _shutdown():
        if m.pool:
            await m.pool.close()

    m.app.router.on_startup.append(_startup)
    m.app.router.on_shutdown.append(_shutdown)

    with TestClient(m.app) as client:
        yield client

    m.app.router.on_startup.clear()
    m.app.router.on_shutdown.clear()
    m.app.router.on_startup.extend(original_startup)
    m.app.router.on_shutdown.extend(original_shutdown)


@pytest.fixture
def seed_test_users(pg_container):
    dsn = _psycopg2_dsn(pg_container)
    with psycopg2.connect(dsn) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (id, login, password_hash, first_name, last_name, role)
                VALUES
                  (999, 'agent1', 'x', 'A', 'B', 'agent'),
                  (998, 'buyer1', 'x', 'C', 'D', 'buyer')
                ON CONFLICT (id) DO NOTHING
            """)


@pytest.fixture
def prop_client_with_override(asyncpg_dsn, seed_test_users):
    import property_service.main as m
    from property_service.main import get_current_user

    original_startup = m.app.router.on_startup[:]
    original_shutdown = m.app.router.on_shutdown[:]

    m.app.router.on_startup.clear()
    m.app.router.on_shutdown.clear()

    async def _startup():
        m.pool = await asyncpg.create_pool(asyncpg_dsn, min_size=1, max_size=5)

    async def _shutdown():
        if m.pool:
            await m.pool.close()

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
