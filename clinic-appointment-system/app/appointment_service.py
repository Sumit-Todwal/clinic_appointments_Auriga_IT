from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Appointment


def has_appointment_conflict(
    db: Session,
    doctor_id: int,
    start_time: datetime,
    end_time: datetime,
) -> bool:

    conflict = db.scalar(
        select(Appointment.id)
        .where(
            Appointment.doctor_id == doctor_id,
            Appointment.status == "booked",

            # Existing appointment starts before
            # the new appointment ends
            Appointment.start_time < end_time,

            # Existing appointment ends after
            # the new appointment starts
            Appointment.end_time > start_time,
        )
        .limit(1)
    )

    return conflict is not None