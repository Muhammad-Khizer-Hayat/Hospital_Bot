# backend/services/appointment_service.py
"""
A deterministic, step-by-step booking flow — the agent asks one thing
at a time and won't move on until it gets a usable answer. This is on
purpose: letting the LLM freely improvise a multi-turn booking (name,
department, date, time, phone) is exactly where models drop or
invent details. A plain state machine can't do that.

Session state is kept in memory, keyed by a session_id the frontend
generates once and sends with every request. This is fine for a
single-server demo/prototype; move it to Redis or a DB table before
running multiple server processes or workers.
"""
import json
import os
import re
import uuid
from datetime import datetime

import dateparser

import hospital_data
from config import Config

APPOINTMENTS_FILE = os.path.join(os.path.dirname(Config.DOCTORS_DATA_FILE), "appointments.json")

STEPS = ["department", "doctor", "date", "time", "name", "phone", "confirm"]

BOOKING_TRIGGERS = {
    "book", "booking", "appointment", "schedule", "reserve",
}

CANCEL_WORDS = {"cancel", "nevermind", "stop", "never mind", "exit"}

_sessions = {}


def _tokens(text):
    return re.findall(r"[a-zA-Z]+", text.lower())


def wants_to_book(message: str) -> bool:
    tokens = set(_tokens(message))
    return bool(tokens & BOOKING_TRIGGERS)


def wants_to_cancel(message: str) -> bool:
    return message.strip().lower() in CANCEL_WORDS


def is_booking_in_progress(session_id: str) -> bool:
    return session_id in _sessions


def _new_state():
    return {"step": "department", "data": {}}


def start_booking(session_id: str) -> str:
    _sessions[session_id] = _new_state()
    dept_list = ", ".join(hospital_data.get_all_departments())
    return (
        "Sure — let's get you booked in. Which department would you like "
        f"to see a doctor in? We have: {dept_list}."
    )


def _cancel(session_id: str) -> str:
    _sessions.pop(session_id, None)
    return "No problem, I've cancelled that booking. Let me know if you'd like to start again."


def _match_department(text: str):
    dept_lookup = {d.lower(): d for d in hospital_data.get_all_departments()}
    tokens = _tokens(text)
    for token in tokens:
        if token in dept_lookup:
            return dept_lookup[token]
    import difflib
    for token in tokens:
        close = difflib.get_close_matches(token, list(dept_lookup.keys()), n=1, cutoff=0.78)
        if close:
            return dept_lookup[close[0]]
    return None


def _match_doctor(text: str, doctor_pool):
    tokens = _tokens(text)
    for doc in doctor_pool:
        name_tokens = [t for t in _tokens(doc["name"]) if t != "dr"]
        for token in tokens:
            if len(token) > 2 and token in name_tokens:
                return doc
    return None


def _format_date(text: str):
    parsed = dateparser.parse(text, settings={"PREFER_DATES_FROM": "future"})
    if parsed:
        return parsed.strftime("%A, %B %d, %Y"), True
    return text.strip(), False


def _phone_looks_valid(text: str):
    digits = re.sub(r"\D", "", text)
    return 7 <= len(digits) <= 15


def _summary(data: dict) -> str:
    lines = [
        f"- Department: {data.get('department')}",
        f"- Doctor: {data.get('doctor_name', 'Any available doctor')}",
        f"- Date: {data.get('date')}",
        f"- Time: {data.get('time')}",
        f"- Name: {data.get('name')}",
        f"- Phone: {data.get('phone')}",
    ]
    return "Here's what I've got:\n\n" + "\n".join(lines) + "\n\nShall I confirm this appointment? (yes/no)"


def _save_appointment(data: dict):
    os.makedirs(os.path.dirname(APPOINTMENTS_FILE), exist_ok=True)
    existing = []
    if os.path.exists(APPOINTMENTS_FILE):
        try:
            with open(APPOINTMENTS_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = []
    record = dict(data)
    record["id"] = str(uuid.uuid4())[:8]
    record["booked_at"] = datetime.now().isoformat(timespec="seconds")
    existing.append(record)
    with open(APPOINTMENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)
    return record


def handle_booking_reply(session_id: str, message: str) -> str:
    if wants_to_cancel(message):
        return _cancel(session_id)

    state = _sessions.get(session_id)
    if state is None:
        return start_booking(session_id)

    step = state["step"]
    data = state["data"]

    if step == "department":
        dept = _match_department(message)
        if not dept:
            dept_list = ", ".join(hospital_data.get_all_departments())
            return f"Sorry, I didn't catch a valid department. We have: {dept_list}. Which one?"
        data["department"] = dept
        doctor_pool = hospital_data.get_doctors_by_department(dept)
        if not doctor_pool:
            data["doctor_name"] = None
            state["step"] = "date"
            return f"Got it, {dept}. What date would you like to come in?"
        if len(doctor_pool) == 1:
            data["doctor_name"] = doctor_pool[0]["name"]
            state["step"] = "date"
            return f"Got it — {dept}, you'll see {doctor_pool[0]['name']}. What date would you like to come in?"
        names = ", ".join(d["name"] for d in doctor_pool)
        state["step"] = "doctor"
        state["_doctor_pool"] = doctor_pool
        return f"Which doctor would you prefer? Options: {names}."

    if step == "doctor":
        doctor_pool = state.get("_doctor_pool", hospital_data.get_doctors_by_department(data.get("department", "")))
        doc = _match_doctor(message, doctor_pool)
        if not doc:
            names = ", ".join(d["name"] for d in doctor_pool)
            return f"Sorry, I didn't catch that. Please choose one of: {names}."
        data["doctor_name"] = doc["name"]
        state["step"] = "date"
        return f"Great, {doc['name']} it is. What date would you like to come in?"

    if step == "date":
        formatted, understood = _format_date(message)
        data["date"] = formatted
        state["step"] = "time"
        prefix = "Got it" if understood else "Okay, noted"
        return f"{prefix}. What time works for you?"

    if step == "time":
        data["time"] = message.strip()
        state["step"] = "name"
        return "And who is this appointment for? Please give me the patient's full name."

    if step == "name":
        if len(message.strip()) < 2:
            return "Sorry, could you give me the full name for the appointment?"
        data["name"] = message.strip()
        state["step"] = "phone"
        return "What's the best contact phone number to reach you on?"

    if step == "phone":
        if not _phone_looks_valid(message):
            return "That doesn't look like a valid phone number — could you say it again?"
        data["phone"] = message.strip()
        state["step"] = "confirm"
        return _summary(data)

    if step == "confirm":
        reply = message.strip().lower()
        if reply in {"yes", "y", "confirm", "yeah", "yep", "correct"}:
            record = _save_appointment(data)
            _sessions.pop(session_id, None)
            return (
                f"You're all set! Appointment confirmed for {record['name']} with "
                f"{record.get('doctor_name') or 'an available doctor'} ({record['department']}) "
                f"on {record['date']} at {record['time']}. "
                f"Your reference number is {record['id']}."
            )
        if reply in {"no", "n", "nope"}:
            return _cancel(session_id)
        return "Sorry, just to confirm — should I book this? (yes/no)"

    # Shouldn't get here, but fail safe rather than crash the conversation
    _sessions.pop(session_id, None)
    return "Something went wrong with that booking — let's start over. Would you like to book an appointment?"
