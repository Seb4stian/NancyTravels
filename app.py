"""
app.py
NancyTravels - Main Flask web application.
Provides routes for the chat interface, TTS, STT, and the About page.
"""

import json
import logging
import os
from flask import Flask, render_template, request, jsonify, Response

from api import ai_manager, external_apis

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(__name__)

# Load configuration
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_CONFIG_PATH = os.path.join(_BASE_DIR, "config.json")

with open(_CONFIG_PATH, "r") as _f:
    _config = json.load(_f)

app.secret_key = _config["app"].get("secret_key", "change-me")
DEFAULT_LANGUAGE = _config["app"].get("default_language", "en")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Render the main chat page."""
    return render_template("index.html", default_language=DEFAULT_LANGUAGE)


@app.route("/about")
def about():
    """Render the About page."""
    team = [
        {
            "name": "Nancy Chaljub",
            "title": "CEO / Owner",
            "description": (
                "Visionary entrepreneur and travel enthusiast who founded NancyTravels "
                "with the mission of making personalized travel planning accessible to everyone."
            ),
            "icon": "👩‍💼"
        },
        {
            "name": "Francisco Camacho Chaljub",
            "title": "CTO",
            "description": (
                "Technology leader driving the engineering behind NancyTravels, "
                "ensuring a seamless and reliable experience for every traveler."
            ),
            "icon": "👨‍💻"
        },
        {
            "name": "Eduardo Castro Puello",
            "title": "AI Architect",
            "description": (
                "Expert in artificial intelligence and conversational systems, "
                "designing the smart travel planning engine that powers NancyTravels."
            ),
            "icon": "🤖"
        },
    ]
    return render_template("about.html", team=team)


@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Handle a chat message from the user.

    Expected JSON body:
    {
        "message": "string",
        "history": [ {"role": "user"|"assistant", "content": "string"}, ... ],
        "language": "en"   // optional, defaults to config default
    }

    Returns JSON:
    {
        "reply": "string",
        "language": "string"
    }
    """
    data = request.get_json(silent=True) or {}
    user_message = data.get("message", "").strip()
    history = data.get("history", [])
    language = data.get("language", DEFAULT_LANGUAGE)

    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    # Build messages list for the LLM
    messages = list(history)
    messages.append({"role": "user", "content": user_message})

    try:
        # First call to the LLM (may return function/tool calls)
        result = ai_manager.chat(messages, language=language)

        # Handle function calls in a loop (model may chain multiple calls)
        max_iterations = 5
        iteration = 0
        while result["function_calls"] and iteration < max_iterations:
            iteration += 1
            # Append the assistant's function-call message to history
            assistant_msg = {
                "role": "assistant",
                "content": result["content"],
                "tool_calls": [
                    {
                        "id": fc["id"],
                        "type": "function",
                        "function": {
                            "name": fc["name"],
                            "arguments": json.dumps(fc["arguments"]),
                        },
                    }
                    for fc in result["function_calls"]
                ],
            }
            messages.append(assistant_msg)

            # Execute each requested function
            function_results = []
            for fc in result["function_calls"]:
                logger.info(f"Executing function: {fc['name']} with args: {fc['arguments']}")
                api_result = external_apis.execute_function(fc["name"], fc["arguments"])
                function_results.append({
                    "id": fc["id"],
                    "name": fc["name"],
                    "result": api_result,
                })

            # Send results back to the LLM for a final answer
            result = ai_manager.chat_with_function_results(
                messages, function_results, language=language
            )

        return jsonify({
            "reply": result["content"],
            "language": language,
        })

    except ValueError as e:
        # API key not configured or similar configuration error
        logger.error(f"Configuration error: {e}")
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        return jsonify({"error": "An error occurred processing your request. Please try again."}), 500


@app.route("/api/tts", methods=["POST"])
def text_to_speech():
    """
    Convert text to speech using OpenAI TTS.

    Expected JSON body:
    {
        "text": "string"
    }

    Returns: audio/mpeg stream
    """
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()

    if not text:
        return jsonify({"error": "Text is required"}), 400

    # Limit text length to avoid excessive API usage
    if len(text) > 4096:
        text = text[:4096]

    try:
        audio_bytes = ai_manager.text_to_speech(text)
        return Response(
            audio_bytes,
            mimetype="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=speech.mp3"},
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        logger.error(f"TTS error: {e}", exc_info=True)
        return jsonify({"error": "TTS service unavailable"}), 500


@app.route("/api/stt", methods=["POST"])
def speech_to_text():
    """
    Convert uploaded audio to text using OpenAI Whisper.

    Expected: multipart/form-data with 'audio' file field.

    Returns JSON:
    {
        "transcript": "string"
    }
    """
    if "audio" not in request.files:
        return jsonify({"error": "Audio file is required"}), 400

    audio_file = request.files["audio"]
    audio_data = audio_file.read()
    filename = audio_file.filename or "audio.webm"

    try:
        transcript = ai_manager.speech_to_text(audio_data, filename=filename)
        return jsonify({"transcript": transcript})
    except ValueError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        logger.error(f"STT error: {e}", exc_info=True)
        return jsonify({"error": "Speech-to-text service unavailable"}), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    host = _config["app"].get("host", "0.0.0.0")
    port = _config["app"].get("port", 5000)
    debug = _config["app"].get("debug", False)
    logger.info(f"Starting NancyTravels on http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)
