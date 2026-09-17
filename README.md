# clinic_appointments_Auriga_IT
Complete project required for the Assessment of Auriga IT.
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