# import secrets, urllib.parse
#
# password = secrets.token_urlsafe(24) + '@#!'  # Strong random pass with forced special chars
# encoded = urllib.parse.quote_plus(password)
#
# print(f'POSTGRES_PASSWORD={password}')
# print(f'POSTGRES_PASSWORD_URLENCODED={encoded}')
#
#
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# DATABASE_URL = os.environ["DATABASE_URL"]
DATABASE_URL="postgresql+psycopg://homework_app:w6Mpslt9EQhZyD5q1L9RkIlG361P@127.0.0.1:5433/homework_magic"
engine = create_engine(
    DATABASE_URL,
    pool_size=int(os.getenv("DB_POOL_SIZE", "3")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "2")),
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)
print(engine)