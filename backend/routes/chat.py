# backend/routes/chat.py
import uuid

from flask import Blueprint, request, jsonify

from hospital_data import get_doctors_by_department, get_all_departments
from services.ai_service import generate_ai_response
from services.appointment_service import (
    handle_booking_reply,
    is_booking_in_progress,
    start_booking,
    wants_to_book,
)
from utils.intent import handle_intent

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"error": "No message provided"}), 400

    user_message = data["message"]
    # The frontend generates one session_id per browser tab/call and
    # sends it with every message so the booking flow can track where
    # a given caller is in the conversation.
    session_id = data.get("session_id") or str(uuid.uuid4())

    # If this session already has a booking in progress, every message
    # is part of that flow until it's completed or cancelled.
    if is_booking_in_progress(session_id):
        response = handle_booking_reply(session_id, user_message)
        return jsonify({"response": response, "session_id": session_id})

    # A fresh request to book an appointment starts the flow.
    if wants_to_book(user_message):
        response = start_booking(session_id)
        return jsonify({"response": response, "session_id": session_id})

    # Otherwise answer directly from hospital_data.py first — guaranteed
    # accurate, consistently formatted, and doesn't need an AI call.
    intent_response = handle_intent(user_message)
    if intent_response:
        return jsonify({"response": intent_response, "session_id": session_id})

    # Fall back to the AI model (symptoms, general questions, etc.)
    response = generate_ai_response(user_message)
    return jsonify({"response": response, "session_id": session_id})


@chat_bp.route("/departments", methods=["GET"])
def list_departments():
    return jsonify({"departments": get_all_departments()})


@chat_bp.route("/doctors", methods=["GET"])
def list_doctors():
    dept = request.args.get("department")
    if dept:
        doctors = get_doctors_by_department(dept)
        return jsonify({"doctors": doctors})
    return jsonify({"doctors": []})


@chat_bp.route("/appointments", methods=["GET"])
def list_appointments():
    import json
    import os
    from services.appointment_service import APPOINTMENTS_FILE

    if not os.path.exists(APPOINTMENTS_FILE):
        return jsonify({"appointments": []})
    try:
        with open(APPOINTMENTS_FILE, "r", encoding="utf-8") as f:
            appointments = json.load(f)
    except (json.JSONDecodeError, OSError):
        appointments = []
    return jsonify({"appointments": appointments})
