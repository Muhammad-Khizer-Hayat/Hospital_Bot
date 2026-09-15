// Relative paths — works whether you're running locally or deployed,
// since app.py serves the frontend and API from the same origin.
const API = "/api/chat";
const UPLOAD_API = "/api/upload-doctors";
const SOURCE_API = "/api/doctors-source";
const DEPARTMENTS_API = "/api/departments";

// One session id per browser tab, persisted for the tab's lifetime.
// The backend uses this to track multi-turn flows (like appointment
// booking) across separate /api/chat calls.
function getSessionId() {
  let sid = sessionStorage.getItem("chat_session_id");
  if (!sid) {
    sid = (crypto.randomUUID ? crypto.randomUUID() : `sid-${Date.now()}-${Math.random().toString(16).slice(2)}`);
    sessionStorage.setItem("chat_session_id", sid);
  }
  return sid;
}

// Shared by both the text chat UI and voice mode — one place that
// actually talks to the backend, so booking-flow continuity works
// no matter which mode the person is using.
async function askBackend(text) {
  const res = await fetch(API, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: text, session_id: getSessionId() }),
  });
  const data = await res.json();
  return {
    response: data.response || "Sorry, I didn't get a response.",
    choices: data.choices || [],
  };
}

// TODO: replace with your real hospital/on-call contact number.
// Used by every "Call Now" / emergency button below — E.164 format
// (e.g. "+923001234567") works best for the tel: link.
const EMERGENCY_PHONE = "+10000000000";

function wireEmergencyButtons() {
  document.querySelectorAll("[data-emergency-call]").forEach((el) => {
    el.href = `tel:${EMERGENCY_PHONE}`;
  });
}

// ── Helpers ────────────────────────────────────────────────────
function hideWelcome() {
  const w = document.getElementById("welcome");
  if (w) w.remove();
}

function scrollBottom() {
  const box = document.getElementById("messages");
  box.scrollTop = box.scrollHeight;
}

// Turn the bot's lightweight markdown (**bold**, "- " bullets, blank-line
// paragraphs) into real HTML so replies render as clean formatted text
// instead of literal asterisks and dashes.
function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderMarkdown(raw) {
  const lines = escapeHtml(raw).split("\n");
  let html = "";
  let inList = false;

  const closeList = () => {
    if (inList) {
      html += "</ul>";
      inList = false;
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();

    if (!line) {
      closeList();
      continue;
    }

    // Bullet line: "- something"
    if (line.startsWith("- ")) {
      if (!inList) {
        html += "<ul>";
        inList = true;
      }
      html += `<li>${line.slice(2).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")}</li>`;
      continue;
    }

    closeList();

    // Heading line: "**Something**" on its own line
    const headingMatch = line.match(/^\*\*(.+?)\*\*$/);
    if (headingMatch) {
      html += `<div class="bubble-heading">${headingMatch[1]}</div>`;
      continue;
    }

    html += `<p>${line.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")}</p>`;
  }
  closeList();
  return html;
}

function addBubble(text, role, choices) {
  const box = document.getElementById("messages");

  const row = document.createElement("div");
  row.className = `bubble-row ${role}`;

  const avatar = document.createElement("div");
  avatar.className = `avatar ${role === "bot" ? "bot-avatar" : "user-avatar"}`;
  avatar.textContent = role === "bot" ? "+" : "U";

  const bubble = document.createElement("div");
  bubble.className = `bubble ${role === "bot" ? "bot-bubble" : "user-bubble"}`;
  bubble.innerHTML = role === "bot" ? renderMarkdown(text) : escapeHtml(text).replace(/\n/g, "<br>");

  row.appendChild(avatar);
  row.appendChild(bubble);
  box.appendChild(row);

  if (role === "bot" && Array.isArray(choices) && choices.length > 0) {
    const choiceRow = document.createElement("div");
    choiceRow.className = "choice-row";
    choices.forEach((choice) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "choice-btn";
      btn.textContent = choice.label;
      btn.onclick = () => {
        // Disable the whole set once one is picked, so old options
        // from an earlier step can't be clicked after moving on.
        choiceRow.querySelectorAll(".choice-btn").forEach((b) => (b.disabled = true));
        choiceRow.classList.add("answered");
        sendMessage(choice.value);
      };
      choiceRow.appendChild(btn);
    });
    box.appendChild(choiceRow);
  }

  scrollBottom();
  return bubble;
}

function showTyping() {
  const box = document.getElementById("messages");

  const row = document.createElement("div");
  row.className = "bubble-row bot";
  row.id = "typing-row";

  const avatar = document.createElement("div");
  avatar.className = "avatar bot-avatar";
  avatar.textContent = "+";

  const bubble = document.createElement("div");
  bubble.className = "bubble bot-bubble";
  bubble.innerHTML = `<div class="typing-dots"><span></span><span></span><span></span></div>`;

  row.appendChild(avatar);
  row.appendChild(bubble);
  box.appendChild(row);
  scrollBottom();
}

function removeTyping() {
  const t = document.getElementById("typing-row");
  if (t) t.remove();
}

// ── Send ───────────────────────────────────────────────────────
async function sendMessage(prefilledText) {
  const input = document.getElementById("msg-input");
  const btn   = document.getElementById("send-btn");
  const text  = (prefilledText !== undefined ? prefilledText : input.value).trim();
  if (!text) return;

  hideWelcome();
  addBubble(text, "user");
  input.value = "";
  input.style.height = "auto";
  btn.disabled = true;
  showTyping();

  try {
    const { response, choices } = await askBackend(text);
    removeTyping();
    addBubble(response, "bot", choices);
  } catch (err) {
    removeTyping();
    addBubble("⚠️ Could not reach the server. Make sure the backend is running.", "bot");
  } finally {
    btn.disabled = false;
    input.focus();
  }
}

// ── Quick buttons ──────────────────────────────────────────────
function quickAsk(el) {
  document.getElementById("msg-input").value = el.textContent || el.innerText;
  sendMessage();
}

function deptAsk(dept) {
  document.getElementById("msg-input").value = `Tell me about the ${dept} department`;
  sendMessage();
}

function bookAppointmentCta() {
  closeSidebarOnMobile();
  document.getElementById("msg-input").value = "Book an appointment";
  sendMessage();
}

// ── Mobile sidebar drawer ──────────────────────────────────────
function toggleSidebar() {
  document.getElementById("sidebar").classList.toggle("open");
  document.getElementById("sidebar-backdrop").classList.toggle("active");
}

function closeSidebarOnMobile() {
  if (window.innerWidth <= 768) {
    document.getElementById("sidebar").classList.remove("open");
    document.getElementById("sidebar-backdrop").classList.remove("active");
  }
}

// ── Bookings viewer ────────────────────────────────────────────
// ── Admin auth (for viewing bookings / uploading a doctors PDF) ──
// A single shared password, not per-user accounts — set via the
// ADMIN_API_KEY environment variable on the server. Prompted once
// per browser tab and cached in sessionStorage after that.
function getAdminKey(forcePrompt = false) {
  let key = sessionStorage.getItem("admin_key");
  if (!key || forcePrompt) {
    key = window.prompt("Enter the admin password to continue:");
    if (key) sessionStorage.setItem("admin_key", key);
  }
  return key || "";
}

function clearAdminKey() {
  sessionStorage.removeItem("admin_key");
}

async function openBookingsModal(forcePrompt = false) {
  closeSidebarOnMobile();
  const modal = document.getElementById("bookings-modal");
  const body = document.getElementById("bookings-body");
  const count = document.getElementById("bookings-count");
  modal.classList.add("active");
  body.innerHTML = '<div class="bookings-loading">Loading…</div>';

  const key = getAdminKey(forcePrompt);
  if (!key) {
    count.textContent = "—";
    body.innerHTML = '<div class="bookings-empty">Admin password required.</div>';
    return;
  }

  try {
    const res = await fetch(`${API.replace("/chat", "")}/appointments`, {
      headers: { "X-Admin-Key": key },
    });

    if (res.status === 401) {
      clearAdminKey();
      count.textContent = "—";
      body.innerHTML = '<div class="bookings-empty">Incorrect password. <a href="#" onclick="openBookingsModal(); return false;">Try again</a>.</div>';
      return;
    }
    if (res.status === 503) {
      count.textContent = "—";
      body.innerHTML = '<div class="bookings-empty">Admin access isn\'t configured on the server yet (ADMIN_API_KEY not set).</div>';
      return;
    }

    const data = await res.json();
    const appointments = data.appointments || [];
    count.textContent = appointments.length;

    if (appointments.length === 0) {
      body.innerHTML = '<div class="bookings-empty"><div class="empty-icon">□</div><strong>No appointments yet</strong><span>New bookings will appear here.</span></div>';
      return;
    }

    const rows = appointments.map((a) => `
      <article class="booking-row">
        <div class="booking-row-topline">
          <span class="booking-ref">REF #${escapeHtml(a.id || "—")}</span>
          <span class="booking-status"><span></span> Confirmed</span>
        </div>
        <div class="booking-row-main">
          <div class="booking-patient">
            <div class="patient-avatar">${escapeHtml((a.patient_name || "?").trim().charAt(0).toUpperCase())}</div>
            <div><strong class="booking-name">${escapeHtml(a.patient_name || "—")}</strong><span class="booking-contact">${escapeHtml(a.phone || "No phone provided")}</span></div>
          </div>
          <div class="booking-visit"><span class="booking-label">VISIT</span><strong>${escapeHtml(a.appointment_date || "—")}</strong><span>${escapeHtml(a.appointment_time || "—")}</span></div>
        </div>
        <div class="booking-row-details">
          <span><b>Department</b>${escapeHtml(a.department || "—")}</span>
          <span><b>Doctor</b>${escapeHtml(a.doctor_name || "Any available doctor")}</span>
          <span><b>Country</b>${escapeHtml(a.country || "—")}</span>
        </div>
      </article>
    `).join("");
    body.innerHTML = rows;
  } catch (err) {
    count.textContent = "—";
    body.innerHTML = '<div class="bookings-empty">⚠️ Could not load appointments.</div>';
  }
}

function closeBookingsModal() {
  document.getElementById("bookings-modal").classList.remove("active");
}

// ── Keyboard ───────────────────────────────────────────────────
function handleKey(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

// ── Auto-resize textarea ───────────────────────────────────────
function autoResize(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 120) + "px";
}

// ── Doctors PDF upload ───────────────────────────────────────────
async function uploadDoctorsPdf(input) {
  const file = input.files[0];
  if (!file) return;

  const statusEl = document.getElementById("upload-status");

  const key = getAdminKey();
  if (!key) {
    statusEl.textContent = "Admin password required to upload.";
    statusEl.className = "upload-status error";
    input.value = "";
    return;
  }

  statusEl.textContent = "Reading PDF…";
  statusEl.className = "upload-status uploading";

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch(UPLOAD_API, {
      method: "POST",
      headers: { "X-Admin-Key": key },
      body: formData,
    });

    if (res.status === 401) {
      clearAdminKey();
      statusEl.textContent = "Incorrect admin password. Try uploading again.";
      statusEl.className = "upload-status error";
      return;
    }
    if (res.status === 503) {
      statusEl.textContent = "Admin access isn't configured on the server yet.";
      statusEl.className = "upload-status error";
      return;
    }

    const data = await res.json();

    if (!res.ok) {
      statusEl.textContent = data.error || "Couldn't process that PDF.";
      statusEl.className = "upload-status error";
      return;
    }

    if (data.doctors_found > 0) {
      statusEl.textContent = `✓ Loaded ${data.doctors_found} doctor${data.doctors_found === 1 ? "" : "s"} across ${data.departments_found.length} department${data.departments_found.length === 1 ? "" : "s"}.`;
      statusEl.className = "upload-status success";
      refreshDepartmentChips();
    } else {
      statusEl.textContent = (data.warnings && data.warnings[0]) || "No doctors found in that PDF.";
      statusEl.className = "upload-status error";
    }
  } catch (err) {
    statusEl.textContent = "⚠️ Could not reach the server.";
    statusEl.className = "upload-status error";
  } finally {
    input.value = "";
  }
}

// Refresh the sidebar department chips + count badge from whatever data
// is currently active (uploaded PDF or the built-in defaults).
async function refreshDepartmentChips() {
  try {
    const [sourceRes, deptRes] = await Promise.all([
      fetch(SOURCE_API),
      fetch(DEPARTMENTS_API),
    ]);
    const sourceData = await sourceRes.json();
    const deptData = await deptRes.json();

    const badge = document.getElementById("doctor-count-badge");
    if (badge) {
      badge.textContent = `${sourceData.doctor_count} doctor${sourceData.doctor_count === 1 ? "" : "s"} loaded`;
      badge.classList.toggle("from-pdf", sourceData.using_uploaded_data);
    }

    const wrap = document.getElementById("dept-wrap");
    if (wrap && Array.isArray(deptData.departments)) {
      wrap.innerHTML = "";
      deptData.departments.forEach((dept) => {
        const chip = document.createElement("span");
        chip.className = "dept";
        chip.textContent = dept;
        chip.onclick = () => deptAsk(dept);
        wrap.appendChild(chip);
      });
    }
  } catch (err) {
    // silent — non-critical UI refresh
  }
}

document.addEventListener("DOMContentLoaded", () => {
  wireEmergencyButtons();
  refreshDepartmentChips();
});

// ── Voice call mode ────────────────────────────────────────────
// Uses the browser's built-in speech recognition (STT) and speech
// synthesis (TTS) — no telephony provider, no API key, works offline
// once the page is loaded. Chrome/Edge have the best support; Safari
// is partial; Firefox doesn't support SpeechRecognition at all.
const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;

let voiceRecognition = null;
let voiceCallActive = false;
let voiceMuted = false;

const END_CALL_PHRASES = ["goodbye", "bye", "end call", "hang up", "that's all"];

function voiceSupported() {
  return !!SpeechRecognitionAPI && "speechSynthesis" in window;
}

function setCallStatus(text) {
  const el = document.getElementById("call-status");
  if (el) el.textContent = text;
}

function appendCallTranscript(text, role) {
  const box = document.getElementById("call-transcript");
  if (!box) return;
  const line = document.createElement("div");
  line.className = `call-line ${role}`;
  line.textContent = text;
  box.appendChild(line);
  box.scrollTop = box.scrollHeight;
}

function speak(text, onDone) {
  window.speechSynthesis.cancel();
  // Strip markdown symbols so TTS doesn't read out "asterisk asterisk"
  const clean = text.replace(/\*\*/g, "").replace(/^- /gm, "").replace(/\n+/g, ". ");
  const utter = new SpeechSynthesisUtterance(clean);
  utter.rate = 1.0;
  utter.onstart = () => setCallStatus("Speaking…");
  utter.onend = () => {
    if (onDone) onDone();
  };
  window.speechSynthesis.speak(utter);
}

function startListening() {
  if (!voiceCallActive || voiceMuted) return;

  voiceRecognition = new SpeechRecognitionAPI();
  voiceRecognition.lang = "en-US";
  voiceRecognition.interimResults = false;
  voiceRecognition.maxAlternatives = 1;

  voiceRecognition.onstart = () => setCallStatus("Listening…");

  voiceRecognition.onresult = async (event) => {
    const transcript = event.results[0][0].transcript.trim();
    if (!transcript) {
      if (voiceCallActive) startListening();
      return;
    }
    appendCallTranscript(transcript, "user");

    if (END_CALL_PHRASES.some((p) => transcript.toLowerCase().includes(p))) {
      speak("Thanks for calling City General Hospital. Take care!", () => endVoiceCall());
      return;
    }

    setCallStatus("Thinking…");
    try {
      const { response, choices } = await askBackend(transcript);
      const cleanResponse = response.replace(/\*\*/g, "").replace(/^- /gm, "• ");
      appendCallTranscript(cleanResponse, "bot");

      // Messages rely on clickable buttons for their options in text
      // chat — since there's nothing to click over voice, read the
      // options out loud too, or the caller has no idea what to say.
      let spoken = response;
      if (choices && choices.length > 0) {
        const optionsList = choices.map((c) => c.label).join(", ");
        spoken = `${response} Your options are: ${optionsList}.`;
      }

      if (voiceCallActive) speak(spoken, () => startListening());
    } catch (err) {
      appendCallTranscript("Sorry, I couldn't reach the server.", "bot");
      if (voiceCallActive) speak("Sorry, I couldn't reach the server.", () => startListening());
    }
  };

  voiceRecognition.onerror = (event) => {
    // "no-speech" just means silence — restart listening quietly.
    if (event.error === "no-speech" && voiceCallActive) {
      startListening();
      return;
    }
    setCallStatus(`Mic error: ${event.error}`);
  };

  voiceRecognition.onend = () => {
    // If nothing else restarted listening (e.g. we're mid-speak), leave it.
  };

  voiceRecognition.start();
}

function startVoiceCall() {
  if (!voiceSupported()) {
    alert("Voice mode isn't supported in this browser. Try Chrome or Edge.");
    return;
  }
  voiceCallActive = true;
  document.getElementById("call-overlay").classList.add("active");
  document.getElementById("call-transcript").innerHTML = "";
  setCallStatus("Connecting…");

  const greeting = "Hi, you've reached City General Hospital's virtual assistant. How can I help — or say 'book an appointment' to get started?";
  appendCallTranscript(greeting, "bot");
  speak(greeting, () => startListening());
}

function endVoiceCall() {
  voiceCallActive = false;
  window.speechSynthesis.cancel();
  if (voiceRecognition) {
    voiceRecognition.onresult = null;
    voiceRecognition.onerror = null;
    voiceRecognition.stop();
  }
  document.getElementById("call-overlay").classList.remove("active");
  setCallStatus("");
}

function toggleMute() {
  voiceMuted = !voiceMuted;
  const btn = document.getElementById("mute-btn");
  if (btn) btn.textContent = voiceMuted ? "🔇 Unmute" : "🎙️ Mute";
  if (voiceMuted && voiceRecognition) {
    voiceRecognition.stop();
    setCallStatus("Muted");
  } else if (!voiceMuted && voiceCallActive) {
    startListening();
  }
}