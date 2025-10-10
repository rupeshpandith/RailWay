import os
import random
import string
from contextlib import closing
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from flask import (
    Flask,
    abort,
    redirect,
    render_template,
    request,
    url_for,
)
from mysql.connector import Error

from db_config import get_db_connection


class DatabaseError(RuntimeError):
    """Raised when a database operation fails."""


class DomainError(RuntimeError):
    """Raised when business rules are violated (e.g., no seats left)."""


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "railway-dev-secret")


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _generate_pnr(booking_id: int) -> str:
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"PNR{booking_id:04d}{suffix}"


def _to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _compute_fare_amount(base, multiplier) -> Decimal:
    amount = _to_decimal(base) * _to_decimal(multiplier)
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _coerce_date(value):
    if isinstance(value, datetime):
        return value.date()
    return value


def _coerce_time(value):
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds()) % (24 * 3600)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return time(hour=hours, minute=minutes, second=seconds)
    return value


def _normalize_schedule_row(row: dict | None):
    if not row:
        return row
    row["travel_date"] = _coerce_date(row.get("travel_date"))
    row["departure_time"] = _coerce_time(row.get("departure_time"))
    row["arrival_time"] = _coerce_time(row.get("arrival_time"))
    return row


def _normalize_booking_row(row: dict | None):
    if not row:
        return row
    row["travel_date"] = _coerce_date(row.get("travel_date"))
    row["departure_time"] = _coerce_time(row.get("departure_time"))
    row["arrival_time"] = _coerce_time(row.get("arrival_time"))
    fare_amount = row.get("fare_amount")
    if fare_amount is not None:
        row["fare_amount"] = float(_to_decimal(fare_amount))
    for numeric_key in ("base_fare", "fare_multiplier"):
        if numeric_key in row and row[numeric_key] is not None:
            row[numeric_key] = float(_to_decimal(row[numeric_key]))
    return row


def _fetch_all(query: str, params: tuple | list | None = None):
    params = params or tuple()
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()
            return rows
    except Error as exc:
        raise DatabaseError(str(exc)) from exc


def _fetch_one(query: str, params: tuple | list | None = None):
    params = params or tuple()
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params)
            row = cursor.fetchone()
            cursor.close()
            return row
    except Error as exc:
        raise DatabaseError(str(exc)) from exc


def fetch_stations():
    return _fetch_all(
        """
        SELECT id AS station_id, name AS station_name
        FROM station
        ORDER BY station_name
        """
    )


def fetch_coach_types():
    rows = _fetch_all(
        """
    SELECT id, code, name, base_fare, fare_multiplier, description
    FROM coachtype
        ORDER BY base_fare
        """
    )
    result = []
    for row in rows:
        fare_decimal = _compute_fare_amount(row["base_fare"], row["fare_multiplier"])
        row["fare_amount"] = fare_decimal
        row["fare_display"] = format(fare_decimal, ".2f")
        result.append(row)
    return result


def get_coach_type(coach_type_id: int):
    row = _fetch_one(
        """
    SELECT id, code, name, base_fare, fare_multiplier, description
    FROM coachtype
        WHERE id = %s
        """,
        (coach_type_id,),
    )
    if row:
        fare_decimal = _compute_fare_amount(row["base_fare"], row["fare_multiplier"])
        row["fare_amount"] = fare_decimal
        row["fare_display"] = format(fare_decimal, ".2f")
    return row


def search_schedules(source_id: int, destination_id: int, travel_date: date):
    rows = _fetch_all(
        """
        SELECT
            s.id AS schedule_id,
            s.travel_date,
            s.departure_time,
            s.arrival_time,
            s.available_seats,
            t.name AS train_name,
            t.number AS train_number,
            src.name AS source_name,
            dest.name AS destination_name
        FROM schedule s
        JOIN train t ON s.train_id = t.id
        JOIN station src ON s.source_station_id = src.id
        JOIN station dest ON s.destination_station_id = dest.id
        WHERE s.source_station_id = %s
          AND s.destination_station_id = %s
          AND s.travel_date = %s
        ORDER BY s.departure_time
        """,
        (source_id, destination_id, travel_date),
    )
    return [_normalize_schedule_row(row) for row in rows]


def get_schedule(schedule_id: int):
    row = _fetch_one(
        """
        SELECT
            s.id AS schedule_id,
            s.travel_date,
            s.departure_time,
            s.arrival_time,
            s.available_seats,
            t.name AS train_name,
            t.number AS train_number,
            src.name AS source_name,
            dest.name AS destination_name
        FROM schedule s
        JOIN train t ON s.train_id = t.id
        JOIN station src ON s.source_station_id = src.id
        JOIN station dest ON s.destination_station_id = dest.id
        WHERE s.id = %s
        """,
        (schedule_id,),
    )
    return _normalize_schedule_row(row)


def get_booking_overview(booking_id: int):
    row = _fetch_one(
        """
        SELECT
            b.id AS booking_id,
            b.status,
            b.passenger_name,
            b.email,
            b.seat_number,
            b.fare_amount,
            ct.id AS coach_type_id,
            ct.code AS coach_code,
            ct.name AS coach_name,
            ct.description AS coach_description,
            ct.base_fare,
            ct.fare_multiplier,
            tk.pnr,
            s.travel_date,
            s.departure_time,
            s.arrival_time,
            t.name AS train_name,
            t.number AS train_number,
            src.name AS source_name,
            dest.name AS destination_name
        FROM booking b
        JOIN ticket tk ON tk.booking_id = b.id
        JOIN schedule s ON b.schedule_id = s.id
        JOIN train t ON s.train_id = t.id
    JOIN coachtype ct ON b.coach_type_id = ct.id
        JOIN station src ON s.source_station_id = src.id
        JOIN station dest ON s.destination_station_id = dest.id
        WHERE b.id = %s
        """,
        (booking_id,),
    )
    return _normalize_booking_row(row)


def get_ticket(pnr: str):
    row = _fetch_one(
        """
        SELECT
            tk.pnr,
            tk.issued_at,
            b.id AS booking_id,
            b.status AS booking_status,
            b.passenger_name,
            b.email,
            b.seat_number,
            b.fare_amount,
            ct.code AS coach_code,
            ct.name AS coach_name,
            ct.description AS coach_description,
            ct.base_fare,
            ct.fare_multiplier,
            s.travel_date,
            s.departure_time,
            s.arrival_time,
            t.name AS train_name,
            t.number AS train_number,
            src.name AS source_name,
            dest.name AS destination_name
        FROM ticket tk
        JOIN booking b ON tk.booking_id = b.id
        JOIN schedule s ON b.schedule_id = s.id
        JOIN train t ON s.train_id = t.id
    JOIN coachtype ct ON b.coach_type_id = ct.id
        JOIN station src ON s.source_station_id = src.id
        JOIN station dest ON s.destination_station_id = dest.id
        WHERE tk.pnr = %s
        """,
        (pnr,),
    )
    return _normalize_booking_row(row)


def create_booking(schedule_id: int, coach_type_id: int, passenger_name: str, email: str, fare_amount: Decimal):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, available_seats FROM schedule WHERE id = %s FOR UPDATE",
            (schedule_id,),
        )
        schedule = cursor.fetchone()
        if not schedule:
            raise DomainError("Schedule not found")
        if schedule["available_seats"] <= 0:
            raise DomainError("No seats left for this schedule")

        seat_number = f"S{schedule['available_seats']:03d}"

        cursor.execute(
            """
            UPDATE schedule
            SET available_seats = available_seats - 1
            WHERE id = %s
            """,
            (schedule_id,),
        )

        cursor.execute(
            """
            INSERT INTO booking (schedule_id, coach_type_id, passenger_name, email, status, seat_number, fare_amount)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (schedule_id, coach_type_id, passenger_name, email, "PENDING", seat_number, fare_amount),
        )
        booking_id = cursor.lastrowid
        pnr = _generate_pnr(booking_id)

        cursor.execute(
            "INSERT INTO ticket (booking_id, pnr) VALUES (%s, %s)",
            (booking_id, pnr),
        )

        conn.commit()
        return booking_id, pnr, seat_number
    except DomainError:
        if conn:
            conn.rollback()
        raise
    except Error as exc:
        if conn:
            conn.rollback()
        raise DatabaseError(str(exc)) from exc
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def _restore_seat_allocation(cursor, booking_id: int):
    cursor.execute(
        """
        UPDATE schedule s
        JOIN booking b ON b.schedule_id = s.id
        SET s.available_seats = s.available_seats + 1
        WHERE b.id = %s
        """,
        (booking_id,),
    )


def record_payment(booking_id: int, success: bool, method: str = "CARD", amount: float | Decimal = 100.0):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        booking_status = "CONFIRMED" if success else "FAILED"
        payment_status = "SUCCESS" if success else "FAILED"
        amount_value = _to_decimal(amount)

        cursor.execute(
            "UPDATE booking SET status = %s WHERE id = %s",
            (booking_status, booking_id),
        )
        cursor.execute(
            """
            INSERT INTO payment (booking_id, amount, status, method)
            VALUES (%s, %s, %s, %s)
            """,
            (booking_id, amount_value, payment_status, method),
        )

        if not success:
            _restore_seat_allocation(cursor, booking_id)

        conn.commit()
        return booking_status
    except Error as exc:
        if conn:
            conn.rollback()
        raise DatabaseError(str(exc)) from exc
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    try:
        stations = fetch_stations()
    except DatabaseError as exc:
        return render_template("index.html", stations=[], error=str(exc)), 500

    return render_template("index.html", stations=stations, error=None)


@app.route("/search", methods=["POST"])
def search():
    source_id = request.form.get("source")
    destination_id = request.form.get("destination")
    travel_date_raw = request.form.get("date")

    if not (source_id and destination_id and travel_date_raw):
        abort(400, description="Source, destination, and travel date are required.")

    try:
        travel_date = datetime.strptime(travel_date_raw, "%Y-%m-%d").date()
    except ValueError:
        abort(400, description="Invalid travel date format.")

    try:
        schedules = search_schedules(int(source_id), int(destination_id), travel_date)
        stations = fetch_stations()
        coach_types = fetch_coach_types()
    except DatabaseError as exc:
        return render_template(
            "results.html",
            schedules=[],
            search_date=travel_date,
            source_id=source_id,
            destination_id=destination_id,
            stations=[],
            coach_types=[],
            error=str(exc),
        ), 500

    min_fare = None
    if coach_types:
        min_fare = min(_to_decimal(ct["fare_amount"]) for ct in coach_types)

    return render_template(
        "results.html",
        schedules=schedules,
        search_date=travel_date,
        source_id=int(source_id),
        destination_id=int(destination_id),
        stations=stations,
        coach_types=coach_types,
        min_fare=min_fare,
        error=None,
    )


@app.route("/book/<int:schedule_id>", methods=["GET", "POST"])
def book(schedule_id: int):
    try:
        sched = get_schedule(schedule_id)
    except DatabaseError as exc:
        return render_template("booking.html", sched=None, error=str(exc)), 500

    if not sched:
        abort(404, description="Schedule not found")

    try:
        coach_types = fetch_coach_types()
    except DatabaseError as exc:
        return render_template("booking.html", sched=sched, error=str(exc), coach_types=[]), 500

    if request.method == "POST":
        passenger_name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip() or None
        coach_type_raw = request.form.get("coach_type")

        if not passenger_name:
            return render_template(
                "booking.html",
                sched=sched,
                coach_types=coach_types,
                error="Passenger name is required.",
                selected_coach_id=coach_type_raw,
            ), 400

        if not coach_type_raw:
            return render_template(
                "booking.html",
                sched=sched,
                coach_types=coach_types,
                error="Please choose a coach type.",
                selected_coach_id=coach_type_raw,
            ), 400

        try:
            coach_type_id = int(coach_type_raw)
        except ValueError:
            return render_template(
                "booking.html",
                sched=sched,
                coach_types=coach_types,
                error="Invalid coach selection.",
                selected_coach_id=coach_type_raw,
            ), 400

        coach = get_coach_type(coach_type_id)
        if not coach:
            return render_template(
                "booking.html",
                sched=sched,
                coach_types=coach_types,
                error="Selected coach type is unavailable.",
                selected_coach_id=coach_type_raw,
            ), 404

        fare_amount = coach["fare_amount"]

        try:
            booking_id, pnr, seat_number = create_booking(
                schedule_id,
                coach["id"],
                passenger_name,
                email,
                fare_amount,
            )
        except DomainError as exc:
            return render_template(
                "booking.html",
                sched=sched,
                coach_types=coach_types,
                error=str(exc),
                selected_coach_id=coach_type_id,
            ), 409
        except DatabaseError as exc:
            return render_template(
                "booking.html",
                sched=sched,
                coach_types=coach_types,
                error=str(exc),
                selected_coach_id=coach_type_id,
            ), 500

        return redirect(url_for("payment_page", booking_id=booking_id, pnr=pnr))

    return render_template("booking.html", sched=sched, coach_types=coach_types, error=None)


@app.route("/payment")
def payment_page():
    booking_id = request.args.get("booking_id")
    pnr = request.args.get("pnr")

    if not (booking_id and pnr):
        abort(400, description="Missing booking details")

    try:
        booking = get_booking_overview(int(booking_id))
    except DatabaseError as exc:
        return render_template("payment.html", booking=None, error=str(exc)), 500

    if not booking or booking.get("pnr") != pnr:
        abort(404, description="Booking not found")

    return render_template("payment.html", booking=booking, error=None)


@app.route("/pay", methods=["POST"])
def pay():
    booking_id_raw = request.form.get("booking_id")
    pnr = request.form.get("pnr")
    card = request.form.get("card", "").strip()

    if not (booking_id_raw and pnr and card):
        abort(400, description="Missing payment data")

    try:
        booking_id = int(booking_id_raw)
    except ValueError:
        abort(400, description="Invalid booking identifier")

    try:
        booking = get_booking_overview(booking_id)
    except DatabaseError as exc:
        return render_template("payment.html", booking=None, error=str(exc)), 500

    if not booking or booking.get("pnr") != pnr:
        abort(404, description="Booking not found")

    success = True
    try:
        if int(card[-1]) % 2 == 1:
            success = False
    except (ValueError, IndexError):
        success = False

    try:
        status = record_payment(booking_id, success, amount=booking["fare_amount"])
    except DatabaseError as exc:
        return render_template("payment.html", booking=booking, error=str(exc)), 500

    if status == "CONFIRMED":
        return redirect(url_for("ticket_view", pnr=pnr))

    booking["status"] = status
    return render_template(
        "payment.html",
        booking=booking,
        error="Payment failed. Try another card number ending with an even digit.",
    ), 402


@app.route("/ticket/<pnr>")
def ticket_view(pnr: str):
    try:
        ticket = get_ticket(pnr)
    except DatabaseError as exc:
        return render_template("ticket.html", ticket=None, error=str(exc)), 500

    if not ticket:
        abort(404, description="Ticket not found")

    return render_template("ticket.html", ticket=ticket, error=None)


if __name__ == "__main__":
    app.run(debug=True, port=4000)