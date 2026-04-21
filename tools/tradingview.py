"""
TradingView automation tool for Alfred.

Controls TradingView in Microsoft Edge via pyautogui.
Uses keyboard shortcuts where possible for reliability.

Actions:
  open          — launch Edge → TradingView
  set_symbol    — change the chart symbol (e.g. BTCUSD, AAPL)
  set_timeframe — switch timeframe (1m 5m 15m 30m 1h 2h 4h 1D 1W 1M)
  screenshot    — capture and save the chart
  zoom          — zoom in or out on the chart
  scroll        — scroll the chart left or right
"""

import os
import base64
import time
import subprocess
import pyautogui

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3

TRADINGVIEW_URL = "https://www.tradingview.com/chart/"
SCREENSHOT_DIR  = os.path.join(os.path.expanduser("~"), "Downloads", "tv_screenshots")

# ── Timeframe keyboard shortcuts (TradingView default hotkeys) ────────────────
# These work when the chart area is focused.
_TIMEFRAME_KEYS = {
    "1m":  "1",
    "3m":  "3",
    "5m":  "5",
    "15m": "D",   # Shift+D on some layouts — see _set_timeframe_kb
    "30m": "F",
    "45m": None,
    "1h":  "G",
    "2h":  "H",
    "4h":  "J",
    "1d":  "K",
    "1w":  "L",
    "1M":  None,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ensure_screenshot_dir():
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def _focus_chart():
    """Click the center of the screen to focus the chart area."""
    w, h = pyautogui.size()
    pyautogui.click(w // 2, h // 2)
    time.sleep(0.3)


# ── Actions ───────────────────────────────────────────────────────────────────

def open_tradingview() -> str:
    """Open TradingView in Microsoft Edge."""
    try:
        edge_paths = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]
        edge = next((p for p in edge_paths if os.path.exists(p)), None)
        if edge:
            subprocess.Popen([edge, TRADINGVIEW_URL])
        else:
            # Fallback: use start command
            subprocess.Popen(["cmd", "/c", "start", "msedge", TRADINGVIEW_URL])
        time.sleep(4)  # Wait for Edge + page to load
        return "TradingView opened in Edge."
    except Exception as e:
        return f"Failed to open TradingView: {e}"


def set_symbol(symbol: str) -> str:
    """Change the chart symbol by clicking the symbol search box."""
    try:
        symbol = symbol.upper().strip()
        _focus_chart()
        time.sleep(0.3)

        # TradingView: press / or click header symbol field to open search
        pyautogui.hotkey("alt", "s")    # Opens symbol search on many TradingView layouts
        time.sleep(0.6)

        # Fallback: also try clicking the symbol area at the top-left of chart toolbar
        # (adjust these coordinates using find_coords.py if needed)
        # pyautogui.click(150, 52)
        # time.sleep(0.5)

        pyautogui.hotkey("ctrl", "a")
        pyautogui.write(symbol, interval=0.05)
        time.sleep(0.8)
        pyautogui.press("enter")
        time.sleep(1.0)

        return f"Symbol changed to {symbol}."
    except Exception as e:
        return f"Failed to set symbol: {e}"


def set_timeframe(timeframe: str) -> str:
    """Switch to a timeframe using keyboard shortcut or clicks."""
    try:
        tf = timeframe.lower().strip()
        key = _TIMEFRAME_KEYS.get(tf)

        _focus_chart()
        time.sleep(0.3)

        if key:
            pyautogui.hotkey("alt", key)
            time.sleep(0.5)
            return f"Timeframe set to {timeframe}."
        else:
            # For timeframes without shortcuts, type it in the timeframe input
            # TradingView has a timeframe box in the top toolbar — click it
            pyautogui.hotkey("alt", "t")  # some layouts open timeframe dialog
            time.sleep(0.5)
            pyautogui.hotkey("ctrl", "a")
            pyautogui.write(timeframe, interval=0.05)
            pyautogui.press("enter")
            time.sleep(0.5)
            return f"Timeframe set to {timeframe}."
    except Exception as e:
        return f"Failed to set timeframe: {e}"


def take_screenshot(label: str = "") -> str:
    """Take a screenshot of the current TradingView chart."""
    try:
        _ensure_screenshot_dir()
        ts = time.strftime("%Y%m%d_%H%M%S")
        suffix = f"_{label}" if label else ""
        filename = os.path.join(SCREENSHOT_DIR, f"chart{suffix}_{ts}.png")
        pyautogui.screenshot(filename)
        return f"Screenshot saved to {filename}"
    except Exception as e:
        return f"Screenshot failed: {e}"


def zoom(direction: str) -> str:
    """Zoom the chart in or out using scroll."""
    try:
        _focus_chart()
        clicks = 3
        if direction.lower() in ("in", "zoom in", "+"):
            pyautogui.scroll(clicks)
            return "Zoomed in on chart."
        else:
            pyautogui.scroll(-clicks)
            return "Zoomed out on chart."
    except Exception as e:
        return f"Zoom failed: {e}"


def analyze_chart(focus: str = "") -> list:
    """
    Take a screenshot of the chart and return it as image content
    for Claude's vision API to analyze.
    Returns a list of content blocks: [image, text].
    """
    try:
        _ensure_screenshot_dir()
        ts = time.strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(SCREENSHOT_DIR, f"analysis_{ts}.png")

        # Small pause so any ongoing animation settles
        time.sleep(0.5)
        pyautogui.screenshot(filepath)

        with open(filepath, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")

        if focus:
            prompt = (
                f"Analyze this TradingView chart. The user wants to focus on: {focus}. "
                "Describe the price action, what each visible indicator is showing, "
                "any signals or patterns you see, and give a clear assessment."
            )
        else:
            prompt = (
                "Analyze this TradingView chart. Describe the price action, "
                "what each visible indicator is showing (RSI, MACD, moving averages, volume, etc.), "
                "any notable patterns or signals, and give your overall assessment."
            )

        return [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": img_b64,
                },
            },
            {
                "type": "text",
                "text": prompt,
            },
        ]
    except Exception as e:
        return [{"type": "text", "text": f"Chart analysis failed: {e}"}]


def open_pine_editor() -> str:
    """Open the Pine Script editor panel in TradingView."""
    try:
        _focus_chart()
        # Alt+P opens Pine Editor on TradingView (works when chart is focused)
        pyautogui.hotkey("alt", "p")
        time.sleep(1.2)
        return "Pine Editor opened."
    except Exception as e:
        return f"Failed to open Pine Editor: {e}"


def write_pine_script(code: str) -> str:
    """Clear the Pine Editor and paste new Pine Script code."""
    try:
        # Click inside the editor area — roughly bottom third of screen
        w, h = pyautogui.size()
        pyautogui.click(w // 2, int(h * 0.75))
        time.sleep(0.4)

        # Select all existing code and replace it
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.2)

        # Use clipboard for reliable paste of multi-line code
        import subprocess
        subprocess.run(
            ["clip"],
            input=code.encode("utf-16"),
            check=True,
            shell=True,
        )
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.5)
        return "Pine Script written to editor."
    except Exception as e:
        return f"Failed to write Pine Script: {e}"


def add_to_chart() -> str:
    """Compile and add the current Pine Script to the chart (Add to chart button)."""
    try:
        # Alt+Enter submits / adds to chart in TradingView Pine Editor
        pyautogui.hotkey("alt", "Return")
        time.sleep(1.5)
        return "Script added to chart."
    except Exception as e:
        return f"Failed to add script to chart: {e}"


def load_pine_file(file_path: str) -> str:
    """Read a .pine file from disk and load it into the Pine Editor."""
    try:
        path = os.path.expanduser(file_path.strip())
        if not os.path.exists(path):
            # Try relative to Downloads
            alt = os.path.join(os.path.expanduser("~"), "Downloads", file_path.strip())
            if os.path.exists(alt):
                path = alt
            else:
                return f"File not found: {file_path}"
        with open(path, "r", encoding="utf-8") as f:
            code = f.read()
        result = write_pine_script(code)
        return f"Loaded {os.path.basename(path)} into Pine Editor. {result}"
    except Exception as e:
        return f"Failed to load Pine file: {e}"


def close_pine_editor() -> str:
    """Close / hide the Pine Editor panel."""
    try:
        pyautogui.hotkey("alt", "p")
        time.sleep(0.5)
        return "Pine Editor closed."
    except Exception as e:
        return f"Failed to close Pine Editor: {e}"


def scroll_chart(direction: str) -> str:
    """Scroll the chart left (back in time) or right (forward)."""
    try:
        _focus_chart()
        w, h = pyautogui.size()
        cx, cy = w // 2, h // 2

        if direction.lower() in ("left", "back", "backward", "past"):
            pyautogui.keyDown("shift")
            pyautogui.scroll(-5, x=cx, y=cy)
            pyautogui.keyUp("shift")
            return "Scrolled chart back in time."
        else:
            pyautogui.keyDown("shift")
            pyautogui.scroll(5, x=cx, y=cy)
            pyautogui.keyUp("shift")
            return "Scrolled chart forward."
    except Exception as e:
        return f"Scroll failed: {e}"


# ── Tool definitions (for Claude) ─────────────────────────────────────────────

TRADINGVIEW_TOOL = {
    "name": "tradingview_control",
    "description": (
        "Control TradingView in Edge browser. "
        "Use this when the user asks to open TradingView, change a chart symbol or ticker, "
        "switch timeframe, take a chart screenshot, zoom in/out, or scroll the chart. "
        "Examples: 'open TradingView', 'show me Bitcoin', 'switch to 4 hour', "
        "'take a screenshot of the chart', 'zoom in', 'go back in time'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["open", "set_symbol", "set_timeframe", "screenshot", "zoom", "scroll", "analyze",
                         "open_pine_editor", "write_pine_script", "load_pine_file", "add_to_chart", "close_pine_editor"],
                "description": "The action to perform on TradingView.",
            },
            "symbol": {
                "type": "string",
                "description": "Ticker symbol, e.g. BTCUSD, AAPL, EURUSD, NIFTY. Required for set_symbol.",
            },
            "timeframe": {
                "type": "string",
                "description": "Timeframe string: 1m 3m 5m 15m 30m 1h 2h 4h 1D 1W 1M. Required for set_timeframe.",
            },
            "direction": {
                "type": "string",
                "description": "For zoom: 'in' or 'out'. For scroll: 'left' (past) or 'right' (future).",
            },
            "label": {
                "type": "string",
                "description": "Optional label to include in the screenshot filename.",
            },
            "focus": {
                "type": "string",
                "description": "What to focus on during analysis, e.g. 'RSI and MACD signals', 'support resistance levels', 'trend direction'. Optional for analyze action.",
            },
            "code": {
                "type": "string",
                "description": "Pine Script v5 source code to write into the editor. Required for write_pine_script.",
            },
            "file_path": {
                "type": "string",
                "description": "Path to a .pine file to load into the editor. Can be absolute or relative to ~/Downloads. Required for load_pine_file.",
            },
        },
        "required": ["action"],
    },
}

TOOL_NAMES = {"tradingview_control"}
ALL_TOOLS  = [TRADINGVIEW_TOOL]


def execute(tool_name: str, tool_input: dict) -> str:
    """Dispatch a TradingView tool call."""
    if tool_name != "tradingview_control":
        return f"Unknown tool: {tool_name}"

    action = tool_input.get("action", "")

    if action == "open":
        return open_tradingview()

    elif action == "set_symbol":
        symbol = tool_input.get("symbol", "")
        if not symbol:
            return "Please provide a symbol, e.g. BTCUSD or AAPL."
        return set_symbol(symbol)

    elif action == "set_timeframe":
        tf = tool_input.get("timeframe", "")
        if not tf:
            return "Please provide a timeframe, e.g. 1h or 4h."
        return set_timeframe(tf)

    elif action == "screenshot":
        label = tool_input.get("label", "")
        return take_screenshot(label)

    elif action == "zoom":
        direction = tool_input.get("direction", "in")
        return zoom(direction)

    elif action == "scroll":
        direction = tool_input.get("direction", "left")
        return scroll_chart(direction)

    elif action == "analyze":
        focus = tool_input.get("focus", "")
        return analyze_chart(focus)  # returns list of content blocks

    elif action == "open_pine_editor":
        return open_pine_editor()

    elif action == "write_pine_script":
        code = tool_input.get("code", "")
        if not code:
            return "Please provide Pine Script code."
        return write_pine_script(code)

    elif action == "load_pine_file":
        file_path = tool_input.get("file_path", "")
        if not file_path:
            return "Please provide a file path."
        return load_pine_file(file_path)

    elif action == "add_to_chart":
        return add_to_chart()

    elif action == "close_pine_editor":
        return close_pine_editor()

    else:
        return f"Unknown TradingView action: {action}"
