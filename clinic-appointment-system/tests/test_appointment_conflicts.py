from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import User, Doctor, Appointment


def create_test_doctor(db):
    user = User(
        name="Test Doctor",
        email="doctor_test@example.com",
        password_hash="dummy",
        role="doctor",
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    doctor = Doctor(
        user_id=user.id,
        specialization="Cardiology",
        experience=5,
        consultation_fee=500,
    )

    db.add(doctor)
    db.commit()
    db.refresh(doctor)

    return user, doctor


def create_test_patient(db):
    patient = User(
        name="Test Patient",
        email="patient_test@example.com",
        password_hash="dummy",
        role="patient",
    )

    db.add(patient)
    db.commit()
    db.refresh(patient)

    return patient


@pytest.fixture
def db():
    db = SessionLocal()

    try:
        yield db
    finally:
        # Clean test data
        db.query(Appointment).delete()
        db.query(Doctor).delete()
        db.query(User).filter(
            User.email.in_([
                "doctor_test@example.com",
                "patient_test@example.com",
            ])
        ).delete(synchronize_session=False)

        db.commit()
        db.close()


def make_appointment(
    db,
    doctor_id,
    patient_id,
    start,
    duration=30,
):
    appointment = Appointment(
        doctor_id=doctor_id,
        patient_id=patient_id,
        start_time=start,
        end_time=start + timedelta(minutes=duration),
        status="booked",
    )

    db.add(appointment)
    db.commit()

    return appointment



def test_same_slot_is_rejected(db):
    _, doctor = create_test_doctor(db)
    patient = create_test_patient(db)

    start = datetime(2026, 9, 20, 10, 0)

    make_appointment(
        db,
        doctor.id,
        patient.id,
        start,
    )

    with pytest.raises(IntegrityError):
        make_appointment(
            db,
            doctor.id,
            patient.id,
            start,
        )

    db.rollback()


def test_overlapping_appointment_is_rejected(db):
    _, doctor = create_test_doctor(db)
    patient = create_test_patient(db)

    first_start = datetime(2026, 9, 20, 10, 0)

    make_appointment(
        db,
        doctor.id,
        patient.id,
        first_start,
    )

    overlapping_start = datetime(
        2026,
        9,
        20,
        10,
        15,
    )

    with pytest.raises(IntegrityError):
        make_appointment(
            db,
            doctor.id,
            patient.id,
            overlapping_start,
        )

    db.rollback()

def test_existing_appointment_inside_new_range_is_rejected(db):
    _, doctor = create_test_doctor(db)
    patient = create_test_patient(db)

    first_start = datetime(2026, 9, 20, 10, 15)

    make_appointment(
        db,
        doctor.id,
        patient.id,
        first_start,
    )

    new_start = datetime(2026, 9, 20, 10, 0)

    new_appointment = Appointment(
        doctor_id=doctor.id,
        patient_id=patient.id,
        start_time=new_start,
        end_time=datetime(2026, 9, 20, 11, 0),
        status="booked",
    )

    db.add(new_appointment)

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_adjacent_appointment_is_allowed(db):
    _, doctor = create_test_doctor(db)
    patient = create_test_patient(db)

    first_start = datetime(2026, 9, 20, 10, 0)

    first = make_appointment(
        db,
        doctor.id,
        patient.id,
        first_start,
    )

    second_start = datetime(2026, 9, 20, 10, 30)

    second = make_appointment(
        db,
        doctor.id,
        patient.id,
        second_start,
    )

    assert first.id != second.id

