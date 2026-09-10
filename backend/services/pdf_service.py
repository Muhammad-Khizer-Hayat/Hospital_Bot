# backend/services/pdf_service.py
"""
Parses a doctors-list PDF into structured records.

Two strategies are tried, in order:
  1. Table extraction  — works when the PDF has an actual table with
     columns like Name / Department / Specialization (most exports
     from Excel/Word "insert table" do this).
  2. Line-by-line text — fallback for PDFs that are just plain text,
     one doctor per line, e.g.:
       "Dr. Ayesha Khan - Cardiology - Heart Failure & Transplant"
       "Dr. Ayesha Khan | Cardiology | Heart Failure & Transplant"

If your PDF uses a different layout and the parser misses entries,
the safest formats are either a real table, or one doctor per line
with the department and specialization separated by "-" or "|".
"""
import json
import os
import re

import pdfplumber

from config import Config

KNOWN_DEPARTMENTS = [
    "Cardiology", "Neurology", "Orthopedics", "Pediatrics", "Dermatology",
    "Radiology", "Emergency", "Oncology", "Gynecology", "Obstetrics",
    "Urology", "ENT", "Ophthalmology", "Psychiatry", "Gastroenterology",
    "Nephrology", "Pulmonology", "Endocrinology", "General Medicine",
    "General Surgery", "Dentistry", "ICU", "Pharmacy", "Anesthesiology",
]

_HEADER_ALIASES = {
    "name": {"name", "doctor", "doctor name", "doctor's name", "physician"},
    "department": {"department", "dept", "specialty area", "division", "ward"},
    "specialization": {"specialization", "specialisation", "speciality", "specialty", "field", "expertise"},
}

_NAME_RE = re.compile(r"(Dr\.?\s+[A-Z][a-zA-Z.\-]+(?:\s+[A-Z][a-zA-Z.\-]+){0,3})")


def _match_header(cell):
    if not cell:
        return None
    key = cell.strip().lower()
    for field, aliases in _HEADER_ALIASES.items():
        if key in aliases:
            return field
    return None


def _extract_from_tables(pdf):
    doctors = []
    for page in pdf.pages:
        for table in page.extract_tables():
            if not table or len(table) < 2:
                continue
            header = [_match_header(c) for c in table[0]]
            if "name" not in header:
                continue
            for row in table[1:]:
                record = {}
                for col_idx, field in enumerate(header):
                    if field and col_idx < len(row) and row[col_idx]:
                        record[field] = row[col_idx].strip()
                name = record.get("name", "").strip()
                if name:
                    doctors.append({
                        "name": name if name.lower().startswith("dr") else f"Dr. {name}",
                        "department": record.get("department", "").strip() or "General",
                        "specialization": record.get("specialization", "").strip() or "General Practice",
                    })
    return doctors


def _extract_from_text(pdf):
    doctors = []
    for page in pdf.pages:
        text = page.extract_text() or ""
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            name_match = _NAME_RE.search(line)
            if not name_match:
                continue
            name = name_match.group(1).strip()
            rest = line[name_match.end():].strip(" -|,:\t")

            parts = [p.strip() for p in re.split(r"\s*[-|]\s*", rest) if p.strip()]

            department = next(
                (dept for dept in KNOWN_DEPARTMENTS if dept.lower() in line.lower()),
                None,
            )

            specialization = None
            for part in parts:
                if department and part.lower() == department.lower():
                    continue
                specialization = part
                break

            doctors.append({
                "name": name,
                "department": department or "General",
                "specialization": specialization or "General Practice",
            })
    return doctors


def parse_doctors_pdf(file_path):
    """Returns (doctors, departments, warnings)."""
    with pdfplumber.open(file_path) as pdf:
        doctors = _extract_from_tables(pdf)
        if not doctors:
            doctors = _extract_from_text(pdf)

    warnings = []
    if not doctors:
        warnings.append(
            "Couldn't find any doctor entries in this PDF. For best results, "
            "use either a real table with Name / Department / Specialization "
            "columns, or one doctor per line like: "
            "\"Dr. Jane Smith - Cardiology - Heart Failure\"."
        )

    seen = set()
    unique = []
    for d in doctors:
        if d["name"] not in seen:
            seen.add(d["name"])
            unique.append(d)

    departments = sorted({d["department"] for d in unique})
    return unique, departments, warnings


def save_doctors_data(doctors, departments):
    os.makedirs(os.path.dirname(Config.DOCTORS_DATA_FILE), exist_ok=True)
    with open(Config.DOCTORS_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"doctors": doctors, "departments": departments}, f, indent=2)
