# ✈️ NancyTravels

**NancyTravels** is an AI-powered travel planning web application. Tell Nancy your destination, budget, and group size, and she will create a personalized itinerary with restaurants, events, and attractions — complete with booking links and travel tips.

---

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.10+
- An **OpenAI API key** (required)
- Optional API keys for live data: Ticketmaster, TripAdvisor, Expedia, OpenTable

### 2. Clone & install dependencies

```bash
git clone https://github.com/Seb4stian/NancyTravels.git
cd NancyTravels
pip install -r requirements.txt
```

### 3. Configure API keys and settings

Open `config.json` and fill in your keys:

```json
{
  "openai": {
    "api_key": "sk-...",          // ← Your OpenAI key (REQUIRED)
    "model": "gpt-4o",            // ← OpenAI model to use
    "tts_voice": "alloy"          // ← TTS voice (alloy/echo/fable/onyx/nova/shimmer)
  },
  "app": {
    "default_language": "en",     // ← Initial chat language
    "secret_key": "change-me"     // ← Change for production
  },
  "external_apis": {
    "ticketmaster": { "api_key": "..." },   // optional – live events
    "opentable":    { "api_key": "..." },   // optional – live restaurants
    "tripadvisor":  { "api_key": "..." },   // optional – live attractions
    "expedia":      { "api_key": "..." }    // optional – live hotels
  }
}
```

> **Without external API keys** the app runs in demo mode, returning realistic sample data so you can explore the full UX immediately.

### 4. Run the application

```bash
python app.py
```

### 5. Open in your browser

```
http://localhost:5000
```

Use **http://localhost:5000/about** to see the About page.

---

## 🗺️ How to Use

1. **Type** your travel question in the chat box.
   - Example: *"I want to visit Barcelona for 3 days with 2 people and a $600 budget"*
2. **Or speak** — click the 🎙️ microphone button, say your question, then click again to stop.
3. Nancy will ask follow-up questions if she needs more information.
4. She will search restaurants, events, and attractions and present a complete itinerary with links.
5. The assistant speaks her reply aloud using text-to-speech.
6. The conversation adapts to the language you write in.

---

## 📁 Project Structure

```
NancyTravels/
├── app.py                     # Flask web server & API routes
├── config.json                # All configuration & API keys
├── requirements.txt           # Python dependencies
├── README.md                  # This file
├── ARCHITECTURE.md            # Full system architecture documentation
│
├── api/
│   ├── __init__.py
│   ├── ai_manager.py          # OpenAI chat / TTS / STT
│   └── external_apis.py       # Ticketmaster, OpenTable, TripAdvisor, Expedia
│
├── functions/
│   └── api_functions.json     # OpenAI function definitions (add more here)
│
├── prompts/
│   ├── system_prompt.txt      # Main AI system prompt
│   ├── clarification_prompt.txt
│   ├── itinerary_prompt.txt
│   └── off_topic_prompt.txt
│
├── templates/
│   ├── index.html             # Chat page
│   └── about.html             # About page
│
└── static/
    ├── css/
    │   ├── main.css           # Shared styles
    │   └── about.css          # About page styles
    └── js/
        └── chat.js            # Frontend chat + TTS + STT logic
```

---

## 🔧 Configuration Reference (`config.json`)

| Key | Description |
|-----|-------------|
| `openai.api_key` | **Required.** Your OpenAI API key from [platform.openai.com](https://platform.openai.com/api-keys) |
| `openai.model` | GPT model (default: `gpt-4o`) |
| `openai.tts_model` | TTS model (default: `tts-1`) |
| `openai.tts_voice` | Voice for TTS: `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer` |
| `openai.stt_model` | Whisper model (default: `whisper-1`) |
| `app.default_language` | Initial language code (e.g. `en`, `es`, `fr`) |
| `app.port` | HTTP port (default: `5000`) |
| `app.debug` | Enable Flask debug mode (`false` in production) |
| `app.secret_key` | Flask session secret — **change before deploying** |
| `external_apis.*` | Optional third-party API keys for live data |

---

## ➕ Adding More External APIs

1. Add the function definition to `functions/api_functions.json`.
2. Implement the function in `api/external_apis.py`.
3. Register it in the `FUNCTION_MAP` dictionary at the bottom of `external_apis.py`.

---

## 👥 Team

| Name | Role |
|------|------|
| Nancy Chaljub | CEO / Owner |
| Francisco Camacho Chaljub | CTO |
| Eduardo Castro Puello | AI Architect |

---

## 📄 License

MIT

