import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
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
    app.register_blueprint(chat_bp, url_prefix="/api")
    app.register_blueprint(upload_bp, url_prefix="/api")

    @app.route("/")
    def index():
        return send_from_directory(frontend_dir, "index.html")

    @app.route("/<path:filename>")
    def static_files(filename):
        return send_from_directory(frontend_dir, filename)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)