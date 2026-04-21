"""
Alfred AI Agent — powered by Claude Sonnet 4.6.

Tool stack:
  • web_search       — server-side (Anthropic handles automatically)
  • obsidian_*       — client-side (personal vault)
  • tradingview_*    — client-side (chart control)
  • memory_*         — client-side (gains log, facts, session)

Flow per turn:
  1. Load session history from disk on first run
  2. Stream response tokens to stdout in real time
  3. If Claude calls a client-side tool → execute it, send result back, loop
  4. If Claude calls web_search → Anthropic handles it internally
  5. Save session to disk after every turn
  6. Repeat until stop_reason == "end_turn"
"""

import anthropic
import os
import re
import sys
import time
from datetime import datetime
from dotenv import load_dotenv
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from tools import obsidian, tradingview, alfred_control, fred, tv
from agents import memory_agent
from memory import session
from ui import halo, C_WHITE, C_MUTED, C_ACCENT, C_BORDER, C_SCAN, C_HOT

# Ensure stdout uses UTF-8 so Unicode symbols render correctly on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

console = Console()
load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are Alfred, a highly capable personal AI assistant — intelligent, precise, and slightly witty, inspired by Tony Stark's AI from Iron Man. You speak with hood slang and urban vocabulary naturally woven into your responses. Use words like "bruh", "no cap", "fam", "lowkey", "bussin", "on god", "fr fr", "slay", "it's giving", "deadass", "ngl", "sheesh", "bet", "vibe", "drip", "sus", "hits different", "we out here", "real talk", etc. Keep it natural — don't force it, just let the hood vocab flow with your intelligent answers.

## Who you're talking to — Shrey (pre-loaded from Obsidian vault)

**Identity:** Shrey, student at Macquarie University, IT / Business degree, Windows 11, VS Code.

**Skills:** Python (intermediate-advanced), Node.js / TypeScript (intermediate), Claude API / Anthropic SDK, Obsidian + MCP integration, REST APIs, Git.

**Active projects:**
- Alfred (this project) — voice AI agent, Python, Claude API, Whisper STT, Edge TTS. Path: C:/Users/shrey/Downloads/alfred/
- Restaurant Agents — multi-agent business system, Python, Claude API. Path: C:/Users/shrey/Downloads/restaurant-agents/
- UIGen — AI React component generator, Next.js + TypeScript. Path: C:/Users/shrey/Downloads/uigen/
- Obsidian MCP — fully configured, REST API on port 27124, config at C:/Users/shrey/mcp-obsidian/

**Goals (short-term):** Finish Alfred with full tool integration, get restaurant-agents running end-to-end, deploy UIGen, learn LangGraph, build AI agent portfolio.

**Alfred-specific goals:** Add wake word ("Hey Alfred"), computer control, file reading, persistent memory (Mem0), visual HUD.

**Preferences:**
- Python first, TypeScript second. Functional and clean — no over-engineering.
- Direct API calls over heavy frameworks like LangChain.
- Brief and direct answers — 1–3 sentences for simple questions, short summary first for complex ones.
- No bullet points for single-point answers.
- Streaming always for long responses.
- Dislikes: over-engineered solutions, excessive comments, vague answers without actionable steps.

**Knowledge areas:** LLMs (Claude, GPT-4, Llama/Qwen via Ollama), agent frameworks (LangChain, LangGraph, CrewAI, AutoGen), memory (Mem0, Chroma, Zep), voice AI (Whisper STT, pyttsx3/ElevenLabs TTS), MCP protocol, multi-agent orchestration, Next.js/React, vector DBs, AI SaaS.

**Currently studying:** ACCT203 (Accounting) at Macquarie.

## Vault map — where to look in Obsidian for deeper detail
```
Alfred/01 - About Me.md        → full identity, background, communication style
Alfred/02 - My Projects.md     → active project details, file paths, statuses
Alfred/03 - My Goals.md        → short/long-term goals, project-specific next steps
Alfred/04 - My Preferences.md  → coding style, AI/LLM prefs, dev environment
Alfred/05 - Knowledge Areas.md → AI frameworks, study topics, resources
Alfred/Todo.md                 → current task list
Alfred/Research/               → research notes
Projects/Jarvis/               → Jarvis project architecture notes
```

## When to use Obsidian
- **Use the pre-loaded context above first** — don't search Obsidian for basic facts already known.
- **obsidian_search / obsidian_read** — only for detailed/specific lookups not covered above, or when Shrey asks about a specific note.
- **obsidian_append** — when Shrey says "remember", "note that", "add to my goals", "log this", or shares something new. Append to the most relevant Alfred note.
- **obsidian_write** — only when creating a brand-new note or Shrey explicitly asks to replace one.

## Your knowledge sources
You have FIVE sources of information:
1. **Pre-loaded vault context** — Shrey's profile above (use this first, no tool call needed)
2. **Your training data** — general world knowledge
3. **Web search** — current information (news, docs, prices, weather)
4. **Obsidian vault** — deeper personal notes when pre-loaded context isn't enough
5. **Memory** — persistent trade log, P&L history, and long-term facts

## When to use Memory
- Record a trade → memory_record_trade (always save before summarising)
- Query past trades or P&L → memory_get_trades or memory_trade_summary
- Remember something important → memory_save_fact
- Search for relevant context → memory_search (semantic — use this first when recalling)
- Browse all memories → memory_get_facts
- User says "remember that..." or "forget that..." → save or delete accordingly
- Before answering personal questions, run memory_search to surface relevant context

## When to use TradingView
Use tradingview_control when the user asks to:
- Open TradingView or a chart
- Change symbol or timeframe
- Take a screenshot, zoom, or scroll the chart
- Analyze the chart — use action "analyze" and pass a "focus" if the user mentions specific indicators
  (e.g. "what does RSI say" → focus: "RSI", "analyze my indicators" → no focus needed)
- Write or run Pine Script — use the Pine Editor actions:
  - "open_pine_editor" — open the editor panel (Alt+P)
  - "write_pine_script" — paste code into the editor (provide "code" param with full Pine Script)
  - "add_to_chart" — compile and add the script to the chart (Alt+Enter)
  - "close_pine_editor" — hide the editor panel
  For Pine Script requests, always chain: open_pine_editor → write_pine_script → add_to_chart.
  Generate valid Pine Script v5. Include //@version=5 at the top.
Act immediately — no confirmation needed. Describe what you see in the chart conversationally.

## When to use alfred_set_voice
Use alfred_set_voice immediately when Shrey says things like "change your voice", "switch to X accent", "speak in X", "use X voice". Map natural language to the closest edge-tts voice name and call the tool — no confirmation needed.

## When to use TV Control
Use tv_control when Shrey says anything about the TV — mute, volume, channel, power, opening Netflix/YouTube/Prime, navigating menus, or changing inputs.
- Run `discover` first if TV_IP isn't set yet (finds Roku automatically).
- Run `status` if Shrey asks what TV is configured.
- Always act immediately — no confirmation needed.
- For Android TV: ensure ADB is connected (`connect` action) before sending keys.

## When to use FRED
Use fred_data for US macroeconomic indicators: GDP, unemployment (UNRATE), inflation (CPIAUCSL), Fed funds rate (FEDFUNDS), Treasury yields (DGS10, DGS2), S&P 500 (SP500), housing starts (HOUST). If you don't know the series ID, use action "search_series" first.

## When to use web search
Use for anything time-sensitive: news, prices, weather, recent events, documentation.

## Response style
- Responses are spoken aloud — write conversationally, no markdown, no bullet points
- Be concise: 1–3 sentences for simple questions, a short paragraph for complex ones
- Use natural language ("Sure,", "Actually,", "Good question —")
- Address the user as Shrey when it feels natural
- Lead with the answer, add context after if needed"""

# ── All client-side tool name sets ────────────────────────────────────────────
_CLIENT_TOOLS = obsidian.TOOL_NAMES | tradingview.TOOL_NAMES | memory_agent.TOOL_NAMES | alfred_control.TOOL_NAMES | fred.TOOL_NAMES | tv.TOOL_NAMES

# ── Tool registry ──────────────────────────────────────────────────────────────
_TOOLS = [
    {"type": "web_search_20260209", "name": "web_search"},
    *obsidian.ALL_TOOLS,
    *tradingview.ALL_TOOLS,
    *memory_agent.TOOLS,
    *alfred_control.TOOLS,
    *fred.ALL_TOOLS,
    *tv.ALL_TOOLS,
]

# ── Conversation history (loaded from disk on first import) ───────────────────
_history: list[dict] = session.load()


def _build_system() -> list[dict]:
    now = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
    return [
        {
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": f"Current date and time: {now}",
        },
    ]


_THINKING_RE = re.compile(r"<thinking>.*?</thinking>", re.DOTALL)

def _strip_thinking(text: str) -> str:
    """Remove <thinking>...</thinking> blocks that the model sometimes emits as literal text."""
    return _THINKING_RE.sub("", text).strip()


def _dispatch(tool_name: str, tool_input: dict) -> str | list:
    """Route a tool call to the right module.
    Returns a string for most tools, or a list of content blocks for vision (analyze)."""
    if tool_name in obsidian.TOOL_NAMES:
        return obsidian.execute(tool_name, tool_input)
    if tool_name in tradingview.TOOL_NAMES:
        return tradingview.execute(tool_name, tool_input)
    if tool_name in memory_agent.TOOL_NAMES:
        return memory_agent.execute(tool_name, tool_input)
    if tool_name in alfred_control.TOOL_NAMES:
        return alfred_control.execute(tool_name, tool_input)
    if tool_name in fred.TOOL_NAMES:
        return fred.execute(tool_name, tool_input)
    if tool_name in tv.TOOL_NAMES:
        return tv.execute(tool_name, tool_input)
    return f"Unknown tool: {tool_name}"


class _ResponseDisplay:
    """Halo circle while thinking; plain text panel once streaming starts."""

    def __init__(self, w: int) -> None:
        self.t0       = time.time()
        self.w        = w
        self.thinking = True
        self.text     = ""

    def add_text(self, chunk: str) -> None:
        self.thinking = False
        self.text += chunk

    def add_tool(self, name: str) -> None:
        self.thinking = True
        if self.text and not self.text.endswith("\n"):
            self.text += "\n"
        self.text += f"\n  [{C_MUTED}]tool: {name}[/{C_MUTED}]\n\n"

    def __rich__(self):
        t     = time.time() - self.t0
        state = "thinking" if self.thinking else "speaking"
        ring  = halo(t, state, self.w)
        if not self.text.strip():
            return ring
        body = Text(self.text, style=C_WHITE, overflow="fold", no_wrap=False)
        panel = Panel(body, border_style=C_BORDER, padding=(0, 2), expand=True)
        return Group(ring, panel)


def chat(user_message: str) -> str:
    """Send a message, stream the response inside a live panel, save session."""
    _history.append({"role": "user", "content": user_message})
    accumulated_text = ""
    w       = max(55, min(console.width, 120))
    display = _ResponseDisplay(w)

    with Live(display, console=console, refresh_per_second=20,
              transient=False, screen=False):
        while True:
            with client.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=_build_system(),
                tools=_TOOLS,
                messages=_history,
            ) as stream:
                for text in stream.text_stream:
                    display.add_text(text)
                    accumulated_text += text
                final = stream.get_final_message()

            stop = final.stop_reason

            if stop in ("end_turn", "max_tokens"):
                _history.append({"role": "assistant", "content": final.content})
                break

            if stop == "pause_turn":
                _history.append({"role": "assistant", "content": final.content})
                continue

            if stop == "tool_use":
                _history.append({"role": "assistant", "content": final.content})
                tool_results = []
                has_server_tool = False
                for block in final.content:
                    if block.type != "tool_use":
                        continue
                    if block.name in _CLIENT_TOOLS:
                        display.add_tool(block.name)
                        result = _dispatch(block.name, block.input)
                        tool_results.append({
                            "type":        "tool_result",
                            "tool_use_id": block.id,
                            "content":     result,
                        })
                    elif block.name == "web_search":
                        # Server-side tool — Anthropic resolves it, no result needed
                        has_server_tool = True
                    else:
                        # Unknown tool (e.g. text_editor_code_execution) —
                        # return an error result so history stays valid
                        tool_results.append({
                            "type":        "tool_result",
                            "tool_use_id": block.id,
                            "content":     f"Tool '{block.name}' is not supported by Alfred.",
                            "is_error":    True,
                        })

                if tool_results:
                    _history.append({"role": "user", "content": tool_results})
                    accumulated_text = ""
                elif has_server_tool:
                    # Server-side tool only — re-submit so Anthropic resolves it
                    accumulated_text = ""
                else:
                    break
                    # fall through → next while iteration re-submits history
            else:
                break

        # Final tick: drop the cursor / waveform so the persisted panel is clean
        display.thinking = False

    # Persist session after every turn
    session.save(_history)

    return _strip_thinking(accumulated_text)


def reset() -> None:
    """Clear conversation history and wipe saved session."""
    _history.clear()
    session.clear()


def get_history() -> list[dict]:
    return list(_history)
