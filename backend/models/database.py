import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Neon (serverless Postgres) closes idle connections, which broke the
# background analysis task: it would compute results but fail to save them
# with "SSL connection has been closed unexpectedly".
#   - pool_pre_ping: test a connection is alive before using it, and
#     transparently reconnect if Neon dropped it
#   - pool_recycle: proactively replace connections older than 5 minutes
#     so they never get a chance to go stale
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
