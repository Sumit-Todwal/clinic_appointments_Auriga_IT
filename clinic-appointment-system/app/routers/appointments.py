from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Appointment, Doctor, User
from app.appointment_service import has_appointment_conflict
from app.schemas import AppointmentResponse


router = APIRouter(
    prefix="/api/appointments",
    tags=["Appointments"],
)

APPOINTMENT_DURATION = timedelta(minutes=30)


def _as_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value

    return value.astimezone(timezone.utc).replace(tzinfo=None)


@router.post(
    "",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_appointment(
    doctor_id: int,
    start_time: datetime,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Only patients can book
    if current_user.role != "patient":
        raise HTTPException(
            status_code=403,
            detail="Only patients can book appointments",
        )

    doctor = db.get(Doctor, doctor_id)

    if not doctor:
        raise HTTPException(
            status_code=404,
            detail="Doctor not found",
        )

    start_time = _as_utc_naive(start_time)

    end_time = start_time + APPOINTMENT_DURATION

    # Don't allow booking in the past
    now = datetime.utcnow()

    if start_time <= now:
        raise HTTPException(
            status_code=400,
            detail="Appointment must be in the future",
        )

    # Application-level conflict check
    if has_appointment_conflict(
        db,
        doctor_id,
        start_time,
        end_time,
    ):
        raise HTTPException(
            status_code=409,
            detail="Doctor already has an appointment during this time",
        )

    appointment = Appointment(
        doctor_id=doctor_id,
        patient_id=current_user.id,
        start_time=start_time,
        end_time=end_time,
        status="booked",
    )

    db.add(appointment)

    try:
        db.commit()
        db.refresh(appointment)
    except IntegrityError:
        db.rollback()

        # Database trigger is the final protection
        raise HTTPException(
            status_code=409,
            detail="Doctor already has an overlapping appointment",
        )

    return appointment



@router.get("", response_model=list[AppointmentResponse])
def get_appointments(
    page: int = 1,
    limit: int = 10,
    sort: str = "start_time",
    order: str = "asc",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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

    query = db.query(Appointment)

    if current_user.role == "patient":
        query = query.filter(
            Appointment.patient_id == current_user.id
        )

    elif current_user.role == "doctor":
        doctor = db.query(Doctor).filter(
            Doctor.user_id == current_user.id
        ).first()

        if not doctor:
            raise HTTPException(
                status_code=404,
                detail="Doctor profile not found",
            )

        query = query.filter(
            Appointment.doctor_id == doctor.id
        )

    allowed_sort_fields = {
        "start_time": Appointment.start_time,
        "created_at": Appointment.created_at,
        "status": Appointment.status,
    }

    sort_column = allowed_sort_fields.get(sort)

    if not sort_column:
        raise HTTPException(
            status_code=400,
            detail="Invalid sort field",
        )

    if order == "desc":
        query = query.order_by(sort_column.desc())
    elif order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        raise HTTPException(
            status_code=400,
            detail="Order must be asc or desc",
        )

    offset = (page - 1) * limit

    return query.offset(offset).limit(limit).all()


@router.patch(
    "/{appointment_id}/cancel",
    response_model=AppointmentResponse,
)
def cancel_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    appointment = db.get(Appointment, appointment_id)

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found",
        )

    # Patient can cancel only their own appointment
    if appointment.patient_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only cancel your own appointments",
        )

    if appointment.status != "booked":
        raise HTTPException(
            status_code=400,
            detail="Only booked appointments can be cancelled",
        )

    now = datetime.utcnow()

    # 24-hour cancellation rule
    if appointment.start_time - now >= timedelta(hours=24):
        appointment.status = "cancelled_early"
    else:
        appointment.status = "cancelled_late"

    appointment.cancelled_at = now

    db.commit()
    db.refresh(appointment)

    return appointment

@router.patch(
    "/{appointment_id}/reschedule",
    response_model=AppointmentResponse,
)
def reschedule_appointment(
    appointment_id: int,
    new_start_time: datetime,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    appointment = db.get(Appointment, appointment_id)

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found",
        )

    if appointment.patient_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only reschedule your own appointments",
        )

    if appointment.status != "booked":
        raise HTTPException(
            status_code=400,
            detail="Only booked appointments can be rescheduled",
        )

    # Keep the database's naive datetime convention
    new_start_time = _as_utc_naive(new_start_time)

    new_end_time = new_start_time + APPOINTMENT_DURATION

    if new_start_time <= datetime.utcnow():
        raise HTTPException(
            status_code=400,
            detail="New appointment time must be in the future",
        )

    # Check conflicts while excluding the appointment
    # being rescheduled.
    conflict = (
        db.query(Appointment)
        .filter(
            Appointment.id != appointment.id,
            Appointment.doctor_id == appointment.doctor_id,
            Appointment.status == "booked",
            Appointment.start_time < new_end_time,
            Appointment.end_time > new_start_time,
        )
        .first()
    )

    if conflict:
        raise HTTPException(
            status_code=409,
            detail="Doctor already has an appointment during the new time",
        )

    appointment.start_time = new_start_time
    appointment.end_time = new_end_time

    try:
        db.commit()
        db.refresh(appointment)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Doctor already has an overlapping appointment",
        )

    return appointment