from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = "patient"

    # Required only when role = doctor
    specialization: str | None = None
    experience: int | None = None
    consultation_fee: float | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str

    model_config = ConfigDict(from_attributes=True)


class DoctorResponse(BaseModel):
    id: int
    user_id: int
    specialization: str
    experience: int
    consultation_fee: float

    model_config = ConfigDict(from_attributes=True)


class AppointmentResponse(BaseModel):
    id: int
    doctor_id: int
    patient_id: int
    start_time: datetime
    end_time: datetime
    status: str

    model_config = ConfigDict(from_attributes=True)