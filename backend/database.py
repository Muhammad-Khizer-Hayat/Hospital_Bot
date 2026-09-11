# backend/database.py
"""
SQLite database for storing appointment bookings.

Why SQLite: the whole database lives in one file — no separate
database server to install or run, and Python's sqlite3 module is
built in (no extra dependency). Good fit for a single-server
deployment; swap for Postgres/MySQL later if you outgrow it or need
multiple app servers writing at once.

The file lives at backend/data/hospital.db — open it directly with
any SQLite viewer (e.g. "DB Browser for SQLite", a free GUI app) to
see booked appointments, or query it with the functions below.
"""
import os
import sqlite3
from contextlib import contextmanager

from config import Config

DB_FILE = os.path.join(os.path.dirname(Config.DOCTORS_DATA_FILE), "hospital.db")


def _ensure_dir():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)


@contextmanager
def get_connection():
    _ensure_dir()
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Creates the appointments table if it doesn't exist yet. Safe to
    call every time the app starts."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id TEXT PRIMARY KEY,
                patient_name TEXT NOT NULL,
                country TEXT,
                phone TEXT,
                department TEXT NOT NULL,
                doctor_name TEXT,
                appointment_date TEXT,
                appointment_time TEXT,
                booked_at TEXT NOT NULL
            )
        """)


def insert_appointment(record: dict) -> dict:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO appointments
                (id, patient_name, country, phone, department, doctor_name,
                 appointment_date, appointment_time, booked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["name"],
                record.get("country"),
                record.get("phone"),
                record["department"],
                record.get("doctor_name"),
                record.get("date"),
                record.get("time"),
                record["booked_at"],
            ),
        )
    return record


def get_all_appointments() -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM appointments ORDER BY booked_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]
