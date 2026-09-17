from fastapi import FastAPI

from app.database import engine
from app.models import Base
from app.database_constraints import create_appointment_triggers
from app.routers.auth import router as auth_router

app = FastAPI(
    title="Clinic Appointment System",
    version="1.0.0",
)


Base.metadata.create_all(bind=engine)
from app.database_constraints import create_appointment_triggers

create_appointment_triggers()
app.include_router(auth_router)

@app.get("/")
def root():
    return {
        "message": "Clinic Appointment System API"
    }