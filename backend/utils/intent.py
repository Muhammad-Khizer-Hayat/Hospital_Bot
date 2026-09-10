# backend/utils/intent.py
import re
import difflib
import hospital_data

# Words that signal the user actually wants to be routed to a doctor/
# department (as opposed to just mentioning a body part or symptom).
REQUEST_WORDS = {
    "doctor", "doctors", "specialist", "physician", "dr", "see",
    "who", "which", "appointment", "book", "recommend", "consult",
    "department", "departments",
}

# Common everyday words -> actual department name in hospital_data.py
SYNONYMS = {
    "heart": "Cardiology",
    "cardiac": "Cardiology",
    "brain": "Neurology",
    "stroke": "Neurology",
    "bone": "Orthopedics",
    "joint": "Orthopedics",
    "fracture": "Orthopedics",
    "child": "Pediatrics",
    "children": "Pediatrics",
    "kid": "Pediatrics",
    "baby": "Pediatrics",
    "skin": "Dermatology",
    "xray": "Radiology",
    "scan": "Radiology",
    "emergency": "Emergency",
}

_WORD_RE = re.compile(r"[a-zA-Z]+")


def _tokens(text: str):
    """Whole-word tokens only — avoids substring bugs like 'er' matching
    inside 'where'."""
    return _WORD_RE.findall(text.lower())


def _closest(word, vocab, cutoff=0.8):
    """Typo-tolerant match against a vocabulary of whole words."""
    matches = difflib.get_close_matches(word, vocab, n=1, cutoff=cutoff)
    return matches[0] if matches else None


def _format_doctor_list(doc_list):
    return "\n".join(f"- {d['name']} — {d['specialization']}" for d in doc_list)


def _department_response(dept_name):
    doc_list = hospital_data.get_doctors_by_department(dept_name)
    if doc_list:
        return f"**{dept_name} Department**\n\n{_format_doctor_list(doc_list)}"
    return f"**{dept_name} Department**\n\nNo doctors are currently listed for this department."


def handle_intent(message: str):
    """
    Returns a formatted, data-accurate answer straight from hospital_data.py
    for department/doctor questions, or None if the AI model should
    handle the message instead (general/symptom questions, etc).
    """
    tokens = _tokens(message)
    if not tokens:
        return None
    token_set = set(tokens)

    # 1. List every department
    if {"all", "departments"} <= token_set or (
        {"which", "departments"} <= token_set or {"what", "departments"} <= token_set
    ):
        dept_lines = "\n".join(f"- {d}" for d in hospital_data.get_all_departments())
        return f"**Our Departments**\n\n{dept_lines}"

    # 2. List every doctor
    if (
        {"all", "doctors"} <= token_set
        or {"list", "doctors"} <= token_set
        or {"our", "doctors"} <= token_set
    ):
        return f"**Our Doctors**\n\n{_format_doctor_list(hospital_data.get_all_doctors())}"

    # 3. Specific doctor lookup — whole-word match, with typo tolerance
    for doc in hospital_data.get_all_doctors():
        name_tokens = [t for t in _tokens(doc["name"]) if t != "dr"]
        for token in tokens:
            if len(token) <= 2:
                continue
            if token in name_tokens or _closest(token, name_tokens, cutoff=0.82):
                return (
                    f"**{doc['name']}**\n"
                    f"- Department: {doc['department']}\n"
                    f"- Specialization: {doc['specialization']}"
                )

    # 4. Direct department name match, with typo tolerance
    dept_lookup = {d.lower(): d for d in hospital_data.get_all_departments()}
    for token in tokens:
        if token in dept_lookup:
            return _department_response(dept_lookup[token])
        close = _closest(token, list(dept_lookup.keys()), cutoff=0.8)
        if close:
            return _department_response(dept_lookup[close])

    # 5. Everyday-language synonyms ("heart", "child", ...) — only treated
    #    as a routing request if the message also asks to see/find/recommend
    #    a doctor. Otherwise a message like "signs of a heart attack" is a
    #    real medical question and should go to the AI, not a doctor list.
    has_request_word = any(
        t in REQUEST_WORDS or _closest(t, REQUEST_WORDS, cutoff=0.82) for t in tokens
    )
    if has_request_word:
        for token in tokens:
            dept = SYNONYMS.get(token) or SYNONYMS.get(
                _closest(token, list(SYNONYMS.keys()), cutoff=0.8) or ""
            )
            if dept:
                return _department_response(dept)

    return None
