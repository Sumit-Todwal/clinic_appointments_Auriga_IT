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
	db: Session = Depends(get_db),
):
	return db.query(Doctor).order_by(Doctor.id.asc()).all()


@router.get("/{doctor_id}", response_model=DoctorResponse)
def get_doctor(
	doctor_id: int,
	db: Session = Depends(get_db),
):
	doctor = db.get(Doctor, doctor_id)

	if doctor is None:
		raise HTTPException(status_code=404, detail="Doctor not found")

	return doctor

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