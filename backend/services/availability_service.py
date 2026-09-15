# backend/services/availability_service.py
"""
Generates real, bookable appointment slots and checks them against
existing bookings in the database — so the booking flow only ever
offers dates/times that are actually open, and two patients can't be
booked into the same doctor/date/time slot.

Working hours are a simple default applied to every doctor (Mon-Fri
9am-5pm, Saturday half-day, Sunday closed). If different doctors need
different schedules later, this is the one place to extend — e.g. by
reading per-doctor hours out of hospital_data.py instead of the flat
WORKING_HOURS table below.
"""
from datetime import datetime, timedelta

import database

# weekday(): Monday=0 ... Sunday=6
WORKING_HOURS = {
    0: ("09:00", "17:00"),
    1: ("09:00", "17:00"),
    2: ("09:00", "17:00"),
    3: ("09:00", "17:00"),
    4: ("09:00", "17:00"),
    5: ("09:00", "13:00"),
    6: None,
}

SLOT_MINUTES = 60
DAYS_AHEAD = 14


def _time_slots_for_weekday(weekday: int):
    hours = WORKING_HOURS.get(weekday)
    if not hours:
        return []
    start = datetime.strptime(hours[0], "%H:%M")
    end = datetime.strptime(hours[1], "%H:%M")
    slots = []
    current = start
    while current < end:
        slots.append(current.strftime("%I:%M %p").lstrip("0"))
        current += timedelta(minutes=SLOT_MINUTES)
    return slots


def get_available_dates(doctor_name: str, limit: int = 7):
    """Next `limit` upcoming dates with at least one open slot, as
    [{"value": "2026-09-16", "label": "Mon, Sep 16"}, ...]."""
    results = []
    today = datetime.now().date()
    offset = 0
    while len(results) < limit and offset < DAYS_AHEAD:
        day = today + timedelta(days=offset)
        offset += 1
        all_slots = _time_slots_for_weekday(day.weekday())
        if not all_slots:
            continue
        booked = database.get_booked_times(doctor_name, day.isoformat())
        if len(booked) < len(all_slots):
            results.append({"value": day.isoformat(), "label": day.strftime("%a, %b %d")})
    return results


def get_available_times(doctor_name: str, date_value: str):
    """Open time slots for a specific ISO date (YYYY-MM-DD)."""
    try:
        day = datetime.strptime(date_value, "%Y-%m-%d").date()
    except ValueError:
        return []
    all_slots = _time_slots_for_weekday(day.weekday())
    booked = set(database.get_booked_times(doctor_name, date_value))
    return [t for t in all_slots if t not in booked]


def is_slot_available(doctor_name: str, date_value: str, time_value: str) -> bool:
    return time_value in get_available_times(doctor_name, date_value)


def format_date_label(date_value: str) -> str:
    """ISO date -> friendly display string, e.g. 'Wed, Sep 16, 2026'."""
    try:
        return datetime.strptime(date_value, "%Y-%m-%d").strftime("%a, %b %d, %Y")
    except ValueError:
        return date_value
