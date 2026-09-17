from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

from app.routers.auth import router as auth_router
from app.routers.appointments import router as appointments_router
from app.routers.doctors import router as doctors_router
from app.routers.doctors import router as doctor_router


app = FastAPI(
    title="Clinic Appointment System",
    version="1.0.0",
)


app.include_router(auth_router)
app.include_router(appointments_router)
app.include_router(doctors_router)
app.include_router(doctor_router)

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request},
    )

@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request},
    )


@app.get("/register")
def register_page(request: Request):
    return templates.TemplateResponse(
        "register.html",
        {"request": request},
    )


@app.get("/dashboard")
def dashboard_page(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request},
    )

app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static",
)

templates = Jinja2Templates(
    directory="app/templates"
)