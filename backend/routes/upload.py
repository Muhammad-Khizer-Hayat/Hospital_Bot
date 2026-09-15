# backend/routes/upload.py
import os
import tempfile

from flask import Blueprint, jsonify, request

import hospital_data
from auth import require_admin
from services.pdf_service import parse_doctors_pdf, save_doctors_data

upload_bp = Blueprint("upload", __name__)

ALLOWED_EXT = {".pdf"}


@upload_bp.route("/upload-doctors", methods=["POST"])
@require_admin
def upload_doctors():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded. Send it as multipart form field 'file'."}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify({"error": "Only PDF files are supported."}), 400

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        doctors, departments, warnings = parse_doctors_pdf(tmp_path)
    except Exception as e:
        return jsonify({"error": f"Couldn't read that PDF: {e}"}), 400
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

    if doctors:
        save_doctors_data(doctors, departments)
        hospital_data.reload_data()

    return jsonify({
        "doctors_found": len(doctors),
        "departments_found": departments,
        "doctors": doctors,
        "warnings": warnings,
    })


@upload_bp.route("/doctors-source", methods=["GET"])
def doctors_source():
    """Lets the frontend show whether it's serving the uploaded PDF's
    data or the built-in defaults."""
    return jsonify({
        "using_uploaded_data": hospital_data.using_uploaded_data(),
        "doctor_count": len(hospital_data.get_all_doctors()),
    })
