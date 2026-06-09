import os
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./japan_auctions.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
pool_kwargs = {"poolclass": NullPool} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, **pool_kwargs)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=DELETE")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-32000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# _active_session_factory holds the current factory; swapped to /tmp by _switch_to_tmp()
_active_session_factory = SessionLocal


def _switch_to_tmp():
    """After startup DB copy to /tmp, rebind to local file for fast reads."""
    global engine, SessionLocal, _active_session_factory
    engine.dispose()
    tmp_url = "sqlite:////tmp/japan_auctions.db"
    engine = create_engine(tmp_url, connect_args={"check_same_thread": False}, poolclass=NullPool)

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA mmap_size=268435456")
        cursor.close()

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    _active_session_factory = SessionLocal


def get_db():
    db = _active_session_factory()
    try:
        yield db
    finally:
        db.close()
