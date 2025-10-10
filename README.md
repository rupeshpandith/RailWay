# Railway 2.0 – Train Ticket Booking System

A Flask-based web application for searching trains, booking seats, simulating payments, and generating e-tickets.

## Features

- Search trains by source, destination, and date
- View available schedules with seat availability
- Capture passenger details and reserve seats
- Simulate card payments (even last digit → success)
- Generate printable e-ticket with PNR and journey summary
- MySQL-backed with schema/seed helper (`init_db.py`)

## Prerequisites

- Python 3.11+ (tested on 3.12)
- MySQL 8+ server
- PowerShell (for the commands below on Windows)

## Setup

1. **Clone the project** and open the folder in VS Code.
2. **Create and activate a virtual environment (optional but recommended):**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```
4. **Configure environment variables:**
   - Copy `.env.example` to `.env` and update the MySQL credentials and database name.
   - Create the database specified in `DB_NAME` if it does not exist:
     ```sql
     CREATE DATABASE railway_app CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
     ```
5. **Provision schema & seed sample data:**
   ```powershell
   python init_db.py
   ```
   The script is idempotent—tables are created if missing and sample rows are inserted only when empty.

## Running the app

```powershell
python app.py
```

Then open <http://127.0.0.1:4000> in your browser. Use the landing form to search for trains, proceed through booking, simulate payment, and view the generated ticket.

## Project structure

```
app.py            # Flask application routes and business logic
init_db.py        # Database schema + sample seed helper
requirements.txt  # Python dependencies
static/           # CSS/JS assets
templates/        # Jinja2 templates for pages
```

## Testing & troubleshooting

- If you see database errors, verify `.env` values and that MySQL is running.
- Re-run `python init_db.py` anytime to ensure schema consistency or reseed demo data.
- Logs appear in the terminal where the Flask app is running.

## Next steps

- Add authentication for user accounts
- Integrate real payment gateway instead of simulation
- Extend schedule management for admins
