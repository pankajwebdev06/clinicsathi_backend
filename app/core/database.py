from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from app.core.config import settings

engine_args = {
    "pool_pre_ping": True,  # Verify connections before using
    "pool_recycle": 300,    # Recycle connections after 5 minutes
    "connect_args": {},
}

if settings.DATABASE_URL.startswith("sqlite"):
    engine_args["connect_args"]["check_same_thread"] = False
else:
    # PostgreSQL settings for Supabase/Render
    engine_args["pool_size"] = 5
    engine_args["max_overflow"] = 10
    engine_args["pool_timeout"] = 30
    # SSL mode for Supabase
    engine_args["connect_args"]["sslmode"] = "require"
    # Connection timeout
    engine_args["connect_args"]["connect_timeout"] = 10

engine = create_engine(settings.DATABASE_URL, **engine_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()
