# NancyTravels – System Architecture Documentation

## 1. Overview

NancyTravels is an AI-powered travel planning web application that uses OpenAI's GPT models to interpret natural-language queries about city activities and generate personalized itineraries. The system integrates with external travel APIs (OpenTable, Ticketmaster, TripAdvisor, Expedia) via OpenAI Function Calling to retrieve real-time data, then presents a curated, budget-optimized itinerary with booking links.

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          User's Browser                             │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  HTML (templates/index.html, templates/about.html)           │  │
│  │  CSS  (static/css/main.css, static/css/about.css)            │  │
│  │  JS   (static/js/chat.js)                                    │  │
│  │                                                              │  │
│  │  • Text input / send                                         │  │
│  │  • Voice recording (MediaRecorder API)  ──────────────────┐  │  │
│  │  • TTS playback (Audio API)  ◄────────────────────────────┘  │  │
│  └────────────────────────────┬─────────────────────────────────┘  │
└───────────────────────────────│─────────────────────────────────────┘
                                │  HTTP (JSON / multipart)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Flask Web Server (app.py)                    │
│                                                                     │
│   GET  /                 → render index.html                        │
│   GET  /about            → render about.html                        │
│   POST /api/chat         → orchestrate AI + function calls          │
│   POST /api/tts          → convert text → MP3 audio                 │
│   POST /api/stt          → convert audio → transcript text          │
└───────────┬─────────────────────────────────┬───────────────────────┘
            │                                 │
            ▼                                 ▼
┌───────────────────────┐         ┌───────────────────────────────────┐
│   api/ai_manager.py   │         │     api/external_apis.py          │
│                       │         │                                   │
│  • chat()             │ ──────► │  • search_restaurants()           │
│  • chat_with_         │ ◄────── │  • search_events()                │
│    function_results() │         │  • search_attractions()           │
│  • text_to_speech()   │         │  • search_hotels()                │
│  • speech_to_text()   │         │  • get_city_info()                │
└───────────┬───────────┘         └───────────────────────────────────┘
            │                                 │
            ▼                                 ▼
┌───────────────────────┐         ┌───────────────────────────────────┐
│   OpenAI Platform     │         │     External Travel APIs          │
│                       │         │                                   │
│  • GPT-4o (chat)      │         │  • OpenTable  (restaurants)       │
│  • TTS-1  (speech)    │         │  • Ticketmaster (events)          │
│  • Whisper (STT)      │         │  • TripAdvisor (attractions)      │
└───────────────────────┘         │  • Expedia    (hotels)            │
                                  └───────────────────────────────────┘
```

---

## 3. Component Descriptions

### 3.1 `app.py` – Flask Web Server

The entry point of the application. Responsibilities:

- Serves HTML pages via Flask's Jinja2 template engine.
- Exposes three JSON API endpoints:
  - `POST /api/chat` – receives a user message and conversation history, runs the AI reasoning loop (with function calling), and returns the assistant's reply.
  - `POST /api/tts` – receives plain text and returns MP3 audio.
  - `POST /api/stt` – receives an audio file and returns the transcribed text.
- Loads `config.json` at startup for host/port/language settings.
- Orchestrates the function-calling loop: after calling `ai_manager.chat()`, if the model requests external API calls, `app.py` executes them via `external_apis.execute_function()` and sends results back to the model with `ai_manager.chat_with_function_results()`.

### 3.2 `api/ai_manager.py` – AI Manager

Single responsibility: all communication with the OpenAI API.

| Function | Description |
|----------|-------------|
| `chat(messages, language)` | Calls GPT with the system prompt and function definitions loaded from `functions/api_functions.json`. Returns the model's reply or a list of function calls. |
| `chat_with_function_results(messages, function_results, language)` | Continues a conversation by appending tool result messages and getting a final reply. |
| `text_to_speech(text)` | Calls the OpenAI TTS API and returns MP3 bytes. |
| `speech_to_text(audio_data, filename)` | Calls OpenAI Whisper and returns the transcript string. |

Configuration (model, voice, token limits) is read from `config.json`. The system prompt is read from `prompts/system_prompt.txt`.

### 3.3 `api/external_apis.py` – External API Manager

Implements the actual external API calls that correspond to the OpenAI function definitions. Each function:
1. Reads API credentials from `config.json`.
2. Attempts a live API call.
3. Falls back to realistic demo data if the key is not configured or the call fails.
4. Returns a structured dict that the AI can summarize for the user.

The `execute_function(name, arguments)` dispatcher maps function names to Python callables, allowing `app.py` to execute any tool the model requests without knowing the implementation.

### 3.4 `functions/api_functions.json` – OpenAI Function Definitions

Declarative JSON array of function schemas passed to the OpenAI API as `tools`. Each entry contains:
- `name` – must match a key in `FUNCTION_MAP` in `external_apis.py`.
- `description` – natural-language description read by the model to decide when to call the function.
- `parameters` – JSON Schema defining the function's inputs.

Adding a new external API requires only:
1. Adding an entry here.
2. Implementing the corresponding function in `external_apis.py`.

### 3.5 `prompts/` – Prompt Files

All prompts are stored as plain text files so they can be edited without touching Python code.

| File | Purpose |
|------|---------|
| `system_prompt.txt` | Main system prompt defining Nancy's persona, capabilities, and behavior rules (focus on travel only, language matching, etc.) |
| `clarification_prompt.txt` | Template for asking the user for missing information |
| `itinerary_prompt.txt` | Template structure for presenting a completed itinerary |
| `off_topic_prompt.txt` | Response when the user asks about non-travel topics |

### 3.6 `config.json` – Configuration

Central configuration file containing:
- OpenAI model names, API key, TTS voice, token limits
- App settings: default language, host, port, debug flag, Flask secret key
- External API keys and base URLs for all integrated services

> **Security note**: This file contains API keys. Never commit real keys to version control. In production, use environment variables or a secrets manager.

### 3.7 `templates/` – HTML Templates

Rendered by Flask's Jinja2 engine.

| File | Description |
|------|-------------|
| `index.html` | Main chat page with the message list, text input, and mic button |
| `about.html` | Company about page with team bios and feature highlights |

### 3.8 `static/css/` – Stylesheets

| File | Description |
|------|-------------|
| `main.css` | Shared styles: navbar, hero, chat bubbles, input area, footer, responsive layout |
| `about.css` | About page-specific styles: team cards, feature grid, hero variant |

### 3.9 `static/js/chat.js` – Frontend JavaScript

Client-side single-file module (IIFE pattern) handling:

- **Chat flow**: captures user input, POSTs to `/api/chat`, renders replies.
- **Markdown rendering**: lightweight renderer (no library dependency) for headings, bold, italic, lists, code blocks, and clickable links.
- **TTS**: calls `/api/tts`, creates a blob URL, and plays the response audio.
- **STT**: uses the browser's `MediaRecorder` API to capture microphone audio, uploads to `/api/stt`, and injects the transcript into the input field.
- **Language**: tracks the current language and passes it on each request.
- **State management**: maintains `conversationHistory` array sent with each request for context continuity.

---

## 4. Data Flow – Chat Request

```
User types/speaks → chat.js collects input
        │
        ▼
POST /api/chat  {message, history, language}
        │
        ▼  app.py
Build messages list  +  load system prompt
        │
        ▼  ai_manager.chat()
OpenAI GPT-4o (with function tools)
        │
   ┌────┴────────────────────┐
   │ finish_reason = "stop"  │ finish_reason = "tool_calls"
   │                         │
   ▼                         ▼
Return text reply     For each tool call:
        │              execute_function(name, args)
        │                      │
        │              external_apis.py → Travel API
        │                      │
        │              ai_manager.chat_with_function_results()
        │                      │
        │              OpenAI GPT-4o synthesizes results → text
        │                      │
        └──────────────────────┘
                    │
                    ▼
        JSON response  {reply, language}
                    │
                    ▼  chat.js
        Render Markdown in bubble
        Play TTS audio
```

---

## 5. Voice Flow

```
User clicks 🎙️ → MediaRecorder starts
User clicks 🎙️ again → recording stops
        │
        ▼
Blob (audio/webm) POSTed to POST /api/stt
        │
        ▼  app.py → ai_manager.speech_to_text()
OpenAI Whisper transcribes audio → text
        │
        ▼  chat.js
Text injected into input → handleSend() triggered
```

---

## 6. Language Support

- The `default_language` setting in `config.json` determines the language of Nancy's first greeting.
- On every chat request, the current language code is sent to the server.
- The system prompt instructs the model to respond in the same language as the user's latest message, so the conversation naturally follows the user's language choice.

---

## 7. Function-Calling Extension Points

To add a new travel data source:

1. **Add the function definition** to `functions/api_functions.json` (name, description, parameters schema).
2. **Implement the function** in `api/external_apis.py`.
3. **Register it** in the `FUNCTION_MAP` dict at the bottom of `external_apis.py`.
4. **Add API credentials** to `config.json` under `external_apis`.

No changes to `app.py` or `ai_manager.py` are required.

---

## 8. Security Considerations

- API keys are stored in `config.json` and never exposed to the browser.
- The system prompt strictly limits the AI to travel-related topics.
- TTS text input is capped at 4096 characters to prevent abuse.
- Flask's `secret_key` should be changed before production deployment.
- In production, serve the application behind HTTPS (e.g., with nginx + gunicorn).
- Consider rate-limiting `/api/chat`, `/api/tts`, and `/api/stt` endpoints.

---

## 9. Deployment Notes

For production use:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

Set `"debug": false` in `config.json` before deploying.

---

*Document generated for NancyTravels v1.0*
