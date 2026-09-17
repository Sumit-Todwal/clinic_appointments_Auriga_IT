from sqlalchemy import text

from app.database import engine


def _ensure_no_show_status():
    with engine.begin() as connection:
        status_constraint = connection.execute(
            text(
                """
                SELECT sql
                FROM sqlite_master
                WHERE type = 'table' AND name = 'appointments'
                """
            )
        ).scalar_one_or_none()

        if status_constraint is None or "'no_show'" in status_constraint:
            return

        connection.execute(text("DROP TRIGGER IF EXISTS prevent_doctor_overlap"))
        connection.execute(
            text("DROP TRIGGER IF EXISTS prevent_doctor_overlap_update")
        )
        connection.execute(
            text("ALTER TABLE appointments RENAME TO appointments_legacy")
        )
        connection.execute(
            text(
                """
                CREATE TABLE appointments (
                    id INTEGER NOT NULL PRIMARY KEY,
                    doctor_id INTEGER NOT NULL,
                    patient_id INTEGER NOT NULL,
                    start_time DATETIME NOT NULL,
                    end_time DATETIME NOT NULL,
                    status VARCHAR(30) NOT NULL,
                    created_at DATETIME NOT NULL,
                    cancelled_at DATETIME,
                    CONSTRAINT check_valid_appointment_time
                        CHECK (end_time > start_time),
                    CONSTRAINT check_appointment_status
                        CHECK (status IN (
                            'booked', 'cancelled_early', 'cancelled_late',
                            'completed', 'no_show'
                        )),
                    FOREIGN KEY(doctor_id) REFERENCES doctors (id)
                        ON DELETE CASCADE,
                    FOREIGN KEY(patient_id) REFERENCES users (id)
                        ON DELETE CASCADE
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO appointments (
                    id, doctor_id, patient_id, start_time, end_time,
                    status, created_at, cancelled_at
                )
                SELECT
                    id, doctor_id, patient_id, start_time, end_time,
                    status, created_at, cancelled_at
                FROM appointments_legacy
                """
            )
        )
        connection.execute(text("DROP TABLE appointments_legacy"))
        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_doctor_appointment_time
                ON appointments (doctor_id, start_time, end_time)
                """
            )
        )


def create_appointment_triggers():
    _ensure_no_show_status()

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