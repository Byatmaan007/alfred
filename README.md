# Alfred

A voice-first AI assistant powered by Claude, Whisper STT, and Edge TTS. Talk to it, type to it, and it talks back — with full tool access to the web, your Obsidian vault, TradingView, and persistent memory.

## Features

- **Voice I/O** — speak naturally, Alfred responds out loud via Edge TTS
- **Whisper STT** — local speech recognition with automatic voice activity detection
- **Claude-powered** — streams responses in real time via the Anthropic API
- **Web search** — built-in, no setup needed (handled server-side by Anthropic)
- **Obsidian integration** — read, search, and write to your personal vault
- **TradingView control** — open charts, change symbols, analyze visuals
- **Persistent memory** — trade log, facts, and session history saved to disk
- **Switchable voices** — change accent/voice mid-conversation

## Requirements

- Python 3.10+
- Windows (uses `msvcrt` for keyboard input and `edge-tts`)
- A working microphone
- [Anthropic API key](https://console.anthropic.com)
- (Optional) [Obsidian Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) plugin

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/YOUR_USERNAME/alfred.git
cd alfred
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Configure environment variables**
```bash
cp .env.example .env
```
Edit `.env` and fill in your keys:
```
ANTHROPIC_API_KEY=your_key_here
OBSIDIAN_API_KEY=your_key_here   # optional
```

**4. Run Alfred**
```bash
python main.py
```

Alfred will load the Whisper model on first run (downloads ~140 MB), then greet you and start listening.

## Usage

| Input | Action |
|-------|--------|
| Just speak | Alfred detects your voice automatically |
| Type + Enter | Send a text message |
| `reset` | Clear conversation history |
| `quit` / `exit` / `q` | Exit Alfred |
| `Ctrl+C` | Force quit |

### Changing voice
Say something like *"switch to a British accent"* or *"use a Nigerian voice"* and Alfred will change its TTS voice on the fly.

## Project Structure

```
alfred/
├── main.py          # Entry point — VAD loop, keyboard input, main run loop
├── agent.py         # Claude API integration, tool routing, streaming
├── ui.py            # Terminal UI components (halo animation, colors)
├── agents/
│   └── memory_agent.py   # Persistent memory tools (facts, trades, search)
├── tools/
│   ├── obsidian.py        # Obsidian vault read/write/search
│   ├── tradingview.py     # TradingView browser control
│   └── alfred_control.py  # Runtime settings (voice switching)
├── voice/
│   ├── stt.py     # Whisper speech-to-text
│   ├── tts.py     # Edge TTS text-to-speech
│   └── wake.py    # Wake word detection
├── memory/        # Session history (auto-created, gitignored)
├── requirements.txt
└── .env.example
```

## Customising the System Prompt

Alfred's personality, knowledge, and tool instructions live in `SYSTEM_PROMPT` inside `agent.py`. Edit it to match your own context — your name, projects, preferences, and Obsidian vault layout.

## Dependencies

| Package | Purpose |
|---------|---------|
| `anthropic` | Claude API client |
| `openai-whisper` | Local speech recognition |
| `edge-tts` | Microsoft neural TTS |
| `sounddevice` | Microphone input |
| `pygame` | Audio playback |
| `rich` | Terminal UI |
| `python-dotenv` | Environment variable loading |

## License

MIT
