import os

# Variáveis precisam existir antes de importar a aplicação.
os.environ["API_KEYS"] = "test-key"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["RATE_LIMIT_PER_MINUTE"] = "1000"
os.environ["GEMINI_API_KEY"] = ""
os.environ["STORE_INPUT_TEXT"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.rate_limit import get_limiter  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.routers.deps import get_ai_provider  # noqa: E402
from tests.helpers import SAMPLE_TEXT, FakeAI  # noqa: E402

@pytest.fixture
def ai() -> FakeAI:
    return FakeAI()


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def client(ai, session_factory):
    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_ai_provider] = lambda: ai
    get_limiter.cache_clear()
    with TestClient(app, headers={"X-API-Key": "test-key"}) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def body():
    return {"texto_input": SAMPLE_TEXT, "origem": "texto_colado"}
