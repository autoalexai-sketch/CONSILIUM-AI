"""Regression: SQLAlchemy 2.1 defaults bare postgresql:// to psycopg (v3),
which is not installed. The app must always use psycopg2 explicitly."""
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from app.database import normalize_db_url


def test_bare_postgresql_url_uses_psycopg2():
    url = normalize_db_url("postgresql://u:p@db.example.com:5432/app")
    assert make_url(url).get_dialect().driver == "psycopg2"
    # Engine creation imports the DBAPI; fails if the driver is missing.
    create_engine(url)


def test_heroku_style_postgres_scheme_is_normalized():
    assert normalize_db_url("postgres://u:p@h/db") == "postgresql+psycopg2://u:p@h/db"


def test_explicit_driver_and_sqlite_untouched():
    assert normalize_db_url("postgresql+psycopg2://u:p@h/db") == "postgresql+psycopg2://u:p@h/db"
    assert normalize_db_url("sqlite:///./consilium.db") == "sqlite:///./consilium.db"
