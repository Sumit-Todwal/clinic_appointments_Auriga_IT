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