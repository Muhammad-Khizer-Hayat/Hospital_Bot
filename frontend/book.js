// book.js — standalone appointment booking form.
// Reuses the same API as the chat assistant's booking flow, just
// collected all at once instead of turn by turn.

const API_BASE = "/api";

const deptSelect   = document.getElementById("department");
const doctorSelect = document.getElementById("doctor");
const dateSelect   = document.getElementById("date");
const timeSelect   = document.getElementById("time");
const form         = document.getElementById("book-form");
const submitBtn    = document.getElementById("submit-btn");
const banner       = document.getElementById("banner");

// ── Load departments on page load ───────────────────────────────
async function loadDepartments() {
  try {
    const res = await fetch(`${API_BASE}/departments`);
    const data = await res.json();
    (data.departments || []).forEach((dept) => {
      const opt = document.createElement("option");
      opt.value = dept;
      opt.textContent = dept;
      deptSelect.appendChild(opt);
    });
  } catch (err) {
    showBanner("Couldn't load departments. Please refresh the page.");
  }
}

// ── Department -> Doctor ─────────────────────────────────────────
deptSelect.addEventListener("change", async () => {
  resetSelect(doctorSelect, "Loading…", true);
  resetSelect(dateSelect, "Select a doctor first…", true);
  resetSelect(timeSelect, "Select a date first…", true);

  const dept = deptSelect.value;
  if (!dept) {
    resetSelect(doctorSelect, "Select a department first…", true);
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/doctors?department=${encodeURIComponent(dept)}`);
    const data = await res.json();
    const doctors = data.doctors || [];

    resetSelect(doctorSelect, doctors.length ? "Select a doctor…" : "Any available doctor", false);
    doctors.forEach((doc) => {
      const opt = document.createElement("option");
      opt.value = doc.name;
      opt.textContent = `${doc.name} — ${doc.specialization}`;
      doctorSelect.appendChild(opt);
    });

    // No doctors listed for this department — availability still
    // works (unassigned to a specific doctor), so let the date step run.
    if (doctors.length === 0) {
      loadDates("");
    }
  } catch (err) {
    showBanner("Couldn't load doctors for that department.");
  }
});

// ── Doctor -> Date ────────────────────────────────────────────────
doctorSelect.addEventListener("change", () => {
  loadDates(doctorSelect.value);
});

async function loadDates(doctorName) {
  resetSelect(dateSelect, "Loading…", true);
  resetSelect(timeSelect, "Select a date first…", true);

  try {
    const res = await fetch(`${API_BASE}/available-dates?doctor=${encodeURIComponent(doctorName)}`);
    const data = await res.json();
    const dates = data.dates || [];

    resetSelect(dateSelect, dates.length ? "Select a date…" : "No availability", dates.length === 0);
    dates.forEach((d) => {
      const opt = document.createElement("option");
      opt.value = d.value;
      opt.textContent = d.label;
      dateSelect.appendChild(opt);
    });
  } catch (err) {
    showBanner("Couldn't load available dates.");
  }
}

// ── Date -> Time ──────────────────────────────────────────────────
dateSelect.addEventListener("change", async () => {
  resetSelect(timeSelect, "Loading…", true);
  const date = dateSelect.value;
  if (!date) {
    resetSelect(timeSelect, "Select a date first…", true);
    return;
  }

  try {
    const res = await fetch(
      `${API_BASE}/available-times?doctor=${encodeURIComponent(doctorSelect.value)}&date=${encodeURIComponent(date)}`
    );
    const data = await res.json();
    const times = data.times || [];

    resetSelect(timeSelect, times.length ? "Select a time…" : "No times available", times.length === 0);
    times.forEach((t) => {
      const opt = document.createElement("option");
      opt.value = t;
      opt.textContent = t;
      timeSelect.appendChild(opt);
    });
  } catch (err) {
    showBanner("Couldn't load available times.");
  }
});

// ── Submit ────────────────────────────────────────────────────────
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearErrors();
  hideBanner();

  const payload = {
    name: document.getElementById("name").value.trim(),
    country: document.getElementById("country").value.trim(),
    department: deptSelect.value,
    doctor_name: doctorSelect.value,
    date: dateSelect.value,
    time: timeSelect.value,
    phone: document.getElementById("phone").value.trim(),
  };

  submitBtn.disabled = true;
  submitBtn.textContent = "Booking…";

  try {
    const res = await fetch(`${API_BASE}/book-appointment`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (!res.ok) {
      showFieldErrors(data.fields || {});
      showBanner(data.error || "Something went wrong — please check the form.");
      submitBtn.disabled = false;
      submitBtn.textContent = "Book Appointment";
      return;
    }

    showSuccess(data.appointment);
  } catch (err) {
    showBanner("⚠️ Could not reach the server. Please try again.");
    submitBtn.disabled = false;
    submitBtn.textContent = "Book Appointment";
  }
});

// ── Helpers ───────────────────────────────────────────────────────
function resetSelect(select, placeholder, disabled) {
  select.innerHTML = `<option value="">${placeholder}</option>`;
  select.disabled = disabled;
}

function showBanner(msg) {
  banner.textContent = msg;
  banner.style.display = "block";
}
function hideBanner() {
  banner.style.display = "none";
}

function showFieldErrors(fields) {
  Object.keys(fields).forEach((key) => {
    const fieldEl = document.getElementById(`field-${key}`);
    if (fieldEl) {
      fieldEl.classList.add("has-error");
      const errEl = fieldEl.querySelector(".field-error");
      if (errEl) errEl.textContent = fields[key];
    }
  });
}

function clearErrors() {
  document.querySelectorAll(".field.has-error").forEach((el) => el.classList.remove("has-error"));
}

function showSuccess(appointment) {
  document.querySelector(".book-card").innerHTML = `
    <div class="success-card">
      <div class="success-icon">✓</div>
      <h2>Appointment Confirmed</h2>
      <div class="success-details">
        <div><strong>Name:</strong> ${appointment.name}</div>
        <div><strong>Department:</strong> ${appointment.department}</div>
        <div><strong>Doctor:</strong> ${appointment.doctor_name || "Any available doctor"}</div>
        <div><strong>Date:</strong> ${appointment.date_label}</div>
        <div><strong>Time:</strong> ${appointment.time}</div>
        <div><strong>Phone:</strong> ${appointment.phone}</div>
      </div>
      <div>Reference number: <span class="success-ref">${appointment.id}</span></div>
    </div>
  `;
}

loadDepartments();
