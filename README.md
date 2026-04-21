# Alfred

A voice-first AI assistant powered by Claude, Whisper STT, and Edge TTS. Talk to it, type to it, and it talks back — with full tool access to the web, your Obsidian vault, TradingView, your Sony TV, and persistent memory.

## Features

- **Voice I/O** — speak naturally, Alfred responds out loud via Edge TTS
- **Whisper STT** — local speech recognition with automatic voice activity detection
- **Claude-powered** — streams responses in real time via the Anthropic API
- **Web search** — built-in, no setup needed (handled server-side by Anthropic)
- **Obsidian integration** — read, search, and write to your personal vault
- **TradingView control** — open charts, change symbols, analyze visuals, write Pine Script
- **Sony TV control** — mute, volume, power, inputs, open apps — all by voice
- **FRED macro data** — pull live US economic indicators (GDP, inflation, Fed rate, etc.)
- **Persistent memory** — trade log, facts, and session history saved to disk
- **Switchable voices** — change accent/voice mid-conversation

---

## Requirements

- Python 3.10+
- Windows (uses `msvcrt` for keyboard input and `edge-tts`)
- A working microphone
- [Anthropic API key](https://console.anthropic.com)
- (Optional) [Obsidian Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) plugin
- (Optional) Sony BRAVIA TV on the same Wi-Fi network

---

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/Byatmaan007/alfred.git
cd alfred
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables
```bash
cp .env.example .env
```
Open `.env` and fill in your keys. See the [Environment Variables](#environment-variables) section below for what each one does.

### 4. Run Alfred
```bash
python main.py
```

Alfred will load the Whisper model on first run (downloads ~140 MB), then greet you and start listening.

---

## Environment Variables

All config lives in `.env`. Copy `.env.example` to get started.

### Core (required)

| Variable | Where to get it | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | Claude API key — required for everything |

### Obsidian (optional)

| Variable | Value | Description |
|---|---|---|
| `OBSIDIAN_API_KEY` | Obsidian → Settings → Local REST API | API key from the plugin |
| `OBSIDIAN_HOST` | `127.0.0.1` | Leave as-is unless running remotely |
| `OBSIDIAN_PORT` | `27124` | Default port for the plugin |

### OpenAI TTS (optional)

Used for higher-quality voice output. Falls back to Edge TTS if not set.

| Variable | Example | Description |
|---|---|---|
| `OPENAI_API_KEY` | `sk-proj-...` | OpenAI API key |
| `OPENAI_TTS_VOICE` | `nova` | Voice name (`nova`, `alloy`, `echo`, `fable`, `onyx`, `shimmer`) |
| `OPENAI_TTS_MODEL` | `gpt-4o-mini-tts` | TTS model |

### FRED — US Economic Data (optional)

| Variable | Where to get it | Description |
|---|---|---|
| `FRED_API_KEY` | [fredaccount.stlouisfed.org/apikey](https://fredaccount.stlouisfed.org/apikey) | Free API key for macro data |

### Sony TV (optional)

Enables full voice control of your Sony BRAVIA TV.

| Variable | Example | Description |
|---|---|---|
| `TV_TYPE` | `sony` | TV brand. Options: `sony`, `roku`, `samsung`, `lg`, `android` |
| `TV_IP` | `192.168.1.50` | TV's local IP — find it in TV Settings → Network |
| `TV_PSK` | `1234` | Pre-shared key you set on the TV (Sony only) |

**Sony TV one-time setup (do this once on the TV):**
1. TV Settings → Network → find and note the IP address
2. TV Settings → Network → **IP Remote Control** → Enable
3. Set **Authentication** to *Normal and Pre-Shared Key*
4. Enter any PSK (e.g. `1234`) and put the same value in `TV_PSK`
5. For power-on from standby: Settings → Power → **Network standby** → On
6. Fill in `.env` with `TV_IP` and `TV_PSK`, then restart Alfred

---

## Usage

### Controls

| Input | Action |
|---|---|
| Just speak | Alfred detects your voice and responds |
| Type + Enter | Send a text message |
| `reset` | Clear conversation history |
| `quit` / `exit` / `q` | Exit Alfred |
| `Ctrl+C` | Force quit |

### What you can say

#### General
- *"What's the weather in Sydney?"*
- *"Search for the latest news on gold"*
- *"What time is it in New York?"*

#### Memory
- *"Remember that I prefer dark mode in all my projects"*
- *"What do you know about my trading preferences?"*
- *"Log a trade: long BTCUSD, entry 95000, exit 97500"*
- *"How am I doing on trades this month?"*

#### Obsidian
- *"Search my vault for notes on LangGraph"*
- *"Read my goals note"*
- *"Add a note to my Alfred todo: set up wake word"*

#### TradingView
- *"Open TradingView on gold 4-hour"*
- *"Take a screenshot of the chart"*
- *"Analyze the chart"*
- *"Write me a Pine Script RSI indicator"*

#### Sony TV
- *"Mute the TV"*
- *"Volume up"*
- *"Open Netflix"*
- *"Turn off the TV"*
- *"Switch to HDMI 2"*
- *"Go home on the TV"*

#### Voice
- *"Switch to a British accent"*
- *"Use a Nigerian voice"*
- *"Change your voice to something deeper"*

#### FRED Macro Data
- *"What's the current US unemployment rate?"*
- *"Pull the Fed funds rate"*
- *"Show me 10-year Treasury yields"*

---

## Memory System

Alfred has three layers of persistent memory:

| Layer | Storage | What it holds | Lifetime |
|---|---|---|---|
| **Session history** | `memory/session.json` | Last 40 conversation turns | Survives restarts |
| **Long-term facts** | `memory/chroma_db/` | Things you ask Alfred to remember — semantic vector search | Permanent |
| **Trade log** | `memory/gains.json` | Every trade you record | Permanent |

To save something permanently: *"Alfred, remember that..."*
To recall: *"What do you remember about my trading setup?"*
To clear session history: type `reset`

> **Token tip:** Session history is trimmed to the last 40 turns. The system prompt is cached by Anthropic (prompt caching). Long-term memories are only fetched on-demand. If you want lighter context, lower `MAX_TURNS` in `memory/session.py`.

---

## Project Structure

```
alfred/
├── main.py               # Entry point — VAD loop, keyboard input, main run loop
├── agent.py              # Claude API integration, tool routing, streaming
├── ui.py                 # Terminal UI components (halo animation, colors)
├── encrypt.py            # Fernet encryption utility for .env secrets
├── decrypt.py            # Fernet decryption utility
├── agents/
│   └── memory_agent.py   # Persistent memory tools (facts, trades, semantic search)
├── tools/
│   ├── obsidian.py       # Obsidian vault read/write/search
│   ├── tradingview.py    # TradingView browser control + Pine Script editor
│   ├── tv.py             # Sony/Roku/Samsung/LG/Android TV remote control
│   ├── fred.py           # FRED US macro economic data
│   └── alfred_control.py # Runtime settings (voice switching)
├── voice/
│   ├── stt.py            # Whisper speech-to-text
│   ├── tts.py            # Edge TTS / OpenAI TTS text-to-speech
│   └── wake.py           # Wake word detection
├── memory/
│   ├── session.py        # Conversation history persistence
│   ├── vector.py         # ChromaDB vector store for long-term facts
│   ├── gains.py          # Trade log (JSON)
│   └── session.json      # Auto-created, gitignored
├── .env.example          # Template for all environment variables
├── requirements.txt
└── README.md
```

---

## Customising Alfred

Alfred's personality, knowledge context, and tool instructions all live in `SYSTEM_PROMPT` inside `agent.py`. Edit it to match your own context — your name, projects, preferences, and Obsidian vault layout.

To add a new tool:
1. Create `tools/mytool.py` with an `execute(tool_name, tool_input)` function, a `TOOL_NAMES` set, and an `ALL_TOOLS` list (Claude tool schema)
2. Import it in `agent.py` and add it to `_CLIENT_TOOLS`, `_TOOLS`, and `_dispatch`
3. Add a "when to use" instruction block to `SYSTEM_PROMPT`

---

## Dependencies

| Package | Purpose |
|---|---|
| `anthropic` | Claude API client |
| `openai-whisper` | Local speech recognition |
| `edge-tts` | Microsoft neural TTS |
| `openai` | OpenAI TTS (optional higher-quality voice) |
| `sounddevice` | Microphone input |
| `pygame` | Audio playback |
| `rich` | Terminal UI |
| `python-dotenv` | Environment variable loading |
| `requests` | HTTP for TV/FRED/Obsidian tool calls |
| `chromadb` | Vector store for long-term memory |
| `sentence-transformers` | Embeddings for semantic memory search |

---

## License

MIT
