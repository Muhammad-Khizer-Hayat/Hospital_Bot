import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
import database
from routes.chat import chat_bp
from routes.upload import upload_bp
from flask import Flask, send_from_directory
from flask_cors import CORS

app_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.join(os.path.dirname(app_dir), "frontend")

def create_app():
    app = Flask(__name__, static_folder=frontend_dir)
    app.config.from_object(Config)
    CORS(app)
    database.init_db()
    app.register_blueprint(chat_bp, url_prefix="/api")
    app.register_blueprint(upload_bp, url_prefix="/api")

    @app.route("/")
    def index():
        return send_from_directory(frontend_dir, "index.html")

    @app.route("/<path:filename>")
    def static_files(filename):
        return send_from_directory(frontend_dir, filename)

    return app

# Module-level instance so a production WSGI server (gunicorn, etc.)
# can import it directly as "app:app" — see Procfile.
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # debug=True is a security risk in production (exposes a debugger
    # that can run arbitrary code). Only enabled when FLASK_DEBUG=1 is
    # explicitly set — leave it unset on your live deployment.
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)