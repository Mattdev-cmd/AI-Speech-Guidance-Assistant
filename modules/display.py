"""
Display module for showing transcripts and response suggestions.

Supports three output modes:
  - Terminal: Rich text UI in the console
  - Web: Flask-SocketIO real-time web dashboard
  - HDMI: Same as terminal, for HDMI-connected displays
"""

import json
import logging
import os
import sys
import textwrap
import threading
import time
from datetime import datetime

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────
#  Terminal display (works on HDMI too)
# ──────────────────────────────────────────

class TerminalDisplay:
    """Rich terminal UI for transcripts and suggestions."""

    # ANSI color codes
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"

    def __init__(self, config: dict):
        self.cfg = config.get("display", {})
        self.show_transcript = self.cfg.get("show_transcript", True)
        self.show_suggestions = self.cfg.get("show_suggestions", True)
        self.max_suggestions = self.cfg.get("max_suggestions", 3)
        self._width = min(os.get_terminal_size().columns, 80) if sys.stdout.isatty() else 80

    def _separator(self, char="─"):
        print(f"{self.DIM}{char * self._width}{self.RESET}")

    def _header(self, text: str, color: str = ""):
        col = color or self.CYAN
        padding = self._width - len(text) - 4
        print(f"\n{col}{self.BOLD}┌─ {text} {'─' * max(padding, 0)}┐{self.RESET}")

    def _footer(self):
        print(f"{self.DIM}└{'─' * (self._width - 2)}┘{self.RESET}")

    def show_listening(self):
        """Display listening indicator."""
        print(f"\n{self.BLUE}{self.BOLD}🎤  Listening...{self.RESET}", end="\r")

    def show_processing(self):
        """Display processing indicator."""
        print(f"\n{self.YELLOW}{self.BOLD}⏳  Processing speech...{self.RESET}")

    def show_transcript_text(self, text: str):
        """Display the transcribed speech."""
        if not self.show_transcript or not text:
            return
        self._header("YOUR SPEECH", self.CYAN)
        wrapped = textwrap.fill(text, width=self._width - 6)
        for line in wrapped.split("\n"):
            print(f"{self.CYAN}│  {self.WHITE}{line}{self.RESET}")
        self._footer()

    def show_response(self, response: dict):
        """Display AI-generated response suggestions."""
        if not self.show_suggestions:
            return

        summary = response.get("summary", "")
        suggestions = response.get("suggestions", [])
        guidance = response.get("guidance", "")

        if summary:
            self._header("UNDERSTANDING", self.MAGENTA)
            print(f"{self.MAGENTA}│  {self.WHITE}{summary}{self.RESET}")
            self._footer()

        if suggestions:
            self._header("SUGGESTED RESPONSES", self.GREEN)
            for i, s in enumerate(suggestions[: self.max_suggestions], 1):
                wrapped = textwrap.fill(s, width=self._width - 10)
                lines = wrapped.split("\n")
                print(f"{self.GREEN}│  {self.BOLD}[{i}]{self.RESET} {self.WHITE}{lines[0]}{self.RESET}")
                for line in lines[1:]:
                    print(f"{self.GREEN}│      {self.WHITE}{line}{self.RESET}")
            self._footer()

        if guidance:
            self._header("GUIDANCE", self.YELLOW)
            wrapped = textwrap.fill(guidance, width=self._width - 6)
            for line in wrapped.split("\n"):
                print(f"{self.YELLOW}│  {self.WHITE}{line}{self.RESET}")
            self._footer()

        print()

    def show_error(self, message: str):
        """Display an error message."""
        print(f"\n{self.BOLD}\033[91m⚠  Error: {message}{self.RESET}")

    def show_scene(self, description: str):
        """Display scene analysis results."""
        if description:
            print(f"{self.DIM}📷 Scene: {description}{self.RESET}")

    def show_learning_insights(self, insights: dict):
        """Display educational learning insights."""
        if not insights:
            return

        vocab = insights.get("vocabulary", [])
        topic = insights.get("topic_note", "")
        feedback = insights.get("speech_feedback", "")
        questions = insights.get("follow_up_questions", [])

        if vocab:
            self._header("VOCABULARY", self.MAGENTA)
            for v in vocab:
                print(f"{self.MAGENTA}│  {self.BOLD}{v['term']}{self.RESET} — {self.WHITE}{v['definition']}{self.RESET}")
            self._footer()

        if topic:
            self._header("TOPIC NOTE", self.CYAN)
            wrapped = textwrap.fill(topic, width=self._width - 6)
            for line in wrapped.split("\n"):
                print(f"{self.CYAN}│  {self.WHITE}{line}{self.RESET}")
            self._footer()

        if feedback:
            self._header("SPEECH FEEDBACK", self.YELLOW)
            wrapped = textwrap.fill(feedback, width=self._width - 6)
            for line in wrapped.split("\n"):
                print(f"{self.YELLOW}│  {self.WHITE}{line}{self.RESET}")
            self._footer()

        if questions:
            self._header("THINK DEEPER", self.GREEN)
            for i, q in enumerate(questions, 1):
                print(f"{self.GREEN}│  {self.BOLD}[{i}]{self.RESET} {self.WHITE}{q}{self.RESET}")
            self._footer()

        print()

    def stream_response_start(self, section_name: str = "RESPONSE"):
        """Start displaying a streaming response section."""
        self._header(section_name, self.GREEN)
        print(f"{self.GREEN}│  ", end="", flush=True)

    def stream_token(self, token: str):
        """Display a single token as it arrives (for streaming)."""
        print(f"{self.WHITE}{token}{self.RESET}", end="", flush=True)

    def stream_response_end(self):
        """End the streaming response section."""
        print(f"\n{self.RESET}")
        self._footer()


# ──────────────────────────────────────────
#  Web dashboard (Flask-SocketIO)
# ──────────────────────────────────────────


class WebDisplay:
    """Real-time web dashboard for the assistant."""

    def show_mic_level(self, rms: float):
        """Emit mic level (RMS) to the frontend via SocketIO."""
        self._emit("mic_level", {"rms": rms})

    def __init__(self, config: dict):
        self.cfg = config.get("display", {})
        self.port = self.cfg.get("web_port", 8080)
        self.tts_enabled = True
        self.educational_enabled = True
        self._app = None
        self._socketio = None
        self._thread = None
        self._init_app()

    def _init_app(self):
        """Initialize the Flask + SocketIO web app."""
        try:
            import secrets
            from flask import Flask, render_template_string, redirect, url_for, session
            from flask_socketio import SocketIO
            from flask_login import LoginManager, login_required, current_user
            from .management import management_bp, FlaskUser
            from .database import get_db

            template_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates"
            )
            self._app = Flask(__name__, template_folder=template_dir)
            self._app.config["SECRET_KEY"] = os.urandom(24).hex()
            self._socketio = SocketIO(self._app, cors_allowed_origins="*")

            # --- Flask-Login setup ---
            login_manager = LoginManager()
            login_manager.init_app(self._app)
            login_manager.login_view = "management.login"
            login_manager.login_message_category = "info"

            @login_manager.user_loader
            def load_user(user_id):
                db = get_db()
                user = db.get_user_by_id(int(user_id))
                if user:
                    return FlaskUser(user)
                return None

            # --- CSRF token generation ---
            @self._app.before_request
            def _csrf_setup():
                if "csrf_token" not in session:
                    session["csrf_token"] = secrets.token_hex(16)

            # --- Register management blueprint ---
            self._app.register_blueprint(management_bp)

            # --- Initialize database on first request ---
            get_db()

            # --- Routes ---
            @self._app.route("/")
            def index():
                if current_user.is_authenticated:
                    return redirect(url_for("management.dashboard"))
                return redirect(url_for("management.login"))

            @self._app.route("/assistant")
            @login_required
            def assistant():
                return render_template_string(WEB_TEMPLATE)

            @self._app.route("/streaming")
            def streaming_assistant():
                """Gemini-like streaming assistant (no login required for demo)."""
                try:
                    from flask import render_template
                    return render_template("streaming_assistant.html")
                except Exception as e:
                    logger.error(f"Error rendering streaming template: {e}")
                    return render_template_string(WEB_TEMPLATE)

            @self._socketio.on("toggle_tts")
            def handle_toggle_tts(data):
                self.tts_enabled = data.get("enabled", True)
                logger.info("TTS toggled: %s", self.tts_enabled)

            @self._socketio.on("toggle_educational")
            def handle_toggle_educational(data):
                self.educational_enabled = data.get("enabled", True)
                logger.info("Educational mode toggled: %s", self.educational_enabled)

            logger.info("Web display initialized on port %d", self.port)
        except ImportError as e:
            logger.warning("Flask/SocketIO/Login not installed, web display unavailable: %s", e)

    def start(self):
        """Start the web server in a background thread."""
        if not self._socketio:
            return

        self._thread = threading.Thread(
            target=self._socketio.run,
            args=(self._app,),
            kwargs={"host": "0.0.0.0", "port": self.port, "allow_unsafe_werkzeug": True},
            daemon=True,
        )
        self._thread.start()
        logger.info("Web dashboard running at http://0.0.0.0:%d", self.port)

    def _emit(self, event: str, data: dict):
        if self._socketio:
            self._socketio.emit(event, data)

    def show_listening(self):
        self._emit("status", {"state": "listening"})

    def show_processing(self):
        self._emit("status", {"state": "processing"})

    def show_transcript_text(self, text: str):
        self._emit("transcript", {"text": text, "time": datetime.now().isoformat()})

    def show_response(self, response: dict):
        self._emit("response", response)

    def show_error(self, message: str):
        self._emit("error", {"message": message})

    def show_scene(self, description: str):
        self._emit("scene", {"description": description})

    def show_learning_insights(self, insights: dict):
        self._emit("learning_insights", insights)

    def stream_response_start(self, section_name: str = "RESPONSE"):
        """Start a streaming response section."""
        self._emit("stream_start", {"section": section_name})

    def stream_token(self, token: str):
        """Emit a single token to the frontend (for streaming)."""
        self._emit("stream_token", {"token": token})

    def stream_response_end(self):
        """End the streaming response."""
        self._emit("stream_end", {})


# ──────────────────────────────────────────
#  Web dashboard HTML template
# ──────────────────────────────────────────

WEB_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Speech Guidance Assistant</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0c0e1a;
            --bg-secondary: #131627;
            --bg-card: rgba(22, 27, 51, 0.7);
            --bg-card-hover: rgba(30, 36, 66, 0.8);
            --bg-sidebar: rgba(16, 19, 36, 0.95);
            --border-subtle: rgba(255, 255, 255, 0.06);
            --border-accent: rgba(110, 198, 255, 0.3);
            --text-primary: #e8eaf0;
            --text-secondary: #8b92a8;
            --text-muted: #5a6178;
            --accent-blue: #6ec6ff;
            --accent-green: #6ee7a0;
            --accent-amber: #ffb86c;
            --accent-purple: #c49cff;
            --accent-red: #ff6b6b;
            --shadow-card: 0 4px 24px rgba(0, 0, 0, 0.3);
            --shadow-glow-blue: 0 0 20px rgba(110, 198, 255, 0.1);
            --radius-sm: 8px;
            --radius-md: 12px;
            --radius-lg: 16px;
            --transition: 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        }

        *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
            line-height: 1.6;
        }

        /* ---- Background Gradient Orbs ---- */
        body::before, body::after {
            content: '';
            position: fixed;
            border-radius: 50%;
            filter: blur(120px);
            opacity: 0.15;
            z-index: 0;
            pointer-events: none;
        }
        body::before {
            width: 500px; height: 500px;
            background: var(--accent-blue);
            top: -100px; left: -100px;
        }
        body::after {
            width: 400px; height: 400px;
            background: var(--accent-purple);
            bottom: -80px; right: -80px;
        }

        /* ---- Layout ---- */
        .app-layout {
            display: grid;
            grid-template-columns: 320px 1fr;
            grid-template-rows: auto 1fr;
            gap: 0;
            min-height: 100vh;
            position: relative;
            z-index: 1;
        }

        /* ---- Header ---- */
        .header {
            grid-column: 1 / -1;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 16px 28px;
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-subtle);
            backdrop-filter: blur(12px);
        }
        .header-left {
            display: flex;
            align-items: center;
            gap: 14px;
        }
        .logo-icon {
            width: 40px; height: 40px;
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
            border-radius: var(--radius-sm);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            flex-shrink: 0;
        }
        .header-title {
            font-size: 1.15em;
            font-weight: 600;
            color: var(--text-primary);
            letter-spacing: -0.3px;
        }
        .header-subtitle {
            font-size: 0.75em;
            color: var(--text-muted);
            font-weight: 400;
        }
        .header-right {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .connection-badge {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.72em;
            font-weight: 500;
            background: rgba(110, 231, 160, 0.1);
            color: var(--accent-green);
            border: 1px solid rgba(110, 231, 160, 0.2);
        }
        .connection-badge.disconnected {
            background: rgba(255, 107, 107, 0.1);
            color: var(--accent-red);
            border-color: rgba(255, 107, 107, 0.2);
        }
        .connection-dot {
            width: 7px; height: 7px;
            border-radius: 50%;
            background: currentColor;
        }
        .icon-btn {
            height: 34px;
            padding: 0 12px;
            border-radius: var(--radius-sm);
            border: 1px solid var(--border-subtle);
            background: transparent;
            color: var(--text-secondary);
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 13px;
            font-family: inherit;
            font-weight: 500;
            transition: var(--transition);
            white-space: nowrap;
        }
        .icon-btn svg {
            width: 15px; height: 15px;
            fill: none; stroke: currentColor;
            stroke-width: 2; stroke-linecap: round; stroke-linejoin: round;
        }
        .icon-btn:hover { background: var(--bg-card); color: var(--text-primary); }

        /* ---- Sidebar ---- */
        .sidebar {
            background: var(--bg-sidebar);
            border-right: 1px solid var(--border-subtle);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .sidebar-header {
            padding: 16px 20px 12px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid var(--border-subtle);
        }
        .sidebar-header h3 {
            font-size: 0.78em;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            color: var(--text-muted);
        }
        .sidebar-actions {
            display: flex;
            gap: 6px;
        }
        .sidebar-actions button {
            padding: 4px 10px;
            font-size: 0.7em;
            border-radius: 6px;
            border: 1px solid var(--border-subtle);
            background: transparent;
            color: var(--text-secondary);
            cursor: pointer;
            transition: var(--transition);
            font-family: inherit;
        }
        .sidebar-actions button:hover {
            background: var(--bg-card);
            color: var(--text-primary);
        }

        .history-list {
            flex: 1;
            overflow-y: auto;
            padding: 8px 12px;
        }
        .history-list::-webkit-scrollbar { width: 4px; }
        .history-list::-webkit-scrollbar-thumb { background: var(--border-subtle); border-radius: 4px; }

        .history-empty {
            text-align: center;
            padding: 40px 20px;
            color: var(--text-muted);
            font-size: 0.82em;
        }
        .history-empty .empty-icon { font-size: 2em; margin-bottom: 10px; opacity: 0.5; }

        .history-item {
            padding: 12px 14px;
            border-radius: var(--radius-sm);
            margin-bottom: 4px;
            cursor: pointer;
            transition: var(--transition);
            border: 1px solid transparent;
        }
        .history-item:hover {
            background: var(--bg-card);
            border-color: var(--border-subtle);
        }
        .history-item.active {
            background: var(--bg-card-hover);
            border-color: var(--border-accent);
        }
        .history-item-time {
            font-size: 0.68em;
            color: var(--text-muted);
            margin-bottom: 4px;
            font-weight: 500;
        }
        .history-item-text {
            font-size: 0.82em;
            color: var(--text-secondary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .history-item.active .history-item-text { color: var(--text-primary); }

        /* ---- Main Content ---- */
        .main-content {
            padding: 24px 32px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        .main-content::-webkit-scrollbar { width: 5px; }
        .main-content::-webkit-scrollbar-thumb { background: var(--border-subtle); border-radius: 4px; }

        /* ---- Status Bar ---- */
        .status-bar {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 14px 20px;
            border-radius: var(--radius-md);
            background: var(--bg-card);
            border: 1px solid var(--border-subtle);
            transition: var(--transition);
        }
        .status-indicator {
            width: 38px; height: 38px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            flex-shrink: 0;
            position: relative;
        }
        .status-bar.listening .status-indicator {
            background: rgba(110, 198, 255, 0.15);
        }
        .status-bar.listening .status-indicator::after {
            content: '';
            position: absolute;
            inset: -4px;
            border-radius: 50%;
            border: 2px solid var(--accent-blue);
            opacity: 0;
            animation: pulse-ring 2s ease-out infinite;
        }
        .status-bar.processing .status-indicator {
            background: rgba(255, 184, 108, 0.15);
            animation: spin-slow 2s linear infinite;
        }
        .status-bar.ready .status-indicator {
            background: rgba(110, 231, 160, 0.15);
        }
        .status-label {
            font-weight: 500;
            font-size: 0.92em;
        }
        .status-bar.listening { border-color: rgba(110, 198, 255, 0.2); }
        .status-bar.listening .status-label { color: var(--accent-blue); }
        .status-bar.processing { border-color: rgba(255, 184, 108, 0.2); }
        .status-bar.processing .status-label { color: var(--accent-amber); }
        .status-bar.ready { border-color: rgba(110, 231, 160, 0.2); }
        .status-bar.ready .status-label { color: var(--accent-green); }
        .status-bar.error { border-color: rgba(255, 107, 107, 0.25); }
        .status-bar.error .status-indicator { background: rgba(255, 107, 107, 0.15); }
        .status-bar.error .status-label { color: var(--accent-red); }

        @keyframes pulse-ring {
            0% { opacity: 0.6; transform: scale(1); }
            100% { opacity: 0; transform: scale(1.5); }
        }
        @keyframes spin-slow {
            to { transform: rotate(360deg); }
        }

        /* ---- Scene Bar ---- */
        .scene-bar {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 16px;
            border-radius: var(--radius-sm);
            background: rgba(196, 156, 255, 0.06);
            border: 1px solid rgba(196, 156, 255, 0.15);
            font-size: 0.82em;
            color: var(--text-secondary);
        }
        .scene-bar .scene-icon { color: var(--accent-purple); }

        /* ---- Cards ---- */
        .card {
            background: var(--bg-card);
            border-radius: var(--radius-md);
            border: 1px solid var(--border-subtle);
            overflow: hidden;
            transition: var(--transition);
            box-shadow: var(--shadow-card);
            animation: fade-in-up 0.35s ease-out;
        }
        .card:hover { border-color: rgba(255, 255, 255, 0.08); }
        .card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 14px 20px;
            border-bottom: 1px solid var(--border-subtle);
        }
        .card-header-left {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .card-icon {
            width: 30px; height: 30px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            flex-shrink: 0;
        }
        .card-label {
            font-size: 0.75em;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .card-body { padding: 16px 20px; }

        /* Transcript card */
        .card.transcript .card-icon { background: rgba(110, 198, 255, 0.12); }
        .card.transcript .card-label { color: var(--accent-blue); }
        .card.transcript .card-body p {
            font-size: 0.95em;
            line-height: 1.7;
            color: var(--text-primary);
        }

        /* Suggestions card */
        .card.suggestions .card-icon { background: rgba(110, 231, 160, 0.12); }
        .card.suggestions .card-label { color: var(--accent-green); }

        .suggestion-item {
            display: flex;
            align-items: flex-start;
            gap: 14px;
            padding: 14px 16px;
            border-radius: var(--radius-sm);
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border-subtle);
            margin-bottom: 8px;
            transition: var(--transition);
            position: relative;
        }
        .suggestion-item:last-child { margin-bottom: 0; }
        .suggestion-item:hover {
            background: rgba(110, 231, 160, 0.04);
            border-color: rgba(110, 231, 160, 0.15);
        }
        .suggestion-num {
            background: linear-gradient(135deg, var(--accent-green), #4ecdc4);
            color: #0c0e1a;
            border-radius: 8px;
            width: 28px; height: 28px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 0.78em;
            flex-shrink: 0;
        }
        .suggestion-text {
            flex: 1;
            font-size: 0.9em;
            line-height: 1.6;
            color: var(--text-primary);
            padding-top: 3px;
        }
        .copy-btn {
            padding: 4px 10px;
            border-radius: 6px;
            border: 1px solid var(--border-subtle);
            background: transparent;
            color: var(--text-muted);
            font-size: 0.7em;
            cursor: pointer;
            transition: var(--transition);
            white-space: nowrap;
            font-family: inherit;
            flex-shrink: 0;
            align-self: center;
        }
        .copy-btn:hover { background: var(--bg-card-hover); color: var(--text-primary); }
        .copy-btn.copied { color: var(--accent-green); border-color: var(--accent-green); }

        /* Guidance card */
        .card.guidance .card-icon { background: rgba(255, 184, 108, 0.12); }
        .card.guidance .card-label { color: var(--accent-amber); }
        .card.guidance .card-body p {
            font-size: 0.9em;
            line-height: 1.7;
            color: var(--text-primary);
        }

        /* Learning Insights card */
        .card.learning .card-icon { background: rgba(196, 156, 255, 0.12); }
        .card.learning .card-label { color: var(--accent-purple); }
        .insights-section {
            margin-bottom: 16px;
        }
        .insights-section:last-child { margin-bottom: 0; }
        .insights-section-title {
            font-size: 0.7em;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: var(--text-muted);
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .vocab-item {
            display: flex;
            align-items: baseline;
            gap: 8px;
            padding: 8px 12px;
            margin-bottom: 4px;
            border-radius: 6px;
            background: rgba(196, 156, 255, 0.04);
            border: 1px solid rgba(196, 156, 255, 0.1);
        }
        .vocab-term {
            font-weight: 600;
            color: var(--accent-purple);
            font-size: 0.88em;
            white-space: nowrap;
        }
        .vocab-def {
            font-size: 0.84em;
            color: var(--text-secondary);
            line-height: 1.5;
        }
        .insights-text {
            font-size: 0.88em;
            line-height: 1.65;
            color: var(--text-secondary);
            padding: 8px 12px;
            border-radius: 6px;
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border-subtle);
        }
        .question-item {
            display: flex;
            align-items: flex-start;
            gap: 10px;
            padding: 10px 12px;
            margin-bottom: 4px;
            border-radius: 6px;
            background: rgba(110, 198, 255, 0.04);
            border: 1px solid rgba(110, 198, 255, 0.1);
        }
        .question-icon {
            color: var(--accent-blue);
            font-size: 0.9em;
            flex-shrink: 0;
            margin-top: 1px;
        }
        .question-text {
            font-size: 0.86em;
            color: var(--text-primary);
            line-height: 1.55;
        }
        .insights-divider {
            height: 1px;
            background: var(--border-subtle);
            margin: 14px 0;
        }

        /* ---- Settings Panel ---- */
        .settings-panel {
            position: fixed;
            top: 0; right: -380px;
            width: 360px;
            height: 100vh;
            background: var(--bg-sidebar);
            border-left: 1px solid var(--border-subtle);
            z-index: 100;
            transition: right 0.3s ease;
            display: flex;
            flex-direction: column;
            backdrop-filter: blur(20px);
        }
        .settings-panel.open { right: 0; }
        .settings-overlay {
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.4);
            z-index: 99;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.3s ease;
        }
        .settings-overlay.open { opacity: 1; pointer-events: all; }
        .settings-header {
            padding: 18px 22px;
            border-bottom: 1px solid var(--border-subtle);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .settings-header h3 {
            font-size: 0.95em;
            font-weight: 600;
        }
        .settings-body {
            flex: 1;
            overflow-y: auto;
            padding: 20px 22px;
        }
        .setting-group {
            margin-bottom: 24px;
        }
        .setting-group-title {
            font-size: 0.7em;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-muted);
            margin-bottom: 12px;
        }
        .setting-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 0;
        }
        .setting-label { font-size: 0.85em; color: var(--text-secondary); }
        .toggle {
            position: relative;
            width: 40px; height: 22px;
            border-radius: 11px;
            background: var(--border-subtle);
            cursor: pointer;
            transition: var(--transition);
            border: none;
        }
        .toggle.active { background: var(--accent-blue); }
        .toggle::after {
            content: '';
            position: absolute;
            top: 3px; left: 3px;
            width: 16px; height: 16px;
            border-radius: 50%;
            background: white;
            transition: var(--transition);
        }
        .toggle.active::after { left: 21px; }
        .settings-footer {
            padding: 16px 22px;
            border-top: 1px solid var(--border-subtle);
        }
        .btn-danger {
            width: 100%;
            padding: 10px;
            border-radius: var(--radius-sm);
            border: 1px solid rgba(255, 107, 107, 0.3);
            background: rgba(255, 107, 107, 0.08);
            color: var(--accent-red);
            font-size: 0.82em;
            font-weight: 500;
            cursor: pointer;
            transition: var(--transition);
            font-family: inherit;
        }
        .btn-danger:hover { background: rgba(255, 107, 107, 0.15); }

        /* ---- Toast ---- */
        .toast {
            position: fixed;
            bottom: 24px;
            left: 50%;
            transform: translateX(-50%) translateY(80px);
            padding: 10px 20px;
            border-radius: var(--radius-sm);
            background: var(--bg-secondary);
            border: 1px solid var(--border-subtle);
            color: var(--text-primary);
            font-size: 0.82em;
            z-index: 200;
            opacity: 0;
            transition: all 0.3s ease;
            pointer-events: none;
        }
        .toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }

        /* ---- Animations ---- */
        @keyframes fade-in-up {
            from { opacity: 0; transform: translateY(12px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* ---- Responsive ---- */
        @media (max-width: 768px) {
            .app-layout { grid-template-columns: 1fr; }
            .sidebar { display: none; }
            .sidebar.mobile-open {
                display: flex;
                position: fixed;
                inset: 0;
                z-index: 90;
                width: 100%;
            }
            .main-content { padding: 16px; }
            .header { padding: 12px 16px; }
            .settings-panel { width: 100%; right: -100%; }
        }
    </style>
</head>
<body>
    <div class="app-layout">
        <!-- Header -->
        <header class="header">
            <div class="header-left">
                <div class="logo-icon">&#x1F3A4;</div>
                <div>
                    <div class="header-title">Speech Guidance Assistant</div>
                    <div class="header-subtitle">AI-Powered Real-Time Response Suggestions</div>
                </div>
            </div>
            <div class="header-right">
                <a href="/dashboard" class="icon-btn" title="Back to Dashboard" style="text-decoration:none;"><svg viewBox="0 0 24 24"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>Dashboard</a>
                <div id="connection-badge" class="connection-badge">
                    <span class="connection-dot"></span>
                    <span id="connection-text">Connected</span>
                </div>
                <button class="icon-btn" onclick="toggleMobileHistory()" title="History" id="mobile-history-btn"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>History</button>
                <button class="icon-btn" onclick="toggleSettings()" title="Settings"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>Settings</button>
            </div>
        </header>

        <!-- Sidebar: Conversation History -->
        <aside class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <h3>Conversation History</h3>
                <div class="sidebar-actions">
                    <button onclick="exportHistory()" title="Export as .txt">Export</button>
                    <button onclick="clearHistory()" title="Clear all">Clear</button>
                </div>
            </div>
            <div class="history-list" id="history-list">
                <div class="history-empty" id="history-empty">
                    <div class="empty-icon">&#x1F4AC;</div>
                    <div>No conversations yet.<br>Start speaking to begin.</div>
                </div>
            </div>
        </aside>

        <!-- Main Content -->
        <main class="main-content" id="main-content">
            <div class="status-bar ready" id="status-bar">
                <div class="status-indicator">&#x2714;</div>
                <div class="status-label">Ready &mdash; Speak to begin</div>
            </div>

            <div id="scene-bar" class="scene-bar" style="display:none;">
                <span class="scene-icon">&#x1F4F7;</span>
                <span id="scene-text"></span>
            </div>

            <div id="transcript-card" class="card transcript" style="display:none;">
                <div class="card-header">
                    <div class="card-header-left">
                        <div class="card-icon">&#x1F4DD;</div>
                        <span class="card-label">Your Speech</span>
                    </div>
                    <span id="transcript-time" style="font-size:0.7em;color:var(--text-muted);"></span>
                </div>
                <div class="card-body">
                    <p id="transcript-text"></p>
                </div>
            </div>

            <div id="suggestions-card" class="card suggestions" style="display:none;">
                <div class="card-header">
                    <div class="card-header-left">
                        <div class="card-icon">&#x1F4A1;</div>
                        <span class="card-label">Suggested Responses</span>
                    </div>
                </div>
                <div class="card-body" id="suggestions-list"></div>
            </div>

            <div id="guidance-card" class="card guidance" style="display:none;">
                <div class="card-header">
                    <div class="card-header-left">
                        <div class="card-icon">&#x1F9ED;</div>
                        <span class="card-label">Guidance</span>
                    </div>
                </div>
                <div class="card-body">
                    <p id="guidance-text"></p>
                </div>
            </div>

            <div id="learning-card" class="card learning" style="display:none;">
                <div class="card-header">
                    <div class="card-header-left">
                        <div class="card-icon">&#x1F393;</div>
                        <span class="card-label">Learning Insights</span>
                    </div>
                    <span style="font-size:0.68em;color:var(--text-muted);font-style:italic;">Educational Mode</span>
                </div>
                <div class="card-body" id="learning-body"></div>
            </div>
        </main>
    </div>

    <!-- Settings Panel -->
    <div class="settings-overlay" id="settings-overlay" onclick="toggleSettings()"></div>
    <div class="settings-panel" id="settings-panel">
        <div class="settings-header">
            <h3>Settings</h3>
            <button class="icon-btn" onclick="toggleSettings()">&#x2715;</button>
        </div>
        <div class="settings-body">
            <div class="setting-group">
                <div class="setting-group-title">Audio</div>
                <div class="setting-row">
                    <span class="setting-label">Text-to-Speech</span>
                    <button class="toggle active" id="tts-toggle" onclick="toggleTTS(this)"></button>
                </div>
            </div>
            <div class="setting-group">
                <div class="setting-group-title">Display</div>
                <div class="setting-row">
                    <span class="setting-label">Auto-scroll on new results</span>
                    <button class="toggle active" id="autoscroll-toggle" onclick="this.classList.toggle('active')"></button>
                </div>
                <div class="setting-row">
                    <span class="setting-label">Show scene context</span>
                    <button class="toggle active" id="scene-toggle" onclick="this.classList.toggle('active')"></button>
                </div>
            </div>
            <div class="setting-group">
                <div class="setting-group-title">Educational</div>
                <div class="setting-row">
                    <span class="setting-label">Learning Insights</span>
                    <button class="toggle active" id="edu-toggle" onclick="toggleEducational(this)"></button>
                </div>
            </div>
            <div class="setting-group">
                <div class="setting-group-title">History</div>
                <div class="setting-row">
                    <span class="setting-label">Keep conversation history</span>
                    <button class="toggle active" id="history-toggle" onclick="this.classList.toggle('active')"></button>
                </div>
            </div>
        </div>
        <div class="settings-footer">
            <button class="btn-danger" onclick="clearHistory(); showToast('History cleared');">Clear All History</button>
        </div>
    </div>

    <!-- Toast -->
    <div class="toast" id="toast"></div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.4/socket.io.min.js"></script>
    <script>
        // ── State ──
        const conversationHistory = [];
        let activeHistoryIdx = -1;
        let ttsEnabled = true;

        // ── Socket ──
        const socket = io();

        socket.on('connect', () => {
            const badge = document.getElementById('connection-badge');
            badge.classList.remove('disconnected');
            document.getElementById('connection-text').textContent = 'Connected';
        });
        socket.on('disconnect', () => {
            const badge = document.getElementById('connection-badge');
            badge.classList.add('disconnected');
            document.getElementById('connection-text').textContent = 'Disconnected';
        });

        socket.on('status', (data) => {
            const bar = document.getElementById('status-bar');
            bar.className = 'status-bar ' + data.state;
            const configs = {
                listening: { icon: '\u{1F3A4}', label: 'Listening...' },
                processing: { icon: '\u{23F3}', label: 'Processing speech...' },
                ready: { icon: '\u{2714}', label: 'Ready \u2014 Speak to begin' }
            };
            const cfg = configs[data.state] || { icon: '\u{2139}', label: data.state };
            bar.querySelector('.status-indicator').textContent = cfg.icon;
            bar.querySelector('.status-label').textContent = cfg.label;
        });

        // Track current exchange being built
        let currentExchange = null;
        let streamingBuffer = '';  // NEW: Buffer for streaming response
        let isStreaming = false;   // NEW: Track streaming state

        socket.on('transcript', (data) => {
            // Start a new exchange
            currentExchange = {
                time: data.time || new Date().toISOString(),
                transcript: data.text,
                summary: '',
                suggestions: [],
                guidance: ''
            };

            showTranscript(data.text, currentExchange.time);
            clearResponseCards();
        });

        // NEW: Handle streaming start
        socket.on('stream_start', (data) => {
            isStreaming = true;
            streamingBuffer = '';
            const card = document.getElementById('guidance-card');
            card.style.display = 'block';
            document.getElementById('guidance-text').innerHTML = '';
            console.log('Streaming started:', data.section);
        });

        // NEW: Handle individual tokens
        socket.on('stream_token', (data) => {
            const token = data.token || '';
            streamingBuffer += token;
            const textEl = document.getElementById('guidance-text');
            textEl.textContent = streamingBuffer;
            
            // Auto-scroll to keep response visible
            if (document.getElementById('autoscroll-toggle').classList.contains('active')) {
                const main = document.getElementById('main-content');
                main.scrollTo({ top: main.scrollHeight, behavior: 'smooth' });
            }
        });

        // NEW: Handle streaming end
        socket.on('stream_end', () => {
            isStreaming = false;
            if (currentExchange) {
                currentExchange.guidance = streamingBuffer;
            }
            console.log('Streaming ended');
        });

        socket.on('response', (data) => {
            if (currentExchange) {
                currentExchange.summary = data.summary || '';
                currentExchange.suggestions = data.suggestions || [];
                // Don't override guidance if it came from streaming
                if (!isStreaming) {
                    currentExchange.guidance = data.guidance || '';
                }

                // Save to history
                if (document.getElementById('history-toggle').classList.contains('active')) {
                    conversationHistory.push({...currentExchange});
                    renderHistoryList();
                    setActiveHistory(conversationHistory.length - 1);
                }
                currentExchange = null;
            }
            // Show suggestions if not already streaming
            if (!isStreaming) {
                showResponse(data);
            } else if (data.suggestions && data.suggestions.length) {
                // Show suggestions even during streaming
                const card = document.getElementById('suggestions-card');
                card.style.display = 'block';
                const list = document.getElementById('suggestions-list');
                list.innerHTML = '';
                data.suggestions.forEach((s, i) => {
                    const item = document.createElement('div');
                    item.className = 'suggestion-item';
                    item.innerHTML =
                        '<div class="suggestion-num">' + (i + 1) + '</div>' +
                        '<div class="suggestion-text">' + escapeHtml(s) + '</div>' +
                        '<button class="copy-btn" onclick="copySuggestion(this, ' + i + ')">Copy</button>';
                    list.appendChild(item);
                });
            }
        });

        socket.on('scene', (data) => {
            if (data.description && document.getElementById('scene-toggle').classList.contains('active')) {
                const el = document.getElementById('scene-bar');
                el.style.display = 'flex';
                document.getElementById('scene-text').textContent = data.description;
            }
        });

        socket.on('error', (data) => {
            const bar = document.getElementById('status-bar');
            bar.className = 'status-bar error';
            bar.querySelector('.status-indicator').textContent = '\u{26A0}';
            bar.querySelector('.status-label').textContent = data.message;
        });

        socket.on('tts_state', (data) => {
            ttsEnabled = data.enabled;
            const btn = document.getElementById('tts-toggle');
            btn.classList.toggle('active', ttsEnabled);
        });

        socket.on('learning_insights', (data) => {
            if (!document.getElementById('edu-toggle').classList.contains('active')) return;
            showLearningInsights(data);
            // Save to current history entry
            if (conversationHistory.length > 0) {
                conversationHistory[conversationHistory.length - 1].learning = data;
            }
        });

        // ── UI Functions ──
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function showTranscript(text, time) {
            const card = document.getElementById('transcript-card');
            card.style.display = 'block';
            document.getElementById('transcript-text').textContent = text;
            const t = new Date(time);
            document.getElementById('transcript-time').textContent =
                t.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
        }

        function clearResponseCards() {
            document.getElementById('suggestions-card').style.display = 'none';
            document.getElementById('guidance-card').style.display = 'none';
            document.getElementById('learning-card').style.display = 'none';
        }

        function showResponse(data) {
            if (data.suggestions && data.suggestions.length) {
                const card = document.getElementById('suggestions-card');
                card.style.display = 'block';
                const list = document.getElementById('suggestions-list');
                list.innerHTML = '';
                data.suggestions.forEach((s, i) => {
                    const item = document.createElement('div');
                    item.className = 'suggestion-item';
                    item.innerHTML =
                        '<div class="suggestion-num">' + (i + 1) + '</div>' +
                        '<div class="suggestion-text">' + escapeHtml(s) + '</div>' +
                        '<button class="copy-btn" onclick="copySuggestion(this, ' + i + ')">Copy</button>';
                    list.appendChild(item);
                });
            }
            if (data.guidance) {
                const card = document.getElementById('guidance-card');
                card.style.display = 'block';
                document.getElementById('guidance-text').textContent = data.guidance;
            }
            // Auto-scroll
            if (document.getElementById('autoscroll-toggle').classList.contains('active')) {
                const main = document.getElementById('main-content');
                main.scrollTo({ top: main.scrollHeight, behavior: 'smooth' });
            }
        }

        // ── Conversation History ──
        function renderHistoryList() {
            const container = document.getElementById('history-list');
            const emptyMsg = document.getElementById('history-empty');
            if (conversationHistory.length === 0) {
                emptyMsg.style.display = 'block';
                return;
            }
            emptyMsg.style.display = 'none';
            container.innerHTML = '';
            conversationHistory.forEach((entry, idx) => {
                const el = document.createElement('div');
                el.className = 'history-item' + (idx === activeHistoryIdx ? ' active' : '');
                const t = new Date(entry.time);
                el.innerHTML =
                    '<div class="history-item-time">' + t.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit', second:'2-digit'}) + '</div>' +
                    '<div class="history-item-text">' + escapeHtml(entry.transcript) + '</div>';
                el.addEventListener('click', () => showHistoryEntry(idx));
                container.appendChild(el);
            });
            // Scroll to bottom
            container.scrollTop = container.scrollHeight;
        }

        function setActiveHistory(idx) {
            activeHistoryIdx = idx;
            document.querySelectorAll('.history-item').forEach((el, i) => {
                el.classList.toggle('active', i === idx);
            });
        }

        function showHistoryEntry(idx) {
            const entry = conversationHistory[idx];
            if (!entry) return;
            setActiveHistory(idx);
            showTranscript(entry.transcript, entry.time);
            if (entry.suggestions.length || entry.guidance) {
                showResponse({ summary: entry.summary, suggestions: entry.suggestions, guidance: entry.guidance });
            } else {
                clearResponseCards();
            }
            if (entry.learning && document.getElementById('edu-toggle').classList.contains('active')) {
                showLearningInsights(entry.learning);
            }
        }

        function clearHistory() {
            conversationHistory.length = 0;
            activeHistoryIdx = -1;
            const container = document.getElementById('history-list');
            container.innerHTML = '<div class="history-empty" id="history-empty"><div class="empty-icon">&#x1F4AC;</div><div>No conversations yet.<br>Start speaking to begin.</div></div>';
            showToast('History cleared');
        }

        function exportHistory() {
            if (conversationHistory.length === 0) {
                showToast('No history to export');
                return;
            }
            let text = 'Speech Guidance Assistant - Conversation History\n';
            text += 'Exported: ' + new Date().toLocaleString() + '\n';
            text += '='.repeat(50) + '\n\n';
            conversationHistory.forEach((entry, i) => {
                const t = new Date(entry.time);
                text += '[' + t.toLocaleTimeString() + '] Exchange ' + (i + 1) + '\n';
                text += '-'.repeat(40) + '\n';
                text += 'You said: ' + entry.transcript + '\n\n';
                if (entry.summary) text += 'Summary: ' + entry.summary + '\n\n';
                if (entry.suggestions.length) {
                    text += 'Suggestions:\n';
                    entry.suggestions.forEach((s, j) => { text += '  ' + (j+1) + '. ' + s + '\n'; });
                    text += '\n';
                }
                if (entry.guidance) text += 'Guidance: ' + entry.guidance + '\n';
                text += '\n' + '='.repeat(50) + '\n\n';
            });
            const blob = new Blob([text], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'conversation-history-' + new Date().toISOString().slice(0,10) + '.txt';
            a.click();
            URL.revokeObjectURL(url);
            showToast('History exported');
        }

        // ── Copy ──
        function copySuggestion(btn, idx) {
            const entry = conversationHistory[activeHistoryIdx] || (currentExchange ? currentExchange : null);
            let text = '';
            const items = document.querySelectorAll('.suggestion-text');
            if (items[idx]) text = items[idx].textContent;
            if (!text) return;
            navigator.clipboard.writeText(text).then(() => {
                btn.textContent = 'Copied!';
                btn.classList.add('copied');
                setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 1500);
            });
        }

        // ── Settings ──
        function toggleSettings() {
            document.getElementById('settings-panel').classList.toggle('open');
            document.getElementById('settings-overlay').classList.toggle('open');
        }

        function toggleTTS(btn) {
            btn.classList.toggle('active');
            ttsEnabled = btn.classList.contains('active');
            socket.emit('toggle_tts', { enabled: ttsEnabled });
        }

        function toggleMobileHistory() {
            document.getElementById('sidebar').classList.toggle('mobile-open');
        }

        // ── Educational ──
        function toggleEducational(btn) {
            btn.classList.toggle('active');
            const enabled = btn.classList.contains('active');
            socket.emit('toggle_educational', { enabled: enabled });
            if (!enabled) {
                document.getElementById('learning-card').style.display = 'none';
            }
        }

        function showLearningInsights(data) {
            const card = document.getElementById('learning-card');
            const body = document.getElementById('learning-body');
            const hasContent = (data.vocabulary && data.vocabulary.length) || data.topic_note || data.speech_feedback || (data.follow_up_questions && data.follow_up_questions.length);
            if (!hasContent) return;

            card.style.display = 'block';
            body.innerHTML = '';

            // Vocabulary
            if (data.vocabulary && data.vocabulary.length) {
                const section = document.createElement('div');
                section.className = 'insights-section';
                section.innerHTML = '<div class="insights-section-title">&#x1F4D6; Key Vocabulary</div>';
                data.vocabulary.forEach(v => {
                    const item = document.createElement('div');
                    item.className = 'vocab-item';
                    item.innerHTML = '<span class="vocab-term">' + escapeHtml(v.term) + '</span>' +
                        '<span class="vocab-def">' + escapeHtml(v.definition) + '</span>';
                    section.appendChild(item);
                });
                body.appendChild(section);
            }

            // Topic Note
            if (data.topic_note) {
                if (body.children.length) body.appendChild(createDivider());
                const section = document.createElement('div');
                section.className = 'insights-section';
                section.innerHTML = '<div class="insights-section-title">&#x1F4A1; Topic Insight</div>' +
                    '<div class="insights-text">' + escapeHtml(data.topic_note) + '</div>';
                body.appendChild(section);
            }

            // Speech Feedback
            if (data.speech_feedback) {
                if (body.children.length) body.appendChild(createDivider());
                const section = document.createElement('div');
                section.className = 'insights-section';
                section.innerHTML = '<div class="insights-section-title">&#x1F399; Speech Feedback</div>' +
                    '<div class="insights-text">' + escapeHtml(data.speech_feedback) + '</div>';
                body.appendChild(section);
            }

            // Follow-up Questions
            if (data.follow_up_questions && data.follow_up_questions.length) {
                if (body.children.length) body.appendChild(createDivider());
                const section = document.createElement('div');
                section.className = 'insights-section';
                section.innerHTML = '<div class="insights-section-title">&#x1F914; Think Deeper</div>';
                data.follow_up_questions.forEach(q => {
                    const item = document.createElement('div');
                    item.className = 'question-item';
                    item.innerHTML = '<span class="question-icon">?</span>' +
                        '<span class="question-text">' + escapeHtml(q) + '</span>';
                    section.appendChild(item);
                });
                body.appendChild(section);
            }

            // Auto-scroll
            if (document.getElementById('autoscroll-toggle').classList.contains('active')) {
                const main = document.getElementById('main-content');
                main.scrollTo({ top: main.scrollHeight, behavior: 'smooth' });
            }
        }

        function createDivider() {
            const d = document.createElement('div');
            d.className = 'insights-divider';
            return d;
        }

        // ── Toast ──
        function showToast(msg) {
            const el = document.getElementById('toast');
            el.textContent = msg;
            el.classList.add('show');
            setTimeout(() => el.classList.remove('show'), 2500);
        }
    </script>
</body>
</html>
"""


# ──────────────────────────────────────────
#  Factory function
# ──────────────────────────────────────────

def create_display(config: dict):
    """Create the appropriate display based on configuration."""
    mode = config.get("display", {}).get("mode", "terminal")
    if mode == "web":
        display = WebDisplay(config)
        display.start()
        return display
    # "terminal" and "hdmi" both use terminal display
    return TerminalDisplay(config)
