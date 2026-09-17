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