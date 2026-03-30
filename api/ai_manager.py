"""
api/ai_manager.py
Manages all LLM API interactions for NancyTravels:
- Chat completions with function/tool calling (OpenAI or Anthropic)
- Text-to-speech (TTS) — OpenAI only
- Speech-to-text (STT / Whisper) — OpenAI only

The active LLM provider is selected via ``llm_provider`` in config.json.
Supported values: "openai", "anthropic".
"""

import json
import os
import logging

from openai import OpenAI

logger = logging.getLogger(__name__)

# Paths relative to project root
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_PATH = os.path.join(_BASE_DIR, "config.json")
_FUNCTIONS_PATH = os.path.join(_BASE_DIR, "functions", "api_functions.json")
_PROMPTS_DIR = os.path.join(_BASE_DIR, "prompts")


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

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
    """Load function definitions from functions/api_functions.json."""
    with open(_FUNCTIONS_PATH, "r") as f:
        return json.load(f)


def get_llm_provider(config: dict) -> str:
    """Return the configured LLM provider name (lower-cased)."""
    return config.get("llm_provider", "openai").lower()


# ---------------------------------------------------------------------------
# Client helpers
# ---------------------------------------------------------------------------

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


def get_anthropic_client():
    """Create and return an Anthropic client using the configured API key."""
    from anthropic import Anthropic

    config = load_config()
    api_key = config.get("anthropic", {}).get("api_key", "")
    if not api_key or api_key.startswith("YOUR_"):
        raise ValueError(
            "Anthropic API key is not configured. "
            "Please add your API key to config.json under anthropic.api_key"
        )
    return Anthropic(api_key=api_key)


# ---------------------------------------------------------------------------
# Format-conversion helpers
# ---------------------------------------------------------------------------

def _openai_functions_to_anthropic_tools(functions: list) -> list:
    """
    Convert OpenAI function definitions to Anthropic tool definitions.

    OpenAI uses ``parameters`` for the JSON schema; Anthropic uses ``input_schema``.
    """
    tools = []
    for fn in functions:
        tool = {
            "name": fn["name"],
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
        }
        tools.append(tool)
    return tools


def _openai_messages_to_anthropic(messages: list) -> tuple[str, list]:
    """
    Convert an OpenAI-format message list into an Anthropic ``(system, messages)`` pair.

    OpenAI format:
      - system message (first, role="system")
      - user/assistant turns with optional ``tool_calls`` / ``role="tool"`` entries

    Anthropic format:
      - ``system`` is a plain string passed separately
      - assistant tool-use is a content list with ``tool_use`` blocks
      - tool results are ``role="user"`` messages with ``tool_result`` content blocks
    """
    system = ""
    anthropic_messages = []

    for msg in messages:
        role = msg.get("role")

        if role == "system":
            system = msg.get("content", "")
            continue

        if role == "user":
            anthropic_messages.append({"role": "user", "content": msg["content"]})
            continue

        if role == "assistant":
            content = []
            text = msg.get("content") or ""
            if text:
                content.append({"type": "text", "text": text})
            for tc in msg.get("tool_calls", []):
                fn = tc.get("function", {})
                raw_args = fn.get("arguments", "{}")
                arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                content.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": fn.get("name", ""),
                    "input": arguments,
                })
            anthropic_messages.append({"role": "assistant", "content": content})
            continue

        if role == "tool":
            # Anthropic expects tool results as a user turn
            tool_result_block = {
                "type": "tool_result",
                "tool_use_id": msg.get("tool_call_id", ""),
                "content": msg.get("content", ""),
            }
            # Merge consecutive tool results into a single user turn
            if (
                anthropic_messages
                and anthropic_messages[-1]["role"] == "user"
                and isinstance(anthropic_messages[-1]["content"], list)
                and anthropic_messages[-1]["content"]
                and anthropic_messages[-1]["content"][0].get("type") == "tool_result"
            ):
                anthropic_messages[-1]["content"].append(tool_result_block)
            else:
                anthropic_messages.append({"role": "user", "content": [tool_result_block]})
            continue

    return system, anthropic_messages


def _parse_anthropic_response(response) -> dict:
    """
    Normalise an Anthropic ``Messages`` response into the standard result dict
    used by this module::

        {
            "content":        str,   # assistant text (may be empty)
            "function_calls": list,  # list of {id, name, arguments}
            "finish_reason":  str,   # "end_turn" | "tool_use" | …
            "role":           "assistant",
        }
    """
    text_parts = []
    function_calls = []

    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use":
            function_calls.append({
                "id": block.id,
                "name": block.name,
                "arguments": block.input,
            })

    return {
        "content": "".join(text_parts),
        "function_calls": function_calls,
        "finish_reason": response.stop_reason,
        "role": "assistant",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chat(messages: list, language: str = "en") -> dict:
    """
    Send a chat request to the configured LLM provider with tool/function calling support.

    Args:
        messages: List of conversation messages (role + content dicts).
        language: The current language code for the conversation.

    Returns:
        A dict containing:
          - 'content': The assistant's text reply (may be empty if a function was called).
          - 'function_calls': List of function calls requested by the model (may be empty).
          - 'finish_reason': The stop reason from the API.
          - 'role': Always "assistant".
    """
    config = load_config()
    provider = get_llm_provider(config)
    functions = load_api_functions()
    system_prompt = load_system_prompt()

    # Prepend system message if not already present
    if not messages or messages[0].get("role") != "system":
        messages = [{"role": "system", "content": system_prompt}] + messages

    if provider == "anthropic":
        return _chat_anthropic(messages, config, functions)

    # Default: OpenAI
    return _chat_openai(messages, config, functions)


def chat_with_function_results(
    messages: list,
    function_results: list,
    language: str = "en",
) -> dict:
    """
    Continue a chat after executing tool/function calls by sending the results back.

    Args:
        messages: Full conversation history including the assistant's function call message.
        function_results: List of dicts with 'id', 'name', and 'result' keys.
        language: The current language code.

    Returns:
        Same structure as chat().
    """
    config = load_config()
    provider = get_llm_provider(config)
    functions = load_api_functions()

    # Append tool results in OpenAI format; _chat_anthropic converts as needed.
    for fr in function_results:
        messages.append({
            "role": "tool",
            "tool_call_id": fr["id"],
            "content": json.dumps(fr["result"]),
        })

    if provider == "anthropic":
        return _chat_anthropic(messages, config, functions)

    # Default: OpenAI
    return _chat_openai(messages, config, functions)


# ---------------------------------------------------------------------------
# Provider-specific chat implementations
# ---------------------------------------------------------------------------

def _chat_openai(messages: list, config: dict, functions: list) -> dict:
    """Execute a chat completion via the OpenAI API."""
    openai_config = config["openai"]
    client = get_openai_client()

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


def _chat_anthropic(messages: list, config: dict, functions: list) -> dict:
    """Execute a chat completion via the Anthropic API."""
    anthropic_config = config.get("anthropic", {})
    client = get_anthropic_client()

    system, anthropic_messages = _openai_messages_to_anthropic(messages)
    tools = _openai_functions_to_anthropic_tools(functions)

    response = client.messages.create(
        model=anthropic_config.get("model", "claude-opus-4-5"),
        system=system,
        messages=anthropic_messages,
        tools=tools,
        max_tokens=anthropic_config.get("max_tokens", 2048),
        temperature=anthropic_config.get("temperature", 0.7),
    )

    return _parse_anthropic_response(response)


# ---------------------------------------------------------------------------
# TTS / STT (OpenAI only — Anthropic does not provide these services)
# ---------------------------------------------------------------------------

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
