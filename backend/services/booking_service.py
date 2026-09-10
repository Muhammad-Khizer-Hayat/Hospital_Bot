# backend/services/booking_service.py
"""
A small state machine that walks a caller through booking an appointment
across several turns — department, doctor, date, time, patient name and
phone — then saves the booking. This is what lets the assistant act like
a real front-desk agent instead of just answering one question at a time.

Sessions are kept in memory, keyed by session_id (one per browser tab /
call). This is fine for a single-process dev server; if you deploy with
multiple worker processes, move _sessions to Redis or a database instead,
or in-progress bookings will randomly "forget" mid-conversation depending
on which worker handles the next request.
"""
import json
import os
import uuid
from datetime import datetime, timezone

from config import Config
import hospital_data

APPOINTMENTS_FILE = os.path.join(os.path.dirname(Config.DOCTORS_DATA_FILE), "appointments.json")

BOOKING_TRIGGERS = [
    "book an appointment", "book appointment", "schedule an appointment",
    "schedule appointment", "make an appointment", "i want an appointment",
    "need an appointment", "book a doctor", "i want to book",
    "set up an appointment", "get an appointment",
]

CANCEL_WORDS = {"cancel", "stop", "never mind", "nevermind", "quit", "exit"}
YES_WORDS = {"yes", "yeah", "yep", "correct", "confirm", "sure", "ok", "okay", "right"}
NO_WORDS = {"no", "nope", "incorrect", "wrong"}

_sessions = {}  # session_id -> {"step": str, "data": dict}


def is_booking_trigger(message: str) -> bool:
    low = message.lower()
    return any(t in low for t in BOOKING_TRIGGERS)


def is_booking_active(session_id: str) -> bool:
    return session_id in _sessions


def cancel_booking(session_id: str):
    _sessions.pop(session_id, None)


def _find_department(text):
    text = text.strip().lower()
    for dept in hospital_data.get_all_departments():
        if dept.lower() == text or dept.lower() in text:
            return dept
    return None


def _find_doctor(text, doctors):
    text = text.strip().lower()
    for doc in doctors:
        name = doc["name"].lower().replace("dr.", "").strip()
        if name in text or text in name or any(part in text for part in name.split() if len(part) > 2):
            return doc
    return None


def start_booking(session_id: str) -> str:
    _sessions[session_id] = {"step": "department", "data": {}}
    depts = ", ".join(hospital_data.get_all_departments())
    return f"Sure, I can help you book an appointment. Which department would you like — {depts}?"


def handle_booking_turn(session_id: str, message: str) -> str:
    session = _sessions.get(session_id)
    if not session:
        return start_booking(session_id)

    text = message.strip()
    low = text.lower()

    if low in CANCEL_WORDS:
        cancel_booking(session_id)
        return "No problem, I've cancelled that. Let me know if you'd like to book later."

    step = session["step"]
    data = session["data"]

    if step == "department":
        dept = _find_department(text)
        if not dept:
            depts = ", ".join(hospital_data.get_all_departments())
            return f"I don't have a department called \"{text}\". Please choose one of: {depts}."
        doctors = hospital_data.get_doctors_by_department(dept)
        if not doctors:
            return f"There are no doctors currently listed under {dept}. Would you like to try a different department?"
        data["department"] = dept
        session["step"] = "doctor"
        names = ", ".join(d["name"] for d in doctors)
        return f"Great — which doctor in {dept} would you like to see? Options: {names}."

    if step == "doctor":
        doctors = hospital_data.get_doctors_by_department(data["department"])
        match = _find_doctor(text, doctors)
        if not match:
            names = ", ".join(d["name"] for d in doctors)
            return f"I couldn't match that to a doctor in {data['department']}. Please pick one of: {names}."
        data["doctor"] = match["name"]
        session["step"] = "date"
        return f"Got it, {match['name']}. What date works for you? (e.g. \"tomorrow\" or \"12 October\")"

    if step == "date":
        if not text:
            return "Sorry, what date would you like to come in?"
        data["date"] = text
        session["step"] = "time"
        return "And what time would you prefer?"

    if step == "time":
        if not text:
            return "What time works best for you?"
        data["time"] = text
        session["step"] = "patient_name"
        return "Can I get the patient's full name for the booking?"

    if step == "patient_name":
        if not text:
            return "Sorry, what's the patient's name?"
        data["patient_name"] = text
        session["step"] = "patient_phone"
        return "And a contact phone number, in case we need to reach you?"

    if step == "patient_phone":
        if not text:
            return "What's the best contact number for this booking?"
        data["patient_phone"] = text
        session["step"] = "confirm"
        return (
            f"Let me confirm — {data['patient_name']}, with {data['doctor']} "
            f"({data['department']}), on {data['date']} at {data['time']}, "
            f"contact number {data['patient_phone']}. Shall I book this?"
        )

    if step == "confirm":
        if low in YES_WORDS or any(w in low for w in YES_WORDS):
            appointment_id = _save_appointment(data)
            cancel_booking(session_id)
            return (
                f"You're all set. Your appointment is confirmed — reference {appointment_id}. "
                f"We'll see {data['patient_name']} on {data['date']} at {data['time']} "
                f"with {data['doctor']}."
            )
        if low in NO_WORDS or any(w in low for w in NO_WORDS):
            cancel_booking(session_id)
            return "No problem, I've cancelled that booking. Would you like to start over?"
        return "Sorry, just to confirm — should I go ahead and book this? (yes/no)"

    cancel_booking(session_id)
    return "Something went off track there — let's start over. Would you like to book an appointment?"


def _save_appointment(data: dict) -> str:
    os.makedirs(os.path.dirname(APPOINTMENTS_FILE), exist_ok=True)
    appointments = []
    if os.path.exists(APPOINTMENTS_FILE):
        try:
            with open(APPOINTMENTS_FILE, "r", encoding="utf-8") as f:
                appointments = json.load(f)
        except (json.JSONDecodeError, OSError):
            appointments = []

    appointment_id = uuid.uuid4().hex[:8].upper()
    record = {
        "id": appointment_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **data,
    }
    appointments.append(record)

    with open(APPOINTMENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(appointments, f, indent=2)

    return appointment_id


def get_all_appointments():
    if not os.path.exists(APPOINTMENTS_FILE):
        return []
    try:
        with open(APPOINTMENTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
