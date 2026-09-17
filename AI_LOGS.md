Exactly. users, doctors, and appointments are enough for this assessment. Don't add unnecessary tables like schedules, clinics, time slots, payments, etc.

Let's make the database model solid first, especially around the no-double-booking invariant.

1. Relationships
users
  │
  ├───────────────┐
  │               │
  │               ▼
  │            doctors
  │               │
  │               │
  ▼               ▼
patients      appointments
                 │
                 └── patient → users

More precisely:

User
 ├── can be a PATIENT
 │      └── has many appointments
 │
 └── can be a DOCTOR
        └── has one Doctor profile
              └── has many appointments

I would keep the doctor account in users and doctor-specific information in doctors.

2. models.py

Put this in:

app/models.py
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    CheckConstraint,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(100), nullable=False)

    email = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    password_hash = Column(String(255), nullable=False)

    role = Column(
        String(20),
        nullable=False,
        default="patient",
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    # A doctor has one doctor profile
    doctor_profile = relationship(
        "Doctor",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # Patient's appointments
    appointments = relationship(
        "Appointment",
        back_populates="patient",
        foreign_keys="Appointment.patient_id",
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('patient', 'doctor')",
            name="check_user_role",
        ),
    )


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    specialization = Column(
        String(100),
        nullable=False,
    )

    experience = Column(
        Integer,
        nullable=False,
        default=0,
    )

    consultation_fee = Column(
        Float,
        nullable=False,
        default=0,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    user = relationship(
        "User",
        back_populates="doctor_profile",
    )

    appointments = relationship(
        "Appointment",
        back_populates="doctor",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "experience >= 0",
            name="check_experience_non_negative",
        ),
        CheckConstraint(
            "consultation_fee >= 0",
            name="check_fee_non_negative",
        ),
    )


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)

    doctor_id = Column(
        Integer,
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
    )

    patient_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    start_time = Column(
        DateTime,
        nullable=False,
    )

    end_time = Column(
        DateTime,
        nullable=False,
    )

    status = Column(
        String(30),
        nullable=False,
        default="booked",
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    cancelled_at = Column(
        DateTime,
        nullable=True,
    )

    doctor = relationship(
        "Doctor",
        back_populates="appointments",
    )

    patient = relationship(
        "User",
        back_populates="appointments",
        foreign_keys=[patient_id],
    )

    __table_args__ = (
        CheckConstraint(
            "end_time > start_time",
            name="check_valid_appointment_time",
        ),
        CheckConstraint(
            "status IN "
            "('booked', 'cancelled_early', "
            "'cancelled_late', 'completed')",
            name="check_appointment_status",
        ),

        # Useful for appointment queries
        Index(
            "idx_doctor_appointment_time",
            "doctor_id",
            "start_time",
            "end_time",
        ),
    )
3. Why these constraints matter

There are several important ones here.

User email
unique=True

means:

sumit@gmail.com
sumit@gmail.com

cannot create two accounts.

The database enforces it rather than relying only on Python.

User role
CheckConstraint(
    "role IN ('patient', 'doctor')"
)

prevents something like:

role = "admin123"

from accidentally entering the database.

For our MVP we only need two roles.

One doctor profile per user

This is important:

user_id = Column(
    Integer,
    ForeignKey("users.id"),
    unique=True
)

Because user_id is unique:

User 5 → Doctor 1

is possible, but:

User 5 → Doctor 1
User 5 → Doctor 2

is impossible.

Appointment time
CheckConstraint(
    "end_time > start_time"
)

prevents nonsense like:

10:30 → 10:00

or:

10:00 → 10:00
4. Appointment status

We'll deliberately not delete cancelled appointments.

For example:

id    doctor    patient    time       status
1     5         12         10:00      booked

Patient cancels early:

id    doctor    patient    time       status
1     5         12         10:00      cancelled_early

Patient cancels late:

id    doctor    patient    time       status
1     5         12         10:00      cancelled_late

This gives us an appointment history.

And crucially, cancelled appointments won't block a future booking.

5. The BIG constraint: overlapping appointments

Here's the interesting part.

A normal SQL constraint like:

unique=True

cannot solve our problem.

Imagine:

Appointment A:
10:00 → 10:30

Appointment B:
10:15 → 10:45

Neither (doctor_id, start_time) nor (doctor_id, end_time) is identical.

So a normal unique constraint doesn't detect the overlap.

We need the condition:

existing.start < new.end
AND
existing.end > new.start

while also requiring:

existing.doctor_id == new.doctor_id
existing.status == 'booked'

So conceptually:

SELECT 1
FROM appointments
WHERE doctor_id = :doctor_id
  AND status = 'booked'
  AND start_time < :new_end
  AND end_time > :new_start;

If this returns a row:

❌ Conflict

Otherwise:

✅ Booking allowed
6. Why we're NOT putting this directly in the model

You might notice that our Appointment model doesn't have something like:

UniqueConstraint(...)

for overlapping appointments.

That's intentional.

SQLAlchemy's model-level constraints aren't sufficient to express arbitrary interval overlap in SQLite.

So we'll use two layers:

                BOOK APPOINTMENT
                       │
                       ▼
             Application check
                       │
              overlap exists?
                /           \
              YES            NO
               │              │
               ▼              ▼
          409 Conflict      INSERT
                              │
                              ▼
                       Database trigger
                              │
                       final protection

The application check gives the user a clean API response.

The database trigger protects the actual invariant.

That's the part I'd specifically mention in REASONING.md.

7. Database configuration

Now let's create:

app/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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

And add the database dependency:

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
8. Initialize the database

For now, modify app/main.py:

from fastapi import FastAPI

from app.database import engine
from app.models import Base

app = FastAPI(
    title="Clinic Appointment System",
    version="1.0.0",
)


Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return {
        "message": "Clinic Appointment System API"
    }

Run:

uvicorn app.main:app --reload

You should see a new:

clinic.db

in the project root.

Then open:

http://127.0.0.1:8000/docs

You should see the FastAPI Swagger page.

9. One thing we haven't implemented yet

The database overlap trigger is the one piece I want to add next rather than pretending models.py alone solves double booking.

After the basic DB creation works, we'll add the SQLite trigger roughly like this:

CREATE TRIGGER prevent_doctor_overlap
BEFORE INSERT ON appointments
WHEN NEW.status = 'booked'
BEGIN
    SELECT RAISE(ABORT, 'Doctor already has an overlapping appointment')
    WHERE EXISTS (
        SELECT 1
        FROM appointments
        WHERE doctor_id = NEW.doctor_id
          AND status = 'booked'
          AND start_time < NEW.end_time
          AND end_time > NEW.start_time
    );
END;

We'll also need the corresponding UPDATE protection, because an appointment could theoretically be changed later.

That's why I don't want you to move on to authentication yet.

✅ Major Step 1 — Database design

Completed:

users model ✅
doctors model ✅
appointments model ✅
relationships ✅
foreign keys ✅
unique email ✅
role constraint ✅
valid time constraint ✅
appointment status constraint ✅
doctor profile uniqueness ✅
appointment indexes ✅

Still remaining in Step 1:

SQLite overlap trigger
create DB
verify tables
test the critical booking invariant

Do this now: add the three files/code above, run the server, and confirm that clinic.db is created and /docs opens.

Once that's working, we'll add the INSERT + UPDATE overlap triggers and a tiny database test before touching the API.

our server is not connecting, like i am thinking it is getting wrong url.
don't make it confused we want to make application.,
the tests are failed , how to fix these tests and what things are breaking here.
Now i had done this what next we should proceed we have limited time we also had to implement these features also, so be precise and give fast execution.

Let's go straight to the frontend, but first we need one missing backend piece: doctor search. The UI needs an endpoint to search doctors, so we'll add that, then build the frontend around the APIs we already have.

Major Step 4 — Doctor Search API + Frontend
4.1 Add doctor search API

Open:

app/routers/doctors.py

Put:

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Doctor
from app.schemas import DoctorResponse


router = APIRouter(
    prefix="/api/doctors",
    tags=["Doctors"],
)


@router.get("", response_model=list[DoctorResponse])
def get_doctors(
    search: str = "",
    page: int = 1,
    limit: int = 10,
    sort: str = "experience",
    order: str = "desc",
    db: Session = Depends(get_db),
):
    if page < 1:
        raise HTTPException(
            status_code=400,
            detail="Page must be >= 1",
        )

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100",
        )

    query = db.query(Doctor)

    if search:
        query = query.filter(
            Doctor.specialization.ilike(f"%{search}%")
        )

    sort_fields = {
        "experience": Doctor.experience,
        "fee": Doctor.consultation_fee,
        "id": Doctor.id,
    }

    sort_column = sort_fields.get(sort)

    if not sort_column:
        raise HTTPException(
            status_code=400,
            detail="Invalid sort field",
        )

    if order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    offset = (page - 1) * limit

    return (
        query
        .offset(offset)
        .limit(limit)
        .all()
    )

Then in main.py:

from app.routers.doctors import router as doctor_router

app.include_router(doctor_router)
4.2 Quick backend verification

Open:

/docs

Test:

GET /api/doctors

Then:

GET /api/doctors?search=cardio

Then:

GET /api/doctors?page=1&limit=5&sort=experience&order=desc

You should get doctor records.

Backend checkpoint

At this point:

Authentication       ✅
Doctor search        ✅
Appointment booking  ✅
Appointment listing  ✅
Cancellation         ✅
Rescheduling         ✅
/clock               ✅
/outbox              ✅
Conflict protection  ✅

Now frontend.

4.3 Use one dashboard page

Don't create a complicated frontend architecture.

We'll use:

app/
├── templates/
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   └── dashboard.html
│
└── static/
    ├── style.css
    └── app.js

The frontend communicates directly with our REST APIs.

4.4 Configure FastAPI static/templates

In main.py add:

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

Then:

app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static",
)

templates = Jinja2Templates(
    directory="app/templates"
)

Replace your root endpoint with:

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request},
    )

Add:

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
4.5 Landing page

Create:

app/templates/index.html
<!DOCTYPE html>
<html>
<head>
    <title>Clinic Appointment System</title>
    <link rel="stylesheet" href="/static/style.css">
</head>

<body>

<nav>
    <h2>ClinicCare</h2>

    <div>
        <a href="/login">Login</a>
        <a class="nav-button" href="/register">Get Started</a>
    </div>
</nav>

<section class="hero">
    <div>
        <p class="eyebrow">SMART CLINIC APPOINTMENTS</p>

        <h1>
            Book appointments
            <span>without the scheduling chaos.</span>
        </h1>

        <p>
            A simple clinic appointment system that keeps
            doctor schedules conflict-free and makes
            appointment management easy.
        </p>

        <a class="primary-button" href="/register">
            Book an Appointment
        </a>
    </div>
</section>

<section class="section">

    <h2>Product</h2>

    <p>
        ClinicCare helps patients discover doctors and
        book appointments while helping clinics maintain
        conflict-free schedules.
    </p>

    <div class="cards">

        <div class="card">
            <h3>Doctor Search</h3>
            <p>Find doctors by specialization and experience.</p>
        </div>

        <div class="card">
            <h3>Conflict-Free Booking</h3>
            <p>Doctors can never have overlapping booked appointments.</p>
        </div>

        <div class="card">
            <h3>Smart Cancellations</h3>
            <p>Early and late cancellations are tracked separately.</p>
        </div>

    </div>
</section>

<section class="section">

    <h2>Target Users</h2>

    <div class="cards">
        <div class="card">
            <h3>Patients</h3>
            <p>Search and manage appointments easily.</p>
        </div>

        <div class="card">
            <h3>Doctors</h3>
            <p>View appointments without scheduling conflicts.</p>
        </div>

        <div class="card">
            <h3>Clinics</h3>
            <p>Maintain a simple centralized appointment system.</p>
        </div>
    </div>

</section>

<section class="section">

    <h2>Benefits</h2>

    <ul class="benefits">
        <li>Prevents double booking</li>
        <li>Simple appointment management</li>
        <li>Conflict-free rescheduling</li>
        <li>Tracks cancellation types</li>
    </ul>

</section>

<section class="section">

    <h2>Future Features</h2>

    <div class="cards">

        <div class="card">
            <h3>SMS & Email Reminders</h3>
            <p>Automatically remind patients about upcoming visits.</p>
        </div>

        <div class="card">
            <h3>Online Payments</h3>
            <p>Allow patients to pay consultation fees online.</p>
        </div>

        <div class="card">
            <h3>Video Consultation</h3>
            <p>Enable remote doctor consultations.</p>
        </div>

    </div>

</section>

<footer>
    ClinicCare © 2026
</footer>

</body>
</html>
4.6 Register page

Create:

app/templates/register.html
<!DOCTYPE html>
<html>
<head>
    <title>Register - ClinicCare</title>
    <link rel="stylesheet" href="/static/style.css">
</head>

<body>

<div class="auth-container">

    <div class="auth-card">

        <h1>Create Account</h1>

        <form id="registerForm">

            <input
                id="name"
                placeholder="Full name"
                required
            >

            <input
                id="email"
                type="email"
                placeholder="Email"
                required
            >

            <input
                id="password"
                type="password"
                placeholder="Password"
                required
            >

            <select id="role">
                <option value="patient">Patient</option>
                <option value="doctor">Doctor</option>
            </select>

            <div id="doctorFields" style="display:none">

                <input
                    id="specialization"
                    placeholder="Specialization"
                >

                <input
                    id="experience"
                    type="number"
                    placeholder="Experience (years)"
                >

                <input
                    id="fee"
                    type="number"
                    placeholder="Consultation fee"
                >

            </div>

            <button class="primary-button">
                Register
            </button>

        </form>

        <p id="message"></p>

        <p>
            Already registered?
            <a href="/login">Login</a>
        </p>

    </div>

</div>

<script src="/static/app.js"></script>

</body>
</html>
4.7 Login page

Create:

app/templates/login.html
<!DOCTYPE html>
<html>
<head>
    <title>Login - ClinicCare</title>
    <link rel="stylesheet" href="/static/style.css">
</head>

<body>

<div class="auth-container">

    <div class="auth-card">

        <h1>Welcome Back</h1>

        <form id="loginForm">

            <input
                id="email"
                type="email"
                placeholder="Email"
                required
            >

            <input
                id="password"
                type="password"
                placeholder="Password"
                required
            >

            <button class="primary-button">
                Login
            </button>

        </form>

        <p id="message"></p>

        <p>
            Don't have an account?
            <a href="/register">Register</a>
        </p>

    </div>

</div>

<script src="/static/app.js"></script>

</body>
</html>
4.8 Dashboard

Create:

app/templates/dashboard.html
<!DOCTYPE html>
<html>
<head>
    <title>Dashboard - ClinicCare</title>
    <link rel="stylesheet" href="/static/style.css">
</head>

<body>

<nav>
    <h2>ClinicCare</h2>

    <button onclick="logout()">Logout</button>
</nav>

<main class="dashboard">

    <h1 id="welcome">Dashboard</h1>

    <section>

        <h2>Find a Doctor</h2>

        <div class="search-bar">

            <input
                id="doctorSearch"
                placeholder="Search specialization..."
            >

            <select id="sortDoctors">
                <option value="experience">Experience</option>
                <option value="fee">Fee</option>
            </select>

            <button onclick="loadDoctors()">
                Search
            </button>

        </div>

        <div id="doctors" class="cards"></div>

    </section>

    <section>

        <h2>My Appointments</h2>

        <div id="appointments"></div>

    </section>

</main>

<script src="/static/app.js"></script>

</body>
</html>
4.9 JavaScript

Create:

app/static/app.js
const API = "/api";


function getToken() {
    return localStorage.getItem("token");
}


function authHeaders() {
    return {
        "Authorization": `Bearer ${getToken()}`
    };
}


/* ---------------- REGISTER ---------------- */

const registerForm = document.getElementById("registerForm");

if (registerForm) {

    const role = document.getElementById("role");

    role.addEventListener("change", () => {

        document.getElementById("doctorFields").style.display =
            role.value === "doctor" ? "block" : "none";

    });

    registerForm.addEventListener("submit", async (event) => {

        event.preventDefault();

        const selectedRole = role.value;

        const body = {
            name: document.getElementById("name").value,
            email: document.getElementById("email").value,
            password: document.getElementById("password").value,
            role: selectedRole
        };

        if (selectedRole === "doctor") {

            body.specialization =
                document.getElementById("specialization").value;

            body.experience =
                Number(document.getElementById("experience").value);

            body.consultation_fee =
                Number(document.getElementById("fee").value);
        }

        const response = await fetch(
            `${API}/auth/register`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(body)
            }
        );

        const data = await response.json();

        const message = document.getElementById("message");

        if (!response.ok) {
            message.textContent = data.detail || "Registration failed";
            return;
        }

        message.textContent = "Registration successful!";

        setTimeout(() => {
            window.location.href = "/login";
        }, 700);

    });
}


/* ---------------- LOGIN ---------------- */

const loginForm = document.getElementById("loginForm");

if (loginForm) {

    loginForm.addEventListener("submit", async (event) => {

        event.preventDefault();

        const response = await fetch(
            `${API}/auth/login`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    email: document.getElementById("email").value,
                    password: document.getElementById("password").value
                })
            }
        );

        const data = await response.json();

        if (!response.ok) {
            document.getElementById("message").textContent =
                data.detail || "Login failed";
            return;
        }

        localStorage.setItem(
            "token",
            data.access_token
        );

        window.location.href = "/dashboard";
    });
}


/* ---------------- DASHBOARD ---------------- */

if (window.location.pathname === "/dashboard") {

    if (!getToken()) {
        window.location.href = "/login";
    } else {
        loadUser();
        loadDoctors();
        loadAppointments();
    }
}


async function loadUser() {

    const response = await fetch(
        `${API}/auth/me`,
        {
            headers: authHeaders()
        }
    );

    if (!response.ok) {
        logout();
        return;
    }

    const user = await response.json();

    document.getElementById("welcome").textContent =
        `Welcome, ${user.name}`;
}


/* ---------------- DOCTORS ---------------- */

async function loadDoctors() {

    const search =
        document.getElementById("doctorSearch")?.value || "";

    const sort =
        document.getElementById("sortDoctors")?.value ||
        "experience";

    const response = await fetch(
        `${API}/doctors?search=${encodeURIComponent(search)}&sort=${sort}&order=desc`
    );

    const doctors = await response.json();

    const container =
        document.getElementById("doctors");

    if (!container) return;

    container.innerHTML = "";

    doctors.forEach(doctor => {

        const card = document.createElement("div");

        card.className = "card";

        card.innerHTML = `
            <h3>Dr. ${doctor.user_id}</h3>

            <p>
                <strong>${doctor.specialization}</strong>
            </p>

            <p>
                Experience: ${doctor.experience} years
            </p>

            <p>
                Fee: ₹${doctor.consultation_fee}
            </p>

            <button
                class="primary-button"
                onclick="bookAppointment(${doctor.id})"
            >
                Book Appointment
            </button>
        `;

        container.appendChild(card);

    });
}


/* ---------------- BOOK ---------------- */

async function bookAppointment(doctorId) {

    const startTime = prompt(
        "Enter appointment time (YYYY-MM-DDTHH:MM)"
    );

    if (!startTime) return;

    const response = await fetch(
        `${API}/appointments?doctor_id=${doctorId}&start_time=${encodeURIComponent(startTime)}`,
        {
            method: "POST",
            headers: authHeaders()
        }
    );

    const data = await response.json();

    if (!response.ok) {
        alert(data.detail || "Booking failed");
        return;
    }

    alert("Appointment booked successfully!");

    loadAppointments();
}


/* ---------------- APPOINTMENTS ---------------- */

async function loadAppointments() {

    const response = await fetch(
        `${API}/appointments?page=1&limit=20&sort=start_time&order=asc`,
        {
            headers: authHeaders()
        }
    );

    if (!response.ok) return;

    const appointments = await response.json();

    const container =
        document.getElementById("appointments");

    if (!container) return;

    container.innerHTML = "";

    if (appointments.length === 0) {

        container.innerHTML =
            "<p>No appointments found.</p>";

        return;
    }

    appointments.forEach(appointment => {

        const card = document.createElement("div");

        card.className = "appointment";

        card.innerHTML = `
            <div>
                <strong>Doctor #${appointment.doctor_id}</strong>
                <p>
                    ${new Date(
                        appointment.start_time
                    ).toLocaleString()}
                </p>

                <span>
                    ${appointment.status}
                </span>
            </div>

            ${
                appointment.status === "booked"
                ? `
                    <button
                        onclick="cancelAppointment(${appointment.id})"
                    >
                        Cancel
                    </button>

                    <button
                        onclick="rescheduleAppointment(${appointment.id})"
                    >
                        Reschedule
                    </button>
                `
                : ""
            }
        `;

        container.appendChild(card);

    });
}


/* ---------------- CANCEL ---------------- */

async function cancelAppointment(id) {

    if (!confirm("Cancel this appointment?")) return;

    const response = await fetch(
        `${API}/appointments/${id}/cancel`,
        {
            method: "PATCH",
            headers: authHeaders()
        }
    );

    const data = await response.json();

    if (!response.ok) {
        alert(data.detail || "Cancellation failed");
        return;
    }

    alert(`Appointment ${data.status}`);

    loadAppointments();
}


/* ---------------- RESCHEDULE ---------------- */

async function rescheduleAppointment(id) {

    const newTime = prompt(
        "New time (YYYY-MM-DDTHH:MM)"
    );

    if (!newTime) return;

    const response = await fetch(
        `${API}/appointments/${id}/reschedule?new_start_time=${encodeURIComponent(newTime)}`,
        {
            method: "PATCH",
            headers: authHeaders()
        }
    );

    const data = await response.json();

    if (!response.ok) {
        alert(data.detail || "Rescheduling failed");
        return;
    }

    alert("Appointment rescheduled!");

    loadAppointments();
}


/* ---------------- LOGOUT ---------------- */

function logout() {

    localStorage.removeItem("token");

    window.location.href = "/login";
}
One limitation

Our DoctorResponse currently doesn't contain the doctor's name, so the UI displays:

Dr. 3

instead of:

Dr. Sharma

Don't stop for that right now. It is cosmetic. We can fix it in a couple of minutes after the main UI works.

4.10 CSS

Create:

app/static/style.css
* {
    box-sizing: border-box;
}

body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #f6f7fb;
    color: #202124;
}

nav {
    height: 70px;
    padding: 0 8%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: white;
    border-bottom: 1px solid #eee;
}

nav h2 {
    margin: 0;
}

nav a {
    margin-left: 20px;
    text-decoration: none;
    color: #333;
}

.hero {
    padding: 100px 10%;
    background: white;
}

.hero > div {
    max-width: 700px;
}

.eyebrow {
    font-size: 13px;
    font-weight: bold;
    letter-spacing: 2px;
}

.hero h1 {
    font-size: 50px;
    line-height: 1.1;
    margin: 20px 0;
}

.hero h1 span {
    display: block;
}

.hero p {
    font-size: 18px;
    line-height: 1.6;
}

.primary-button,
.nav-button {
    display: inline-block;
    padding: 12px 20px;
    border: none;
    border-radius: 8px;
    background: #222;
    color: white;
    text-decoration: none;
    cursor: pointer;
}

.section {
    padding: 60px 10%;
}

.cards {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
    margin-top: 25px;
}

.card {
    background: white;
    padding: 25px;
    border-radius: 12px;
    border: 1px solid #e5e5e5;
}

.benefits {
    line-height: 2;
    font-size: 18px;
}

footer {
    padding: 30px;
    text-align: center;
    background: white;
}

.auth-container {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
}

.auth-card {
    width: 400px;
    background: white;
    padding: 35px;
    border-radius: 15px;
    border: 1px solid #ddd;
}

.auth-card input,
.auth-card select,
.search-bar input,
.search-bar select {
    width: 100%;
    padding: 12px;
    margin: 8px 0;
    border: 1px solid #ccc;
    border-radius: 7px;
}

.auth-card button {
    width: 100%;
    margin-top: 10px;
}

.dashboard {
    padding: 40px 8%;
}

.search-bar {
    display: flex;
    gap: 10px;
    margin-bottom: 25px;
}

.search-bar input {
    flex: 1;
}

.search-bar select {
    width: 180px;
}

.appointment {
    background: white;
    padding: 20px;
    margin: 12px 0;
    border-radius: 10px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.appointment button {
    margin-left: 8px;
    padding: 8px 12px;
    cursor: pointer;
}

@media (max-width: 800px) {

    .cards {
        grid-template-columns: 1fr;
    }

    .hero h1 {
        font-size: 38px;
    }

    .search-bar {
        flex-direction: column;
    }

}
🚨 Verify now

Start:

uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

Open:

/

You should now have the landing page.

Then test:

/register

→ create patient

/login

→ login

/dashboard

→ doctor search + appointment management.

Critical UI test

Do this:

Patient login
     ↓
Search Cardiology
     ↓
Book Doctor A at 10:00
     ↓
Try Doctor A at 10:00 again
     ↓
409 Conflict

Then:

Cancel
 ↓
same slot
 ↓
Book again
 ↓
success

Then:

Reschedule
 ↓
existing occupied time
 ↓
409

If those work from the UI, the actual product flow is essentially complete.

Current status
CORE DATABASE             ✅
CONFLICT PROTECTION       ✅
CONFLICT TESTS            ✅
REGISTRATION              ✅
LOGIN/JWT                 ✅
DOCTOR SEARCH             ✅
BOOKING                   ✅
CANCELLATION              ✅
RESCHEDULE T6             ✅
CLOCK T2                  ✅
OUTBOX T1                 ✅
FRONTEND                  🔨 NOW

After the frontend works, stop adding features. We go straight into:

1. Fix any UI/API bugs
2. Add a few integration tests
3. README.md
4. REASONING.md
5. AI_LOGS.md
6. .gitignore
7. Git commit
8. Public GitHub repo

Those final documentation/repository requirements are easy to underestimate, so we should reserve time for them.

i had completed the frontent and now i want an precise reasoning.md file content of what we did.

Absolutely. Since this file is part of the assessment, it should read like your engineering reasoning, not like a generic AI-generated explanation. It should explain what was implemented, why, what trade-offs were made, how conflicts/cancellations work, what was tested, and what was intentionally kept simple.

Below is a ready-to-paste REASONING.md.

# Implementation Reasoning

## 1. Overview

This project implements a simple clinic appointment system using:

- Python
- FastAPI
- SQLAlchemy
- SQLite
- JWT authentication
- HTML/CSS/JavaScript frontend

The main requirement was to ensure that a doctor can never have overlapping booked appointments while correctly handling cancellations and rescheduling.

The implementation was intentionally kept simple because the assessment is time-constrained. The goal was to build a working end-to-end system with a real database, REST APIs, usable UI, authentication, conflict prevention, cancellation handling, automation endpoints, testing, and documentation without introducing unnecessary architectural complexity.

---

# 2. Main Requirements

The implementation focuses on the following core capabilities:

1. Patient and doctor registration
2. Login and JWT-based authentication
3. Doctor search
4. Pagination and sorting
5. Appointment booking
6. Prevention of overlapping appointments
7. Early and late cancellation handling
8. Appointment rescheduling
9. Automatic no-show handling through `POST /clock`
10. Daily appointment reminders through `POST /outbox`
11. Simple browser-based frontend
12. Automated tests for appointment conflict rules

---

# 3. Database Design

I used three main tables:

```text
users
   |
   |---- doctors
   |
   |---- appointments
             |
             |---- doctors
3.1 Users

The users table stores authentication and basic user information.

Important fields:

id
name
email
password_hash
role
created_at

The role field currently supports:

patient
doctor

Passwords are never stored directly. Only password hashes are stored.

The email field is unique so that the same email cannot be registered multiple times.

A database check constraint also prevents invalid roles from being inserted.

3.2 Doctors

The doctors table contains doctor-specific information:

id
user_id
specialization
experience
consultation_fee
created_at

A doctor is associated with a user account through user_id.

user_id is unique in the doctors table so that one user cannot accidentally have multiple doctor profiles.

The database also ensures:

experience >= 0
consultation_fee >= 0
3.3 Appointments

The appointments table contains:

id
doctor_id
patient_id
start_time
end_time
status
created_at
cancelled_at

The appointment duration is fixed at 30 minutes.

For example:

start_time = 10:00
end_time   = 10:30

This keeps the implementation simple and avoids introducing a separate time-slot management system.

The database ensures:

end_time > start_time

Valid appointment statuses are:

booked
cancelled_early
cancelled_late
completed
no_show

Cancelled appointments are retained instead of deleted so that appointment history is preserved.

4. Appointment Conflict Prevention
4.1 The main invariant

The most important rule in the system is:

A doctor must never have two overlapping booked appointments.

Two appointment intervals overlap when:

existing.start_time < new.end_time
AND
existing.end_time > new.start_time

For example:

Existing:
10:00 -------- 10:30

New:
10:15 -------- 10:45

Result: CONFLICT

However:

Existing:
10:00 -------- 10:30

New:
10:30 -------- 11:00

Result: ALLOWED

This is intentional because the appointments only touch at the boundary.

5. Two-Layer Conflict Protection

I used two levels of protection.

5.1 Application-level check

Before creating an appointment, the backend checks whether the doctor already has a conflicting booked appointment.

The query checks:

same doctor
AND
status = booked
AND
existing.start_time < new.end_time
AND
existing.end_time > new.start_time

If a conflict exists, the API returns:

HTTP 409 Conflict

with an appropriate error message.

This provides a clean response to normal API users.

5.2 Database-level protection

The application-level check alone is not enough for complete protection.

For example, two requests could theoretically execute at nearly the same time:

Request A → check → available
Request B → check → available
Request A → insert
Request B → insert

Both requests could pass the application check before either insert is visible to the other request.

To protect the actual database invariant, SQLite triggers were added.

The database trigger checks for another booked appointment belonging to the same doctor and rejects the insert if the intervals overlap.

A second trigger protects updates so that an appointment cannot be moved into an overlapping time.

The important design is therefore:

                Booking request
                       |
                       v
             Application conflict check
                       |
                conflict?
                 /       \
               yes        no
               |           |
              409        database insert
                           |
                           v
                    SQLite trigger
                           |
                    overlap check
                      /       \
                    yes        no
                    |           |
                 rollback     commit

This gives both a useful API response and database-level enforcement.

6. Why I Did Not Use a Separate Slot Table

A separate time_slots table could have been created, but it was unnecessary for this assessment.

The system has a fixed 30-minute appointment duration, so storing:

start_time
end_time

is sufficient.

A separate slot-generation system would add:

additional tables
slot generation logic
more API complexity
more frontend complexity

without improving the core requirement.

7. Cancellation Logic

Appointments are not deleted when cancelled.

Instead, the status is changed.

The cancellation rule is:

>= 24 hours before appointment
        ↓
cancelled_early

< 24 hours before appointment
        ↓
cancelled_late

The server determines the cancellation type using the appointment start time and the current time.

The client does not decide whether a cancellation is early or late.

This prevents clients from manipulating the cancellation classification.

The cancellation timestamp is also stored in:

cancelled_at
8. Why Cancelled Appointments Do Not Block New Bookings

The conflict query and database triggers only consider appointments where:

status = 'booked'

Therefore:

booked
   ↓
cancelled_early

or:

booked
   ↓
cancelled_late

removes the appointment from conflict checking.

This allows another patient to book the released time.

The original appointment remains in the database for history.

9. Rescheduling

The assessment requires rescheduling:

Move an appointment to a new time while keeping the same doctor and patient and ensuring that the new time is conflict-free.

The rescheduling endpoint checks:

Appointment exists
Current user owns the appointment
Appointment is still booked
New time is in the future
The new time does not overlap another booked appointment for the same doctor

The appointment itself is excluded from the conflict query.

For example:

Appointment #5
10:00 - 10:30

When moving it to:

11:00 - 11:30

appointment #5 should not be considered a conflict with itself.

Therefore the query excludes:

Appointment.id != current_appointment.id

The doctor_id and patient_id remain unchanged. Only the start and end times are updated.

The database-level update trigger provides an additional safety layer.

10. Authentication

Authentication uses:

JWT

The registration process is:

registration request
       ↓
validate input
       ↓
hash password
       ↓
save user

During login:

email + password
       ↓
find user
       ↓
verify password hash
       ↓
generate JWT
       ↓
return access token

Protected endpoints use the JWT to identify the current user.

The token contains the user ID and role.

For this assessment, the JWT secret is kept in the application configuration for simplicity. In a production application it should be stored in an environment variable or secret-management system.

11. Doctor Search

The doctor API supports:

search
pagination
sorting

Example:

GET /api/doctors?search=cardio&page=1&limit=10

Sorting can be performed using fields such as:

experience
fee
id

Only known sort fields are accepted rather than directly accepting arbitrary database column names.

This avoids unsafe dynamic query construction.

12. Appointment Listing

The appointment listing endpoint supports:

page
limit
sort
order

Patients see their own appointments.

Doctors see appointments associated with their doctor profile.

Pagination is implemented using:

offset = (page - 1) * limit

and:

limit

The maximum page size is restricted to prevent unnecessarily large queries.

13. POST /clock — No-Show Automation

The assessment requires:

Automatically mark an appointment as no-show 30 minutes after its start if it has not been completed.

Instead of introducing a background scheduler or task queue, I implemented the behavior through:

POST /api/appointments/clock

This matches the assessment requirement that the automation is graded through a /clock request.

The endpoint:

Finds appointments with status booked
Finds appointments whose start time is at least 30 minutes in the past
Changes their status to:
no_show

Appointments that are already:

completed
cancelled_early
cancelled_late

are not changed.

This approach keeps the implementation deterministic and easy to test.

14. POST /outbox — Daily Reminders

The assessment also requires morning reminders for today's appointments.

I implemented:

POST /api/appointments/outbox

The endpoint finds today's booked appointments and creates reminder payloads containing information such as:

appointment ID
patient ID
patient name
doctor ID
doctor name
appointment time
reminder message

The endpoint represents the notification/outbox stage rather than pretending that an SMS or email was actually delivered.

A production version could connect this outbox to:

email
SMS
push notifications
a message queue
an external Notification Service

The current implementation keeps the assessment scope small while still demonstrating the required workflow.

15. REST API Structure

The main endpoints are:

Authentication
POST /api/auth/register
POST /api/auth/login
GET  /api/auth/me
Doctors
GET /api/doctors

Supports search, pagination and sorting.

Appointments
POST   /api/appointments
GET    /api/appointments
PATCH  /api/appointments/{appointment_id}/cancel
PATCH  /api/appointments/{appointment_id}/reschedule
POST   /api/appointments/clock
POST   /api/appointments/outbox

FastAPI also provides Swagger/OpenAPI documentation automatically through:

/docs
16. Frontend Approach

I used a simple HTML/CSS/JavaScript frontend instead of React.

The reason was primarily time and scope.

The assessment requires a usable UI, not a particular frontend framework.

The frontend provides:

landing page
registration
login
doctor search
appointment booking
appointment listing
cancellation
rescheduling
logout

The frontend communicates with the FastAPI REST APIs using JavaScript fetch() calls.

Authentication tokens are stored in browser local storage and sent with protected API requests using the:

Authorization: Bearer <token>

header.

17. Landing Page

The landing page includes the required information:

Product

A clinic appointment management system focused on conflict-free scheduling.

Features
Doctor search
Appointment booking
Double-booking prevention
Cancellation handling
Rescheduling
Appointment management
Target Users
Patients
Doctors
Clinics
Benefits
Prevents scheduling conflicts
Simplifies appointment management
Maintains appointment history
Supports conflict-free rescheduling
Future Features

Three possible future features are presented:

SMS and email reminders
Online payments
Video consultations
18. Testing Strategy

The most important tests were focused on the appointment conflict invariant.

The following scenarios were tested:

Same slot
10:00 - 10:30
10:00 - 10:30

Expected:

Second appointment rejected
Partial overlap
10:00 - 10:30
10:15 - 10:45

Expected:

Second appointment rejected
Containing overlap
10:00 - 11:00
10:15 - 10:45

Expected:

Second appointment rejected
Adjacent appointments
10:00 - 10:30
10:30 - 11:00

Expected:

Both appointments accepted

The conflict tests initially failed because the SQLite triggers were registered from main.py, while the test module imported the database and models directly.

The test process therefore created the tables but never executed the trigger-registration function.

The issue was identified and fixed by explicitly registering the database triggers during test setup.

After the fix:

4 conflict tests passed

This confirmed that the database-level conflict protection behaved as intended.

19. Bugs / Issues Encountered and Fixes
Issue 1 — Database trigger was not active during tests
Problem

The triggers were initially created from main.py.

The tests imported:

database.py
models.py

directly.

Therefore main.py was never imported and the triggers were not registered.

Fix

Trigger initialization was explicitly performed during test setup.

Result

The same-slot, overlapping and containing-overlap tests correctly failed when an invalid appointment was inserted, while the adjacent appointment test succeeded.

Issue 2 — Port conflict during local development

Port 8000 was already being used, so the application was run on another available port.

The application itself does not depend on a specific port, so the server was configured to use port 8001.

This was an environment/development issue and did not require any application logic changes.

20. Important Design Trade-offs

Because this was a time-constrained coding assessment, several intentionally simple choices were made.

SQLite instead of PostgreSQL

SQLite was sufficient for the assessment because:

It is a real relational database
It requires no separate database server
SQLAlchemy provides the required ORM layer
It is easy to run and demonstrate

A production deployment with multiple application instances and higher concurrency would be better suited to PostgreSQL.

Vanilla JavaScript instead of React

The assessment required a usable UI, not a specific framework.

Vanilla JavaScript reduced setup and build time.

Fixed 30-minute appointments

This removed the need for a complex scheduling/availability system.

/clock instead of a scheduler

The assessment explicitly provides /clock as the grading mechanism, so a real background scheduler was unnecessary.

/outbox instead of a real notification provider

The endpoint demonstrates the notification workflow without requiring external SMS/email credentials.

No separate repository/service layers

The project is intentionally small. Adding repositories, service interfaces, factories, or other abstractions would increase code size without providing significant value for this assessment.

21. Security Considerations

The following security-related practices are implemented:

Passwords are hashed rather than stored in plain text.
JWT authentication protects private endpoints.
Users cannot cancel or reschedule another patient's appointment.
Patients cannot book appointments as doctors.
Input values are validated.
Doctor and appointment IDs are validated through database relationships.
Sort fields are restricted to an allowed set.
Appointment conflict checks are performed server-side.
Database triggers provide an additional integrity boundary.

For production, the following would still need improvement:

Store JWT secret in environment/secret management.
Use HTTPS.
Add token refresh/revocation strategy.
Add rate limiting.
Use PostgreSQL or another production database.
Add stronger role/permission management.
Add proper notification provider integration.
Add audit logging.
22. What I Would Improve With More Time

If this system were extended beyond the assessment, I would consider:

Doctor availability schedules
Variable appointment durations
Time-zone aware timestamps
PostgreSQL for production deployment
Database migrations using Alembic
Real notification service integration
Email/SMS reminders
Online payments
Video consultations
Admin/clinic management
Better frontend validation and error handling
More comprehensive integration and concurrency tests
Proper secret management
Appointment history and audit logs
23. Final Implementation Summary

The main design decision was to keep the system small while protecting the most important business invariant.

The central rule is:

A doctor cannot have overlapping BOOKED appointments.

This is enforced at both the application and database levels.

The resulting flow is:

Patient
   |
   v
Search Doctor
   |
   v
Select Time
   |
   v
Backend Conflict Check
   |
   +---- conflict ----> 409 Conflict
   |
   v
Database Trigger
   |
   +---- overlap -----> reject
   |
   v
Appointment Created

Cancellation changes the appointment status rather than deleting the record:

booked
  |
  +---- >= 24h ----> cancelled_early
  |
  +---- < 24h -----> cancelled_late

Rescheduling reuses the same conflict rule while keeping the original doctor and patient.

The /clock endpoint handles no-show automation, while /outbox generates reminders for today's appointments.

Overall, the implementation prioritizes correctness of appointment scheduling, clear API behavior, database integrity, and a complete end-to-end user flow while deliberately avoiding unnecessary complexity for the scope of the assessment.


### One important correction before you save it

In the **testing section**, only claim tests that you actually ran. From our work together, we know the **4 conflict tests passed**, but if you haven't yet run integration tests for `/clock`, `/outbox`, cancellation, rescheduling, etc., don't claim those as automated tests.

Also, since the assessor explicitly requested `AI_LOGS.md` **“containing our complete conversation as-is,” don't put a summarized version there**. `REASONING.md` is the place for the engineering summary above; `AI_LOGS.md` should preserve the actual conversation verbatim.
Also give a readme to paste.

Absolutely. Here's a concise but assessment-ready README.md that matches what we actually built. You can paste it directly into your repository.

# Clinic Appointment System

A simple clinic appointment management system built with **FastAPI, SQLAlchemy, SQLite, HTML, CSS, and JavaScript**.

The primary goal of the system is to ensure that a doctor can **never have overlapping booked appointments**, while supporting registration, authentication, doctor search, booking, cancellation, rescheduling, reminders, and no-show handling.

---

## Features

### Authentication
- Patient and doctor registration
- Secure password hashing
- JWT-based login
- Protected API endpoints
- Current-user endpoint

### Doctor Management
- Search doctors by specialization
- Pagination
- Sorting by experience, fee, or ID

### Appointment Management
- Book a 30-minute appointment
- Prevent overlapping appointments for the same doctor
- View user-specific appointments
- Early cancellation
- Late cancellation
- Reschedule appointments
- Preserve cancelled appointment history

### Automation
- `POST /api/appointments/clock`
  - Automatically marks eligible booked appointments as `no_show` after 30 minutes.
- `POST /api/appointments/outbox`
  - Generates reminder messages for today's booked appointments.

### Frontend
- Product landing page
- Feature and benefit sections
- Target-user information
- Future feature section
- Patient/doctor registration
- Login
- Doctor search
- Appointment booking
- Appointment listing
- Cancellation
- Rescheduling

---

## Tech Stack

| Component | Technology |
|---|---|
| Backend | Python |
| API Framework | FastAPI |
| ORM | SQLAlchemy |
| Database | SQLite |
| Authentication | JWT |
| Password Hashing | Argon2 via `pwdlib` |
| Frontend | HTML, CSS, JavaScript |
| API Documentation | FastAPI / Swagger |
| Testing | Pytest |

---

## Project Structure

```text
clinic-appointment-system/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── database.py
│   ├── database_constraints.py
│   ├── models.py
│   ├── schemas.py
│   ├── auth.py
│   ├── dependencies.py
│   ├── appointment_service.py
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── doctors.py
│   │   └── appointments.py
│   │
│   ├── templates/
│   │   ├── index.html
│   │   ├── login.html
│   │   ├── register.html
│   │   └── dashboard.html
│   │
│   └── static/
│       ├── style.css
│       └── app.js
│
├── tests/
│   └── test_appointment_conflicts.py
│
├── clinic.db
├── requirements.txt
├── README.md
├── REASONING.md
└── AI_LOGS.md
Database Design

The application uses three main tables.

Users

Stores patient and doctor accounts.

id
name
email
password_hash
role
created_at

Roles:

patient
doctor
Doctors

Stores doctor-specific information.

id
user_id
specialization
experience
consultation_fee
created_at

Each doctor profile belongs to one user account.

Appointments

Stores appointment information.

id
doctor_id
patient_id
start_time
end_time
status
created_at
cancelled_at

Appointments have a fixed duration of 30 minutes.

Possible statuses:

booked
cancelled_early
cancelled_late
completed
no_show
Appointment Conflict Prevention

This is the core business rule of the application.

A doctor cannot have two overlapping booked appointments.

Two appointments overlap when:

existing.start_time < new.end_time
AND
existing.end_time > new.start_time

For example:

10:00 - 10:30
10:15 - 10:45

is rejected.

But:

10:00 - 10:30
10:30 - 11:00

is allowed because the appointments are adjacent.

Two-level protection

The system uses:

Application-level conflict checking
SQLite database triggers

The application check allows the API to return a clear:

409 Conflict

response.

The SQLite trigger provides database-level protection so that overlapping appointments cannot be inserted or updated even if the normal API validation is bypassed.

Cancellation Rules

Cancellation is classified based on the time remaining before the appointment.

>= 24 hours before appointment
        ↓
cancelled_early

< 24 hours before appointment
        ↓
cancelled_late

Cancelled appointments are not deleted. Their status is changed so that appointment history is preserved.

Cancelled appointments do not block the doctor's time slot because only appointments with:

status = booked

participate in conflict checking.

Rescheduling

A patient can reschedule their own booked appointment.

The system verifies:

Appointment exists
Patient owns the appointment
Appointment is still booked
New time is in the future
New time does not conflict with another booked appointment for the doctor

The doctor and patient remain unchanged.

Only the appointment time is updated.

API Endpoints
Authentication
Register
POST /api/auth/register

Example:

{
  "name": "John Doe",
  "email": "john@example.com",
  "password": "password123",
  "role": "patient"
}

For a doctor:

{
  "name": "Dr. Sharma",
  "email": "doctor@example.com",
  "password": "password123",
  "role": "doctor",
  "specialization": "Cardiology",
  "experience": 8,
  "consultation_fee": 500
}
Login
POST /api/auth/login

Returns a JWT access token.

Current User
GET /api/auth/me

Requires:

Authorization: Bearer <token>
Doctors
Search/List Doctors
GET /api/doctors

Supported parameters:

search
page
limit
sort
order

Example:

GET /api/doctors?search=cardio&page=1&limit=5&sort=experience&order=desc

Supported sorting fields include:

experience
fee
id
Appointments
Book Appointment
POST /api/appointments

Parameters:

doctor_id
start_time

Example:

POST /api/appointments?doctor_id=1&start_time=2026-09-20T10:00

Appointment duration is automatically set to 30 minutes.

Possible responses:

201 Created
400 Bad Request
403 Forbidden
404 Not Found
409 Conflict
List Appointments
GET /api/appointments

Supported parameters:

page
limit
sort
order

Example:

GET /api/appointments?page=1&limit=10&sort=start_time&order=asc

Patients receive their appointments.

Doctors receive appointments associated with their doctor profile.

Cancel Appointment
PATCH /api/appointments/{appointment_id}/cancel

The server determines whether the cancellation is early or late.

Reschedule Appointment
PATCH /api/appointments/{appointment_id}/reschedule

Parameter:

new_start_time

Example:

PATCH /api/appointments/5/reschedule?new_start_time=2026-09-20T11:00
Automation Endpoints
No-Show Processing
POST /api/appointments/clock

The endpoint finds booked appointments that started at least 30 minutes ago and changes their status to:

no_show

Example response:

{
  "message": "Clock processed successfully",
  "no_show_count": 1
}
Daily Reminder Outbox
POST /api/appointments/outbox

Finds today's booked appointments and generates reminder messages.

Example response:

{
  "date": "2026-09-20",
  "reminder_count": 1,
  "reminders": [
    {
      "appointment_id": 5,
      "patient_id": 2,
      "patient_name": "John Doe",
      "doctor_id": 1,
      "doctor_name": "Dr. Sharma",
      "appointment_time": "2026-09-20T10:00:00",
      "message": "Reminder: You have an appointment with Dr. Sharma at 10:00."
    }
  ]
}

The current implementation generates the notification payload rather than integrating an external SMS/email provider.

Installation
1. Clone the repository
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd clinic-appointment-system
2. Create a virtual environment
Windows
python -m venv venv

Activate it:

.\venv\Scripts\Activate.ps1

If PowerShell execution policy prevents activation, the environment can still be used directly:

venv\Scripts\python.exe
3. Install dependencies
pip install -r requirements.txt
Running the Application

Start the FastAPI server:

uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

For local development, the application will be available at:

http://127.0.0.1:8001

The frontend landing page:

http://127.0.0.1:8001/

Swagger API documentation:

http://127.0.0.1:8001/docs

If running inside GitHub Codespaces, open the forwarded port shown by the Codespaces Ports panel.

Database

SQLite is used as the database.

The database file:

clinic.db

is automatically created when the application starts.

SQLAlchemy creates the required tables:

users
doctors
appointments

The application also registers SQLite triggers that enforce appointment conflict protection.

Testing

Run all tests:

pytest -v

Run the appointment conflict tests:

pytest tests/test_appointment_conflicts.py -v

The conflict test suite covers:

Same slot
10:00 - 10:30
10:00 - 10:30

Expected: second appointment rejected.

Partial overlap
10:00 - 10:30
10:15 - 10:45

Expected: second appointment rejected.

Containing overlap
10:00 - 11:00
10:15 - 10:45

Expected: second appointment rejected.

Adjacent appointments
10:00 - 10:30
10:30 - 11:00

Expected: both appointments accepted.

Debugging
Check the API

Open:

/docs

FastAPI's Swagger interface can be used to test all endpoints without needing a separate API client.

Check the database

The SQLite database is stored as:

clinic.db

The tables can be inspected using any SQLite-compatible database browser.

Common issues
Port already in use

Use another port:

uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
Database tables not visible

Stop and restart the application so that SQLAlchemy initialization runs.

Conflict tests fail

Ensure the SQLite appointment triggers are registered before running the tests.

The tests need to initialize both:

database tables
+
appointment conflict triggers
Application Flow

The main patient flow is:

Landing Page
      ↓
Register
      ↓
Login
      ↓
Dashboard
      ↓
Search Doctors
      ↓
Select Doctor
      ↓
Book Appointment
      ↓
Conflict Check
      ↓
Appointment Created

For an existing appointment:

Appointment
    |
    +---- Cancel ----> cancelled_early / cancelled_late
    |
    +---- Reschedule -> conflict check -> new time

For automation:

POST /clock
      ↓
Find appointments >30 minutes past start
      ↓
Mark as no_show

and:

POST /outbox
      ↓
Find today's booked appointments
      ↓
Generate reminder messages
Future Improvements

The current implementation intentionally focuses on the assessment requirements.

Possible production improvements include:

Real email/SMS notifications
Online payments
Video consultations
Doctor availability schedules
Variable appointment durations
PostgreSQL for production
Database migrations using Alembic
Admin/clinic management
Better audit logging
Improved frontend validation
Automated background scheduling
More extensive concurrency testing
Design Decisions

The implementation intentionally avoids unnecessary complexity.

Why SQLite?

It provides a real relational database without requiring a separate database server and is sufficient for the scope of this assessment.

Why FastAPI?

FastAPI provides simple REST API development, validation, dependency injection, and automatic Swagger documentation.

Why fixed 30-minute appointments?

It keeps scheduling logic simple while still demonstrating conflict detection and rescheduling.

Why database triggers?

Application-level validation alone may not protect the database from concurrent or direct inserts. SQLite triggers provide an additional database-level invariant.

Why vanilla JavaScript?

The assessment requires a usable frontend rather than a particular frontend framework. Vanilla JavaScript reduces setup and build complexity.

Why /clock instead of a background scheduler?

The assessment provides /clock as the mechanism for grading the no-show automation, so a full scheduling system is unnecessary.

License

This project was created as part of a coding assessment.


### Before pushing to GitHub

One thing I **strongly recommend**: don't commit your existing `clinic.db` unless the assessment specifically wants the database file.

Add this to `.gitignore`:

```gitignore
venv/
__pycache__/
*.pyc
.env
clinic.db
.pytest_cache/

Then your GitHub repository contains the code and documentation, while SQLite creates a fresh database when the evaluator runs the project.

Also make sure the README's clone URL is replaced with your actual public repository URL before submission.