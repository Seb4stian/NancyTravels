"""
api/ai_manager.py
Manages all OpenAI API interactions for NancyTravels:
- Chat completions with function calling
- Text-to-speech (TTS)
- Speech-to-text (STT / Whisper)
"""

import json
import os
import logging
from typing import Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

# Paths relative to project root
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_PATH = os.path.join(_BASE_DIR, "config.json")
_FUNCTIONS_PATH = os.path.join(_BASE_DIR, "functions", "api_functions.json")
_PROMPTS_DIR = os.path.join(_BASE_DIR, "prompts")


def load_config() -> dict:
    """Load application configuration from config.json."""
    with open(_CONFIG_PATH, "r") as f:
        return json.load(f)


def load_system_prompt() -> str:
    """Load the main system prompt from prompts/system_prompt.txt."""
    path = os.path.join(_PROMPTS_DIR, "system_prompt.txt")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_api_functions() -> list:
    """Load OpenAI function definitions from functions/api_functions.json."""
    with open(_FUNCTIONS_PATH, "r") as f:
        return json.load(f)


def get_openai_client() -> OpenAI:
    """Create and return an OpenAI client using the configured API key."""
    config = load_config()
    api_key = config["openai"]["api_key"]
    if not api_key or api_key.startswith("YOUR_"):
        raise ValueError(
            "OpenAI API key is not configured. "
            "Please add your API key to config.json under openai.api_key"
        )
    return OpenAI(api_key=api_key)


def chat(messages: list, language: str = "en") -> dict:
    """
    Send a chat request to OpenAI with function calling support.

    Args:
        messages: List of conversation messages (role + content dicts).
        language: The current language code for the conversation.

    Returns:
        A dict containing:
          - 'content': The assistant's text reply (may be empty if a function was called).
          - 'function_calls': List of function calls requested by the model (may be empty).
          - 'finish_reason': The stop reason from the API.
    """
    config = load_config()
    openai_config = config["openai"]

    client = get_openai_client()
    functions = load_api_functions()
    system_prompt = load_system_prompt()

    # Prepend system message if not already present
    if not messages or messages[0].get("role") != "system":
        messages = [{"role": "system", "content": system_prompt}] + messages

    response = client.chat.completions.create(
        model=openai_config.get("model", "gpt-4o"),
        messages=messages,
        tools=[{"type": "function", "function": fn} for fn in functions],
        tool_choice="auto",
        max_tokens=openai_config.get("max_tokens", 2048),
        temperature=openai_config.get("temperature", 0.7),
    )

    choice = response.choices[0]
    message = choice.message

    function_calls = []
    if message.tool_calls:
        for tool_call in message.tool_calls:
            function_calls.append({
                "id": tool_call.id,
                "name": tool_call.function.name,
                "arguments": json.loads(tool_call.function.arguments),
            })

    return {
        "content": message.content or "",
        "function_calls": function_calls,
        "finish_reason": choice.finish_reason,
        "role": "assistant",
    }


def chat_with_function_results(
    messages: list,
    function_results: list,
    language: str = "en"
) -> dict:
    """
    Continue a chat after executing function calls by sending the results back to OpenAI.

    Args:
        messages: Full conversation history including the assistant's function call message.
        function_results: List of dicts with 'id', 'name', and 'result' keys.
        language: The current language code.

    Returns:
        Same structure as chat().
    """
    config = load_config()
    openai_config = config["openai"]

    client = get_openai_client()
    functions = load_api_functions()

    # Add function results to the message list
    for fr in function_results:
        messages.append({
            "role": "tool",
            "tool_call_id": fr["id"],
            "content": json.dumps(fr["result"]),
        })

    response = client.chat.completions.create(
        model=openai_config.get("model", "gpt-4o"),
        messages=messages,
        tools=[{"type": "function", "function": fn} for fn in functions],
        tool_choice="auto",
        max_tokens=openai_config.get("max_tokens", 2048),
        temperature=openai_config.get("temperature", 0.7),
    )

    choice = response.choices[0]
    message = choice.message

    function_calls = []
    if message.tool_calls:
        for tool_call in message.tool_calls:
            function_calls.append({
                "id": tool_call.id,
                "name": tool_call.function.name,
                "arguments": json.loads(tool_call.function.arguments),
            })

    return {
        "content": message.content or "",
        "function_calls": function_calls,
        "finish_reason": choice.finish_reason,
        "role": "assistant",
    }


def text_to_speech(text: str) -> bytes:
    """
    Convert text to speech using OpenAI TTS.

    Args:
        text: The text to convert to speech.

    Returns:
        Audio data as bytes (MP3 format).
    """
    config = load_config()
    openai_config = config["openai"]

    client = get_openai_client()

    response = client.audio.speech.create(
        model=openai_config.get("tts_model", "tts-1"),
        voice=openai_config.get("tts_voice", "alloy"),
        input=text,
    )

    return response.content


def speech_to_text(audio_data: bytes, filename: str = "audio.webm") -> str:
    """
    Convert speech audio to text using OpenAI Whisper.

    Args:
        audio_data: The audio file bytes.
        filename: The filename with extension (used to hint the format).

    Returns:
        Transcribed text string.
    """
    import io

    client = get_openai_client()
    config = load_config()
    openai_config = config["openai"]

    audio_file = io.BytesIO(audio_data)
    audio_file.name = filename

    transcript = client.audio.transcriptions.create(
        model=openai_config.get("stt_model", "whisper-1"),
        file=audio_file,
    )

    return transcript.text
