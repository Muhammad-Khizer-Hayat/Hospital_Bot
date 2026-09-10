# Hospital Bot

A Flask-based hospital AI assistant with a browser chat interface, appointment booking flow, hospital information lookup, voice-assistant controls, and PDF-based doctor data updates.

## Features

- Chat about hospital departments, doctors, services, appointments, and policies
- AI responses for healthcare-related questions using Groq
- Appointment booking conversation flow with browser-session tracking
- Department and doctor listings
- Upload a doctors-list PDF to update the hospital data
- Browser voice assistant interface
- Flask serves both the API and the frontend

## Requirements

- Python 3.10 or newer
- A Groq API key

## Installation

Clone the repository and enter the project directory:

```powershell
git clone https://github.com/Muhammad-Khizer-Hayat/Hospital_Bot.git
cd Hospital_Bot
```

Create and activate a virtual environment on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the dependencies:

```powershell
pip install -r requirements.txt
```

## Environment Configuration

Create a `.env` file in the project root. This file is ignored by Git and must not be committed.

```env
GROQ_API_KEY=your_groq_api_key_here
```

## Running the Application

From the project root, run:

```powershell
python backend\app.py
```

Open the application in your browser:

```text
http://127.0.0.1:5000
```

The Flask development server runs with debug mode enabled in the current configuration.

## API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/api/chat` | Send a chat message and receive a response |
| `GET` | `/api/departments` | List hospital departments |
| `GET` | `/api/doctors?department=...` | List doctors in a department |
| `GET` | `/api/appointments` | List stored appointments |
| `POST` | `/api/upload-doctors` | Upload a doctors list as a PDF |
| `GET` | `/api/doctors-source` | Show the active doctor data source and count |

Example chat request:

```json
{
  "message": "How do I book an appointment?",
  "session_id": "optional-browser-session-id"
}
```

The PDF upload endpoint expects a multipart form field named `file`. PDF uploads are limited to 5 MB.

## Project Structure

```text
backend/
  app.py                  Flask application entry point
  config.py               Environment and application configuration
  hospital_data.py        Hospital, department, and doctor data
  routes/                 Chat and upload API routes
  services/               AI, PDF, booking, and appointment services
  utils/                  Intent handling helpers
  data/                   Persisted doctor data
frontend/
  index.html              Chat interface
  script.js               Frontend behavior and API calls
  style.css               Interface styles
requirements.txt           Python dependencies
```

## Important Notes

- The application is for informational support and does not replace a qualified medical professional or emergency services.
- Update the placeholder emergency phone number in `frontend/script.js` before deploying.
- Do not commit `.env`, API keys, patient information, or other sensitive data.
- The default doctor data is stored in `backend/data/doctors_data.json` and can be replaced through the PDF upload feature.

## License

No license has been specified for this project yet.
