# backend/auth.py
"""
Protects admin-only routes (viewing appointments, uploading a new
doctors PDF) behind a single shared secret set via the ADMIN_API_KEY
environment variable.

This is intentionally simple — one shared password, not per-user
accounts — appropriate for a small clinic/hospital admin team. If you
need individual staff logins/roles later, this is the place to swap
in something like Flask-Login.
"""
from functools import wraps
from flask import jsonify, request
from config import Config


def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not Config.ADMIN_API_KEY:
            # Fail closed, not open — an unset key means "not configured
            # yet", not "no protection needed."
            return jsonify({
                "error": "Admin access isn't configured on this server yet. "
                         "Set ADMIN_API_KEY as an environment variable."
            }), 503

        provided = request.headers.get("X-Admin-Key", "")
        if provided != Config.ADMIN_API_KEY:
            return jsonify({"error": "Unauthorized. Provide a valid X-Admin-Key header."}), 401

        return f(*args, **kwargs)

    return wrapper
