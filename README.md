# Railway – Train Ticket Booking System

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
