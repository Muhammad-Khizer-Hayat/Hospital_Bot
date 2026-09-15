# backend/services/appointment_service.py
"""
A deterministic, step-by-step booking flow — the agent asks one thing
at a time and won't move on until it gets a usable answer. This is on
purpose: letting the LLM freely improvise a multi-turn booking is
exactly where models drop or invent details. A plain state machine
can't do that.

Flow order: name -> country -> department -> doctor -> date -> time
-> phone -> confirm. Date/time are real, bookable slots pulled from
availability_service (which checks the database, so an already-taken
slot is never offered twice).

Every step that has a fixed set of valid answers (department, doctor,
date, time, yes/no confirm) also returns a "choices" list alongside
the message — the frontend renders these as clickable buttons, but
free-text/spoken replies are still matched too, so voice mode keeps
working exactly the same way.

Session state is kept in memory, keyed by a session_id the frontend
generates once and sends with every request. This is fine for a
single-server demo/prototype; move it to Redis or a DB table before
running multiple server processes or workers — the appointments
themselves are safely persisted to SQLite (see database.py) as soon
as they're confirmed, only the in-progress conversation state lives
in memory.
"""
import difflib
import re
import uuid
from datetime import datetime

import dateparser

import database
import hospital_data
from services import availability_service

BOOKING_TRIGGERS = {
    "book", "booking", "appointment", "schedule", "reserve",
}

CANCEL_WORDS = {"cancel", "nevermind", "stop", "never mind", "exit"}
QUESTION_STARTERS = {
    "can", "does", "do", "how", "is", "are", "when", "where", "what", "which", "why",
}
NEW_TOPIC_WORDS = {
    "billing", "insurance", "parking", "pharmacy", "symptom", "symptoms", "stroke", "heart",
    "visiting", "hours", "emergency", "services", "department", "departments",
}

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


def abandon_booking(session_id: str):
    """Drop an unfinished flow when the user starts a different topic."""
    _sessions.pop(session_id, None)


def is_new_topic(message: str) -> bool:
    """Identify common standalone questions that should escape booking mode."""
    tokens = set(_tokens(message))
    if _match_department(message):
        return False
    return bool(tokens & QUESTION_STARTERS or tokens & NEW_TOPIC_WORDS)


def _reply(message: str, choices=None):
    return {"message": message, "choices": choices or []}


def _new_state():
    return {"step": "name", "data": {}}


def start_booking(session_id: str) -> dict:
    _sessions[session_id] = _new_state()
    return _reply("Sure — let's get you booked in. Can I get your full name, please?")


def _cancel(session_id: str) -> dict:
    _sessions.pop(session_id, None)
    return _reply("No problem, I've cancelled that booking. Let me know if you'd like to start again.")


def _match_department(text: str):
    dept_lookup = {d.lower(): d for d in hospital_data.get_all_departments()}
    tokens = _tokens(text)
    for token in tokens:
        if token in dept_lookup:
            return dept_lookup[token]
    for token in tokens:
        close = difflib.get_close_matches(token, list(dept_lookup.keys()), n=1, cutoff=0.78)
        if close:
            return dept_lookup[close[0]]
    return None


def _department_choices():
    return [{"label": d, "value": d} for d in hospital_data.get_all_departments()]


def _match_doctor(text: str, doctor_pool):
    tokens = _tokens(text)
    for doc in doctor_pool:
        name_tokens = [t for t in _tokens(doc["name"]) if t != "dr"]
        for token in tokens:
            if len(token) > 2 and token in name_tokens:
                return doc
    return None


def _doctor_choices(doctor_pool):
    return [{"label": d["name"], "value": d["name"]} for d in doctor_pool]


def _match_date_choice(message: str, available_dates: list):
    msg = message.strip().lower()
    for d in available_dates:
        if msg == d["value"] or msg == d["label"].lower():
            return d["value"]
    # Free-text/spoken fallback ("tomorrow", "next monday", "16 sep")
    parsed = dateparser.parse(message, settings={"PREFER_DATES_FROM": "future"})
    if parsed:
        iso = parsed.date().isoformat()
        if any(d["value"] == iso for d in available_dates):
            return iso
    return None


def _normalize_time(text: str):
    return re.sub(r"[\s.]", "", text.strip().lower())


def _match_time_choice(message: str, available_times: list, date_value: str):
    normalized_msg = _normalize_time(message)
    for t in available_times:
        if normalized_msg == _normalize_time(t):
            return t
    # Free-text/spoken fallback ("9am", "2 o'clock", "14:00")
    parsed = dateparser.parse(f"{date_value} {message}")
    if parsed:
        formatted = parsed.strftime("%I:%M %p").lstrip("0")
        for t in available_times:
            if _normalize_time(t) == _normalize_time(formatted):
                return t
    return None


def _phone_looks_valid(text: str):
    digits = re.sub(r"\D", "", text)
    return 7 <= len(digits) <= 15


def _country_looks_valid(text: str):
    letters = re.sub(r"[^a-zA-Z]", "", text)
    return len(letters) >= 2


def _summary(data: dict) -> str:
    date_label = availability_service.format_date_label(data.get("date", ""))
    lines = [
        f"- Name: {data.get('name')}",
        f"- Country: {data.get('country')}",
        f"- Department: {data.get('department')}",
        f"- Doctor: {data.get('doctor_name', 'Any available doctor')}",
        f"- Date: {date_label}",
        f"- Time: {data.get('time')}",
        f"- Phone: {data.get('phone')}",
    ]
    return "Here's what I've got:\n\n" + "\n".join(lines) + "\n\nShall I confirm this appointment?"


def _save_appointment(data: dict) -> dict:
    record = dict(data)
    record["id"] = str(uuid.uuid4())[:8]
    record["booked_at"] = datetime.now().isoformat(timespec="seconds")
    return database.insert_appointment(record)


def _ask_for_date(data: dict) -> dict:
    available_dates = availability_service.get_available_dates(data.get("doctor_name"))
    if not available_dates:
        return _reply(
            "I'm sorry, there are no open slots in the next two weeks for that doctor. "
            "Please call the hospital directly to arrange a time, or say 'cancel' to stop."
        )
    return _reply("Which date works for you?", choices=available_dates)


def _ask_for_time(data: dict) -> dict:
    available_times = availability_service.get_available_times(data.get("doctor_name"), data["date"])
    if not available_times:
        # Slot filled up between choosing the date and now — bounce back to date step.
        return _ask_for_date(data)
    return _reply("What time works for you?", choices=[{"label": t, "value": t} for t in available_times])


def handle_booking_reply(session_id: str, message: str) -> dict:
    if wants_to_cancel(message):
        return _cancel(session_id)

    state = _sessions.get(session_id)
    if state is None:
        return start_booking(session_id)

    step = state["step"]
    data = state["data"]

    if step == "name":
        if len(message.strip()) < 2:
            return _reply("Sorry, could you tell me your full name?")
        data["name"] = message.strip()
        state["step"] = "country"
        return _reply(f"Thanks, {data['name']}. Which country are you booking from?")

    if step == "country":
        if not _country_looks_valid(message):
            return _reply("Sorry, which country are you calling/booking from?")
        data["country"] = message.strip()
        state["step"] = "department"
        return _reply("Got it. Which department would you like to see a doctor in?", choices=_department_choices())

    if step == "department":
        dept = _match_department(message)
        if not dept:
            return _reply("Sorry, I didn't catch a valid department. Which one?", choices=_department_choices())
        data["department"] = dept
        doctor_pool = hospital_data.get_doctors_by_department(dept)
        if not doctor_pool:
            data["doctor_name"] = None
            state["step"] = "date"
            return _ask_for_date(data)
        if len(doctor_pool) == 1:
            data["doctor_name"] = doctor_pool[0]["name"]
            state["step"] = "date"
            return _ask_for_date(data)
        state["step"] = "doctor"
        state["_doctor_pool"] = doctor_pool
        return _reply("Which doctor would you prefer?", choices=_doctor_choices(doctor_pool))

    if step == "doctor":
        doctor_pool = state.get("_doctor_pool", hospital_data.get_doctors_by_department(data.get("department", "")))
        doc = _match_doctor(message, doctor_pool)
        if not doc:
            return _reply("Sorry, I didn't catch that — which doctor?", choices=_doctor_choices(doctor_pool))
        data["doctor_name"] = doc["name"]
        state["step"] = "date"
        return _ask_for_date(data)

    if step == "date":
        available_dates = availability_service.get_available_dates(data.get("doctor_name"))
        matched = _match_date_choice(message, available_dates)
        if not matched:
            return _reply("Sorry, that date isn't available — please pick one:", choices=available_dates)
        data["date"] = matched
        state["step"] = "time"
        return _ask_for_time(data)

    if step == "time":
        available_times = availability_service.get_available_times(data.get("doctor_name"), data["date"])
        matched = _match_time_choice(message, available_times, data["date"])
        if not matched:
            return _reply(
                "Sorry, that time isn't available — please pick one:",
                choices=[{"label": t, "value": t} for t in available_times],
            )
        data["time"] = matched
        state["step"] = "phone"
        return _reply("What's the best contact phone number to reach you on?")

    if step == "phone":
        if not _phone_looks_valid(message):
            return _reply("That doesn't look like a valid phone number — could you say it again?")
        data["phone"] = message.strip()
        state["step"] = "confirm"
        return _reply(_summary(data), choices=[{"label": "Yes, confirm", "value": "yes"}, {"label": "No, cancel", "value": "no"}])

    if step == "confirm":
        reply = message.strip().lower()
        if reply in {"yes", "y", "confirm", "yeah", "yep", "correct"}:
            # Re-check availability right before saving — the slot could
            # have been taken by someone else since it was offered.
            if data.get("doctor_name") and not availability_service.is_slot_available(
                data["doctor_name"], data["date"], data["time"]
            ):
                state["step"] = "date"
                return _reply(
                    "Sorry, that slot was just taken by someone else. Let's pick another date:",
                    choices=availability_service.get_available_dates(data.get("doctor_name")),
                )
            record = _save_appointment(data)
            _sessions.pop(session_id, None)
            date_label = availability_service.format_date_label(record["date"])
            return _reply(
                f"You're all set, {record['name']}! Appointment confirmed with "
                f"{record.get('doctor_name') or 'an available doctor'} ({record['department']}) "
                f"on {date_label} at {record['time']}. "
                f"Your reference number is {record['id']}."
            )
        if reply in {"no", "n", "nope"}:
            return _cancel(session_id)
        return _reply(
            "Sorry, just to confirm — should I book this?",
            choices=[{"label": "Yes, confirm", "value": "yes"}, {"label": "No, cancel", "value": "no"}],
        )

    # Shouldn't get here, but fail safe rather than crash the conversation
    _sessions.pop(session_id, None)
    return _reply("Something went wrong with that booking — let's start over. Would you like to book an appointment?")
