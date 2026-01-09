import logging
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlmodel import SQLModel, create_engine, Field, Session

from core.config import settings

logger = logging.getLogger(__name__)

# 1. Create database engine (uses URL from configuration)
engine = create_engine(settings.DATABASE_URL, echo=True)


# 2. Basic model with timestamp
class TimeStampedModel(SQLModel):
    """Base class for all tables that contain timestamps."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False, index=True)


# 3. Session Management
@contextmanager
def get_session_context():
    """
    Context manager for database sessions.
    Usage: with get_session_context() as session: ...
    """
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_managed_session():
    """
    FastAPI Dependency.
    """
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# 4. Helper function for creating all tables (for tests/scripts)
def create_all_tables():
    """Creates all tables in the database."""
    SQLModel.metadata.create_all(engine)


def dispose_engine():
    """Disposes the database engine and closes all connections."""
    global engine
    if engine:
        logger.info("Disposing engine...")
        engine.dispose()  # Important: Empties the connection pool
        logger.info("Engine disposed.")
