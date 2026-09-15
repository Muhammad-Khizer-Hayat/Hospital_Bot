# backend/routes/chat.py
import uuid

from flask import Blueprint, request, jsonify

from auth import require_admin
from hospital_data import get_doctors_by_department, get_all_departments
from services.ai_service import generate_ai_response
from services.appointment_service import (
    abandon_booking,
    handle_booking_reply,
    is_booking_in_progress,
    is_new_topic,
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
    if is_booking_in_progress(session_id) and not is_new_topic(user_message):
        response = handle_booking_reply(session_id, user_message)
        return jsonify({"response": response, "session_id": session_id})

    if is_booking_in_progress(session_id):
        abandon_booking(session_id)

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


@chat_bp.route("/diagnostics/groq", methods=["GET"])
def diagnostics_groq():
    """Visit this URL directly in a browser to check exactly where the
    Groq connection is failing — DNS resolution, the raw HTTPS request,
    or authentication — instead of guessing from a generic error."""
    import socket
    import time

    from config import Config

    result = {}

    try:
        ip = socket.gethostbyname("api.groq.com")
        result["dns_resolution"] = {"ok": True, "resolved_ip": ip}
    except Exception as e:
        result["dns_resolution"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        result["diagnosis"] = "DNS can't resolve api.groq.com — likely a network/DNS restriction in this environment."
        return jsonify(result)

    try:
        import httpx
        start = time.time()
        with httpx.Client(timeout=10) as http_client:
            r = http_client.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {Config.GROQ_API_KEY or ''}"},
            )
        result["https_request"] = {
            "ok": True,
            "status_code": r.status_code,
            "elapsed_seconds": round(time.time() - start, 2),
        }
        if r.status_code == 401:
            result["diagnosis"] = "Network connectivity is fine — the API key itself is being rejected (401)."
        elif r.status_code == 200:
            result["diagnosis"] = "Everything works — DNS, network, and the API key are all fine."
        else:
            result["diagnosis"] = f"Reached Groq but got an unexpected status code: {r.status_code}."
    except Exception as e:
        result["https_request"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        result["diagnosis"] = "DNS resolves fine, but the HTTPS connection itself fails — likely outbound network/TLS being blocked in this environment."

    result["groq_api_key_set"] = bool(Config.GROQ_API_KEY)
    result["groq_api_key_prefix"] = (Config.GROQ_API_KEY[:7] + "…") if Config.GROQ_API_KEY else None

    return jsonify(result)


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
@require_admin
def list_appointments():
    import database
    return jsonify({"appointments": database.get_all_appointments()})
