from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base

DATABASE_URL = "sqlite:///./clinic.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


Base.metadata.create_all(bind=engine)

from app.database_constraints import create_appointment_triggers

create_appointment_triggers()

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()