from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
import logging
from app.config import settings

logger = logging.getLogger(__name__)

# Fallback to in-memory SQLite if DATABASE_URL is not set yet, so app doesn't crash on boot
_db_url = settings.database_url or "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(_db_url, echo=False)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    """Dependency to get the DB session."""
    if settings.database_url is None:
        logger.warning("DATABASE_URL is not set. Using in-memory SQLite. Data will be lost on restart.")
    
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    """Initialize the database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
