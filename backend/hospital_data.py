# backend/hospital_data.py
import json
import os
from config import Config

# ── Built-in fallback data ──────────────────────────────────────────
# Used until a doctors-list PDF is uploaded (or if the uploaded file
# couldn't be parsed). Once a PDF is successfully processed, its data
# is cached to Config.DOCTORS_DATA_FILE and takes over from here.
_DEFAULT_DEPARTMENTS = [
    "Cardiology",
    "Neurology",
    "Orthopedics",
    "Pediatrics",
    "Dermatology",
    "Radiology",
    "Emergency",
]

_DEFAULT_DOCTORS = [
    {"name": "Dr. Ayesha Khan", "department": "Cardiology", "specialization": "Heart Failure & Transplant"},
    {"name": "Dr. Bilal Ahmed", "department": "Neurology", "specialization": "Stroke & Epilepsy"},
    {"name": "Dr. Sana Iqbal", "department": "Orthopedics", "specialization": "Joint Replacement"},
    {"name": "Dr. Ali Raza", "department": "Pediatrics", "specialization": "Neonatology"},
    {"name": "Dr. Fatima Noor", "department": "Dermatology", "specialization": "Cosmetic Dermatology"},
]

_cache = {"departments": None, "doctors": None}


def _load():
    """Populate the in-memory cache — prefers data parsed from an
    uploaded PDF, falls back to the built-in defaults above."""
    if os.path.exists(Config.DOCTORS_DATA_FILE):
        try:
            with open(Config.DOCTORS_DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            doctors = data.get("doctors") or []
            departments = data.get("departments") or []
            if doctors:
                dept_set = list(dict.fromkeys(departments + [d["department"] for d in doctors]))
                _cache["doctors"] = doctors
                _cache["departments"] = dept_set
                return
        except (json.JSONDecodeError, OSError):
            pass
    _cache["doctors"] = _DEFAULT_DOCTORS
    _cache["departments"] = _DEFAULT_DEPARTMENTS


def reload_data():
    """Call this right after a new PDF is uploaded so the change is
    picked up immediately, with no server restart needed."""
    _load()


def get_all_departments():
    if _cache["departments"] is None:
        _load()
    return _cache["departments"]


def get_all_doctors():
    if _cache["doctors"] is None:
        _load()
    return _cache["doctors"]


def get_doctors_by_department(dept_name):
    return [doc for doc in get_all_doctors() if doc["department"].lower() == dept_name.lower()]


def using_uploaded_data():
    """True once a PDF's parsed data is what's actually being served."""
    return os.path.exists(Config.DOCTORS_DATA_FILE) and _cache["doctors"] is not _DEFAULT_DOCTORS
