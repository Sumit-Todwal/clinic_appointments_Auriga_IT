from sqlalchemy import text

from app.database import engine


def create_appointment_triggers():
    with engine.begin() as connection:

        # Prevent overlapping INSERTs
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS prevent_doctor_overlap
            BEFORE INSERT ON appointments
            WHEN NEW.status = 'booked'
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Doctor already has an overlapping appointment'
                )
                WHERE EXISTS (
                    SELECT 1
                    FROM appointments
                    WHERE doctor_id = NEW.doctor_id
                      AND status = 'booked'
                      AND start_time < NEW.end_time
                      AND end_time > NEW.start_time
                );
            END;
        """))

        # Prevent overlapping UPDATEs
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS prevent_doctor_overlap_update
            BEFORE UPDATE OF doctor_id, start_time, end_time, status
            ON appointments
            WHEN NEW.status = 'booked'
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Doctor already has an overlapping appointment'
                )
                WHERE EXISTS (
                    SELECT 1
                    FROM appointments
                    WHERE id != NEW.id
                      AND doctor_id = NEW.doctor_id
                      AND status = 'booked'
                      AND start_time < NEW.end_time
                      AND end_time > NEW.start_time
                );
            END;
        """))