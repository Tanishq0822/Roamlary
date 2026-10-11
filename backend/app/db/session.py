"""SQLAlchemy engine, session factory and the FastAPI session dependency.

Plain language:
- Engine: the pooled communication channel between the app and the
  database server. `create_engine(...)` only CONFIGURES it - it does
  NOT open a network connection. The first real connection happens
  lazily on first use, so importing this module never requires the
  database to be running.
- Session: one short-lived unit of database work (a "conversation").
- get_db(): the helper future API routes will use to receive exactly
  one session per HTTP request, guaranteeing it is closed afterwards.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# pool_pre_ping=True verifies a connection still works before using it,
# which avoids stale-connection errors after long idle periods.
engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session]:
    """FastAPI dependency: one session per request, always closed.

    The `finally` block guarantees the session returns to the pool even
    if the route raises an error - sessions are never leaked.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
