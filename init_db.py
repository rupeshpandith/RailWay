"""Utility script to provision the Railway2.0 database schema and sample data."""

from __future__ import annotations

from datetime import date, timedelta

from mysql.connector import Error

from db_config import get_db_connection

EXPECTED_COLUMNS: dict[str, set[str]] = {
    "schedule": {
        "id",
        "train_id",
        "source_station_id",
        "destination_station_id",
        "travel_date",
        "departure_time",
        "arrival_time",
        "available_seats",
    },
    "coachtype": {
        "id",
        "code",
        "name",
        "base_fare",
        "fare_multiplier",
        "description",
    },
    "booking": {
        "id",
        "schedule_id",
        "coach_type_id",
        "passenger_name",
        "email",
        "status",
        "seat_number",
        "fare_amount",
        "created_at",
    },
    "ticket": {
        "id",
        "booking_id",
        "pnr",
        "issued_at",
    },
    "payment": {
        "id",
        "booking_id",
        "amount",
        "status",
        "method",
        "created_at",
    },
}

DROP_ORDER: tuple[str, ...] = (
    "payment",
    "ticket",
    "seat",
    "booking",
    "coachtype",
    "routestop",
    "schedule",
    "train",
    "station",
)

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS station (
        id INT AUTO_INCREMENT PRIMARY KEY,
        code VARCHAR(10) NOT NULL UNIQUE,
        name VARCHAR(120) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS coachtype (
        id INT AUTO_INCREMENT PRIMARY KEY,
        code VARCHAR(10) NOT NULL UNIQUE,
        name VARCHAR(120) NOT NULL,
        base_fare DECIMAL(10, 2) NOT NULL,
        fare_multiplier DECIMAL(5, 2) NOT NULL DEFAULT 1.00,
        description VARCHAR(255)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS train (
        id INT AUTO_INCREMENT PRIMARY KEY,
        number VARCHAR(10) NOT NULL UNIQUE,
        name VARCHAR(160) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS schedule (
        id INT AUTO_INCREMENT PRIMARY KEY,
        train_id INT NOT NULL,
        source_station_id INT NOT NULL,
        destination_station_id INT NOT NULL,
        travel_date DATE NOT NULL,
        departure_time TIME NOT NULL,
        arrival_time TIME NOT NULL,
        available_seats INT NOT NULL DEFAULT 100,
        FOREIGN KEY (train_id) REFERENCES train(id) ON DELETE CASCADE,
        FOREIGN KEY (source_station_id) REFERENCES station(id) ON DELETE RESTRICT,
        FOREIGN KEY (destination_station_id) REFERENCES station(id) ON DELETE RESTRICT
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS booking (
        id INT AUTO_INCREMENT PRIMARY KEY,
        schedule_id INT NOT NULL,
        coach_type_id INT NOT NULL,
        passenger_name VARCHAR(100) NOT NULL,
        email VARCHAR(120),
        status ENUM('PENDING', 'CONFIRMED', 'FAILED') NOT NULL DEFAULT 'PENDING',
        seat_number VARCHAR(10),
        fare_amount DECIMAL(10, 2) NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (schedule_id) REFERENCES schedule(id) ON DELETE CASCADE,
    FOREIGN KEY (coach_type_id) REFERENCES coachtype(id) ON DELETE RESTRICT
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS ticket (
        id INT AUTO_INCREMENT PRIMARY KEY,
        booking_id INT NOT NULL,
        pnr VARCHAR(20) NOT NULL UNIQUE,
        issued_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (booking_id) REFERENCES booking(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS payment (
        id INT AUTO_INCREMENT PRIMARY KEY,
        booking_id INT NOT NULL,
        amount DECIMAL(10, 2) NOT NULL,
        status ENUM('SUCCESS', 'FAILED', 'CONFIRMED') NOT NULL,
        method VARCHAR(50) NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (booking_id) REFERENCES booking(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
]

SAMPLE_STATIONS = [
    ("NDLS", "New Delhi"),
    ("MMCT", "Mumbai Central"),
    ("BPL", "Bhopal Junction"),
    ("LKO", "Lucknow"),
]

SAMPLE_TRAINS = [
    ("12001", "New Delhi - Bhopal Shatabdi"),
    ("12951", "Mumbai - New Delhi Rajdhani"),
    ("12230", "Lucknow Mail"),
]

SAMPLE_COACH_TYPES = [
    ("SL", "Sleeper", 450.00, 1.00, "Sleeper Class"),
    ("3A", "AC 3 Tier", 1050.00, 1.35, "AC 3 Tier"),
    ("2A", "AC 2 Tier", 1480.00, 1.70, "AC 2 Tier"),
]


def ensure_schema(cursor) -> None:
    for statement in SCHEMA_STATEMENTS:
        cursor.execute(statement)


def get_existing_columns(cursor, table_name: str) -> set[str]:
    try:
        cursor.execute(f"SHOW COLUMNS FROM `{table_name}`")
    except Error:
        return set()
    rows = cursor.fetchall()
    return {row[0] for row in rows}


def requires_reset(cursor) -> bool:
    for table, expected in EXPECTED_COLUMNS.items():
        existing = get_existing_columns(cursor, table)
        if existing and not expected.issubset(existing):
            return True
        if not existing and table == "coachtype":
            legacy_columns = get_existing_columns(cursor, "coach_type")
            if legacy_columns:
                return True
    return False


def drop_conflicting_tables(cursor) -> None:
    # The destructive drop logic is intentionally disabled to prevent accidental data loss.
    # This function now acts as a no-op placeholder.
    return


def seed_reference_data(cursor) -> None:
    cursor.execute("SELECT COUNT(*) FROM station")
    (station_count,) = cursor.fetchone()
    if station_count == 0:
        cursor.executemany("INSERT INTO station (code, name) VALUES (%s, %s)", SAMPLE_STATIONS)

    cursor.execute("SELECT COUNT(*) FROM train")
    (train_count,) = cursor.fetchone()
    if train_count == 0:
        cursor.executemany("INSERT INTO train (number, name) VALUES (%s, %s)", SAMPLE_TRAINS)

    cursor.execute("SELECT COUNT(*) FROM coachtype")
    (coach_type_count,) = cursor.fetchone()
    if coach_type_count == 0:
        cursor.executemany(
            "INSERT INTO coachtype (code, name, base_fare, fare_multiplier, description) VALUES (%s, %s, %s, %s, %s)",
            SAMPLE_COACH_TYPES,
        )


def seed_schedules(cursor) -> None:
    cursor.execute("SELECT COUNT(*) FROM schedule")
    (schedule_count,) = cursor.fetchone()
    if schedule_count > 0:
        return

    today = date.today()
    sample_rows = [
        # (train_id, source_id, dest_id, travel_date, departure_time, arrival_time, seats)
        (1, 1, 3, today + timedelta(days=1), "06:00:00", "12:30:00", 120),
        (2, 2, 1, today + timedelta(days=2), "16:45:00", "09:30:00", 90),
        (3, 4, 1, today + timedelta(days=3), "21:15:00", "07:10:00", 110),
    ]
    cursor.executemany(
        """
        INSERT INTO schedule (
            train_id,
            source_station_id,
            destination_station_id,
            travel_date,
            departure_time,
            arrival_time,
            available_seats
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        sample_rows,
    )


def main() -> None:
    try:
        conn = get_db_connection()
        conn.raise_on_warnings = False
    except Error as exc:
        raise SystemExit(f"Unable to connect to database: {exc}")

    try:
        cursor = conn.cursor()
        if requires_reset(cursor):
            print(
                "⚠️  Detected legacy schema differences. Automatic table drops are disabled; "
                "resolve schema conflicts manually before rerunning."
            )
            return

        ensure_schema(cursor)
        seed_reference_data(cursor)
        seed_schedules(cursor)
        conn.commit()
        print("✅ Database ready. Sample data inserted (only if tables were empty).")
    except Error as exc:
        conn.rollback()
        raise SystemExit(f"Database setup failed: {exc}")
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
