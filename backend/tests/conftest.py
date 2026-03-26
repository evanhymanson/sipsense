"""
Shared test fixtures for the SipSense backend test suite.

Provides:
- In-memory SQLite test database (isolated per test)
- FastAPI TestClient with dependency overrides
- Auth helpers (register + get JWT headers)
- Sample whiskey data (6 diverse bottles)
"""

# Fix passlib + bcrypt 4.1+/5.x compatibility
# bcrypt 5.0 removed __about__ and rejects passwords > 72 bytes (breaking passlib's bug detection)
import bcrypt as _bcrypt
if not hasattr(_bcrypt, "__about__"):
    _bcrypt.__about__ = type("about", (), {"__version__": _bcrypt.__version__})()

_orig_hashpw = _bcrypt.hashpw
_orig_checkpw = _bcrypt.checkpw

def _safe_hashpw(password, salt):
    if isinstance(password, str):
        password = password.encode("utf-8")
    return _orig_hashpw(password[:72], salt)

def _safe_checkpw(password, hashed_password):
    if isinstance(password, str):
        password = password.encode("utf-8")
    return _orig_checkpw(password[:72], hashed_password)

_bcrypt.hashpw = _safe_hashpw
_bcrypt.checkpw = _safe_checkpw

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app import models
from app.badges import seed_badges


# ── Database fixtures ────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session(test_engine):
    connection = test_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    # Clear rate limiters between tests so we don't hit 429s
    from app.main import _rate_buckets
    _rate_buckets.clear()
    from app.rate_limit import auth_rate_limit
    auth_rate_limit._attempts.clear()

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


# ── Auth helpers ─────────────────────────────────────────────────────────────

@pytest.fixture()
def auth_headers(client):
    resp = client.post("/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "password123",
    })
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def second_auth_headers(client):
    resp = client.post("/auth/register", json={
        "username": "testuser2",
        "email": "test2@example.com",
        "password": "password456",
    })
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── Sample data ──────────────────────────────────────────────────────────────

SAMPLE_WHISKEYS = [
    {
        "name": "Buffalo Trace",
        "distillery": "Buffalo Trace Distillery",
        "category": "bourbon",
        "region": "Kentucky",
        "age": 8,
        "abv": 45.0,
        "price_usd": 28.0,
        "flavor_profile": "vanilla, caramel, sweet, oak",
        "rating_avg": 4.2,
        "rating_count": 0,
        "image_url": "/uploads/bottles_nobg/buffalo_trace.png",
    },
    {
        "name": "Laphroaig 10",
        "distillery": "Laphroaig",
        "category": "scotch",
        "region": "Islay",
        "age": 10,
        "abv": 43.0,
        "price_usd": 55.0,
        "flavor_profile": "smoky, peaty, medicinal, brine",
        "rating_avg": 4.5,
        "rating_count": 0,
        "image_url": "/uploads/bottles_nobg/laphroaig_10.png",
    },
    {
        "name": "Jameson",
        "distillery": "Irish Distillers",
        "category": "irish",
        "region": "Ireland",
        "age": None,
        "abv": 40.0,
        "price_usd": 25.0,
        "flavor_profile": "smooth, light, vanilla, fruity",
        "rating_avg": 3.8,
        "rating_count": 0,
        "image_url": "/uploads/bottles_nobg/jameson.png",
    },
    {
        "name": "Yamazaki 12",
        "distillery": "Suntory",
        "category": "japanese",
        "region": "Japan",
        "age": 12,
        "abv": 43.0,
        "price_usd": 85.0,
        "flavor_profile": "floral, fruity, honey, delicate",
        "rating_avg": 4.6,
        "rating_count": 0,
        "image_url": "/uploads/bottles_nobg/yamazaki_12.png",
    },
    {
        "name": "Rittenhouse Rye",
        "distillery": "Heaven Hill",
        "category": "rye",
        "region": "Kentucky",
        "age": None,
        "abv": 50.0,
        "price_usd": 30.0,
        "flavor_profile": "spicy, pepper, rye bread, herbal",
        "rating_avg": 4.0,
        "rating_count": 0,
        "image_url": "/uploads/bottles_nobg/rittenhouse_rye.png",
    },
    {
        "name": "Crown Royal Northern Harvest",
        "distillery": "Crown Royal",
        "category": "canadian",
        "region": "Canada",
        "age": None,
        "abv": 45.0,
        "price_usd": 35.0,
        "flavor_profile": "smooth, vanilla, caramel, gentle spice",
        "rating_avg": 3.9,
        "rating_count": 0,
        "image_url": "/uploads/bottles_nobg/crown_royal.png",
    },
]


@pytest.fixture()
def sample_whiskeys(db_session):
    # Seed badge definitions so evaluate_badges() works during rating
    seed_badges(db_session)

    whiskeys = []
    for data in SAMPLE_WHISKEYS:
        w = models.Whiskey(**data)
        db_session.add(w)
        whiskeys.append(w)
    db_session.flush()
    return whiskeys


@pytest.fixture()
def sample_user_with_ratings(client, auth_headers, sample_whiskeys):
    for w in sample_whiskeys[:3]:
        client.post(
            f"/whiskeys/{w.id}/rate",
            json={"score": 4.0, "notes": "Tasty"},
            headers=auth_headers,
        )
    return auth_headers


@pytest.fixture()
def second_user_with_ratings(client, second_auth_headers, sample_whiskeys):
    """testuser2 rates whiskeys [0,1,3] (bourbon, scotch, japanese) for taste comparison."""
    indices_scores = [(0, 4.5), (1, 3.5), (3, 4.0)]
    for idx, score in indices_scores:
        client.post(
            f"/whiskeys/{sample_whiskeys[idx].id}/rate",
            json={"score": score, "notes": f"Test note {idx}"},
            headers=second_auth_headers,
        )
    return second_auth_headers


@pytest.fixture()
def testuser_rating_id(client, auth_headers, sample_whiskeys):
    """Single rating by testuser — returns its id."""
    resp = client.post(
        f"/whiskeys/{sample_whiskeys[0].id}/rate",
        json={"score": 4.0, "notes": "Fixture rating"},
        headers=auth_headers,
    )
    return resp.json()["rating"]["id"]


@pytest.fixture()
def testuser2_rating_id(client, second_auth_headers, sample_whiskeys):
    """Single rating by testuser2 — returns its id."""
    resp = client.post(
        f"/whiskeys/{sample_whiskeys[1].id}/rate",
        json={"score": 4.5, "notes": "Fixture rating 2"},
        headers=second_auth_headers,
    )
    return resp.json()["rating"]["id"]


@pytest.fixture()
def both_users_with_ratings(sample_user_with_ratings, second_user_with_ratings):
    """Both testuser and testuser2 have ratings. Returns (headers1, headers2)."""
    return sample_user_with_ratings, second_user_with_ratings
