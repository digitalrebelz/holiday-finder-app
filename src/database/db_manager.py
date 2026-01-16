"""Database manager for Holiday Finder."""

from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from loguru import logger

from src.config.settings import settings
from src.database.models import Base, create_tables


class DatabaseManager:
    """Manages database connections and sessions."""

    def __init__(self, database_url: str = None):
        """Initialize database manager.

        Args:
            database_url: SQLAlchemy database URL. Defaults to settings.
        """
        self.database_url = database_url or settings.database.url
        self.engine = create_engine(
            self.database_url,
            echo=False,
            connect_args={"check_same_thread": False} if "sqlite" in self.database_url else {}
        )
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        logger.info(f"Database initialized: {self.database_url}")

    def init_db(self):
        """Initialize the database by creating all tables."""
        create_tables(self.engine)
        logger.info("Database tables created")

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get a database session as a context manager.

        Yields:
            SQLAlchemy Session
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()

    def get_session_direct(self) -> Session:
        """Get a database session directly (caller must manage lifecycle).

        Returns:
            SQLAlchemy Session
        """
        return self.SessionLocal()


# Global database manager instance
db_manager = DatabaseManager()
