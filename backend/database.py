from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

# SQLite uses check_same_thread=False for compatibility
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    # Scanner tokens are bearer credentials. SQL bind values must never be logged,
    # including in local DEBUG mode or DB exception strings.
    echo=False,
    hide_parameters=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


@event.listens_for(engine, "begin")
def _set_backend_rls_context(conn):
    """Server-side DB access only (equivalent to Supabase service_role)."""
    url = settings.DATABASE_URL
    if url.startswith("postgresql") or url.startswith("postgres"):
        conn.execute(text("SET LOCAL krx.is_backend = 'true'"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
