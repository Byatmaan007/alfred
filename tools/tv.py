"""
TV remote control tool for Alfred.

Supports: Sony BRAVIA (IRCC-IP), Roku, Samsung (WebSocket), LG WebOS, Android TV (ADB).

Configure in .env:
  TV_TYPE = sony | roku | samsung | lg | android
  TV_IP   = 192.168.1.x
  TV_PSK  = 1234          (Sony only — Pre-Shared Key set in TV network settings)
  TV_NAME = Living Room TV (optional, for Samsung pairing)

Sony setup:
  1. On TV: Settings > Network > IP remote control → Enable
  2. Set "Authentication" to "Normal and Pre-Shared Key"
  3. Enter a PSK (e.g. 1234) and put the same in TV_PSK in .env
  4. For power-on from standby: Settings > System > Power > "Network standby" → On

For Android TV / Sony Android:
  Enable Developer Options → USB debugging → enable ADB over network (port 5555)
  Then run: adb connect <TV_IP>:5555
"""

from __future__ import annotations

import os
import subprocess
import time
import requests
from dotenv import load_dotenv

load_dotenv()

TV_TYPE: str = os.getenv("TV_TYPE", "").lower().strip()
TV_IP:   str = os.getenv("TV_IP",   "").strip()
TV_NAME: str = os.getenv("TV_NAME", "Alfred").strip()
TV_PSK:  str = os.getenv("TV_PSK",  "").strip()  # Sony Pre-Shared Key

TOOL_NAMES = {"tv_control"}

# ── Sony BRAVIA IRCC-IP codes ─────────────────────────────────────────────────
# These Base64-encoded codes are the IR commands sent over the network.
# Supported on all BRAVIA models (2013+). Older models may not need the PSK header.

_SONY_IRCC: dict[str, str] = {
    "power":        "AAAAAQAAAAEAAAAVAw==",
    "power_off":    "AAAAAQAAAAEAAAAvAw==",
    "mute":         "AAAAAQAAAAEAAAAUAw==",
    "volume_up":    "AAAAAQAAAAEAAAASAw==",
    "volume_down":  "AAAAAQAAAAEAAAATAw==",
    "channel_up":   "AAAAAQAAAAEAAAAQAw==",
    "channel_down": "AAAAAQAAAAEAAAARAw==",
    "up":           "AAAAAQAAAAEAAAB0Aw==",
    "down":         "AAAAAQAAAAEAAAB1Aw==",
    "left":         "AAAAAQAAAAEAAAB2Aw==",
    "right":        "AAAAAQAAAAEAAAB3Aw==",
    "select":       "AAAAAQAAAAEAAABlAw==",
    "home":         "AAAAAQAAAAEAAABgAw==",
    "back":         "AAAAAgAAAJcAAAAjAw==",
    "options":      "AAAAAgAAAJcAAAA2Aw==",
    "play":         "AAAAAgAAAJcAAAAaAw==",
    "pause":        "AAAAAgAAAJcAAAAZAw==",
    "stop":         "AAAAAgAAAJcAAAAYAw==",
    "fast_forward": "AAAAAgAAAJcAAAAcAw==",
    "rewind":       "AAAAAgAAAJcAAAAbAw==",
    "input":        "AAAAAQAAAAEAAAAlAw==",
    "input_hdmi1":  "AAAAAgAAABoAAABaAw==",
    "input_hdmi2":  "AAAAAgAAABoAAABbAw==",
    "input_hdmi3":  "AAAAAgAAABoAAABcAw==",
    "input_hdmi4":  "AAAAAgAAABoAAABdAw==",
    "netflix":      "AAAAAgAAABoAAAB8Aw==",
    "youtube":      "AAAAAgAAAMQAAABHAw==",
    "prime":        "AAAAAgAAAMQAAABhAw==",
    "google_play":  "AAAAAgAAAMQAAABiAw==",
    "num_1":        "AAAAAQAAAAEAAAAAAw==",
    "num_2":        "AAAAAQAAAAEAAAABAw==",
    "num_3":        "AAAAAQAAAAEAAAACAw==",
    "num_4":        "AAAAAQAAAAEAAAADAw==",
    "num_5":        "AAAAAQAAAAEAAAAEAw==",
    "num_6":        "AAAAAQAAAAEAAAAFAw==",
    "num_7":        "AAAAAQAAAAEAAAAGAw==",
    "num_8":        "AAAAAQAAAAEAAAAHAw==",
    "num_9":        "AAAAAQAAAAEAAAAIAw==",
    "num_0":        "AAAAAQAAAAEAAAAJAw==",
}

_SONY_IRCC_SOAP = """\
<?xml version="1.0"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
            s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:X_SendIRCC xmlns:u="urn:schemas-sony-com:service:IRCC:1">
      <IRCCCode>{code}</IRCCCode>
    </u:X_SendIRCC>
  </s:Body>
</s:Envelope>"""


def _sony_ircc(action: str) -> str:
    """Send an IRCC IR code to a Sony BRAVIA TV."""
    code = _SONY_IRCC.get(action)
    if code is None:
        return f"Sony: no IRCC code for '{action}'."

    url     = f"http://{TV_IP}/sony/IRCC"
    headers = {
        "Content-Type":  "text/xml; charset=UTF-8",
        "SOAPACTION":    '"urn:schemas-sony-com:service:IRCC:1#X_SendIRCC"',
    }
    if TV_PSK:
        headers["X-Auth-PSK"] = TV_PSK

    try:
        resp = requests.post(
            url,
            data=_SONY_IRCC_SOAP.format(code=code).encode("utf-8"),
            headers=headers,
            timeout=4,
        )
        if resp.ok:
            return f"Sony TV: sent {action}."
        if resp.status_code == 403:
            return (
                "Sony TV: access denied (HTTP 403). "
                "Make sure IP remote control is enabled and TV_PSK matches the TV's PSK."
            )
        return f"Sony TV error: HTTP {resp.status_code} — {resp.text[:120]}"
    except requests.exceptions.ConnectionError:
        return (
            f"Cannot reach Sony TV at {TV_IP}. "
            "Check TV_IP in .env and that IP remote control is enabled on the TV."
        )
    except Exception as e:
        return f"Sony TV error: {e}"


def _sony_power_on() -> str:
    """Power on a Sony BRAVIA from standby via REST API (network standby must be enabled)."""
    url     = f"http://{TV_IP}/sony/system"
    headers = {"Content-Type": "application/json"}
    if TV_PSK:
        headers["X-Auth-PSK"] = TV_PSK
    body = {
        "method":  "setPowerStatus",
        "id":      1,
        "params":  [{"status": True}],
        "version": "1.0",
    }
    try:
        resp = requests.post(url, json=body, headers=headers, timeout=4)
        if resp.ok:
            return "Sony TV: powering on."
        return f"Sony TV power-on error: HTTP {resp.status_code}"
    except requests.exceptions.ConnectionError:
        return (
            f"Cannot reach Sony TV at {TV_IP} to power on. "
            "Ensure 'Network standby' is enabled in TV settings."
        )
    except Exception as e:
        return f"Sony power-on error: {e}"


def _sony_launch_app(app_name: str) -> str:
    """Launch a streaming app on Sony BRAVIA via the app control REST API."""
    _SONY_APPS: dict[str, str] = {
        "netflix":  "com.sony.dtv.networksimplification.netflix.ResumeNFActivity",
        "youtube":  "com.google.android.youtube.tv.TvMainActivity",
        "prime":    "com.amazon.amazonvideo.livingroom.MainActivity",
        "disney":   "com.disney.disneyplus",
        "spotify":  "com.spotify.tv.android",
    }
    uri = _SONY_APPS.get(app_name.lower())
    if uri:
        # Use IRCC shortcut if available, else REST
        ircc_action = app_name.lower()
        if ircc_action in _SONY_IRCC:
            return _sony_ircc(ircc_action)
        url     = f"http://{TV_IP}/sony/appControl"
        headers = {"Content-Type": "application/json"}
        if TV_PSK:
            headers["X-Auth-PSK"] = TV_PSK
        body = {
            "method":  "setActiveApp",
            "id":      601,
            "params":  [{"uri": uri}],
            "version": "1.0",
        }
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=4)
            return f"Launched {app_name} on Sony TV." if resp.ok else f"App launch error: HTTP {resp.status_code}"
        except Exception as e:
            return f"Sony app launch error: {e}"
    # Fallback: try IRCC
    if app_name.lower() in _SONY_IRCC:
        return _sony_ircc(app_name.lower())
    return f"App '{app_name}' not available on Sony. Try: {', '.join(_SONY_APPS)}."


# ── Common key map: Alfred action → per-brand key ─────────────────────────────

_ROKU_KEYS: dict[str, str | None] = {
    "home":        "Home",
    "back":        "Back",
    "select":      "Select",
    "up":          "Up",
    "down":        "Down",
    "left":        "Left",
    "right":       "Right",
    "play":        "Play",
    "pause":       "Play",        # Roku toggles play/pause with same key
    "stop":        "Play",
    "fast_forward":"FastForward",
    "rewind":      "Rewind",
    "volume_up":   "VolumeUp",
    "volume_down": "VolumeDown",
    "mute":        "VolumeMute",
    "power":       "Power",
    "power_on":    "PowerOn",
    "power_off":   "PowerOff",
    "channel_up":  "ChannelUp",
    "channel_down":"ChannelDown",
    "netflix":     "Netflix",
    "prime":       None,          # use launch_app instead
    "youtube":     None,
    "input_hdmi1": None,
    "input_hdmi2": None,
    "input_hdmi3": None,
}

_SAMSUNG_KEYS: dict[str, str] = {
    "home":        "KEY_HOME",
    "back":        "KEY_RETURN",
    "select":      "KEY_ENTER",
    "up":          "KEY_UP",
    "down":        "KEY_DOWN",
    "left":        "KEY_LEFT",
    "right":       "KEY_RIGHT",
    "play":        "KEY_PLAY",
    "pause":       "KEY_PAUSE",
    "stop":        "KEY_STOP",
    "fast_forward":"KEY_FF",
    "rewind":      "KEY_REWIND",
    "volume_up":   "KEY_VOLUP",
    "volume_down": "KEY_VOLDOWN",
    "mute":        "KEY_MUTE",
    "power":       "KEY_POWER",
    "power_on":    "KEY_POWERON",
    "power_off":   "KEY_POWEROFF",
    "channel_up":  "KEY_CHUP",
    "channel_down":"KEY_CHDOWN",
    "input_hdmi1": "KEY_HDMI1",
    "input_hdmi2": "KEY_HDMI2",
    "input_hdmi3": "KEY_HDMI3",
    "netflix":     "KEY_NETFLIX",
    "source":      "KEY_SOURCE",
}

_ANDROID_KEYS: dict[str, int] = {
    "home":        3,
    "back":        4,
    "up":          19,
    "down":        20,
    "left":        21,
    "right":       22,
    "select":      23,
    "power":       26,
    "volume_up":   24,
    "volume_down": 25,
    "mute":        164,
    "play":        85,
    "pause":       85,
    "stop":        86,
    "fast_forward":90,
    "rewind":      89,
    "channel_up":  166,
    "channel_down":167,
    "netflix":     0,   # handled via am start intent
    "youtube":     0,
}

# Roku app IDs (most common)
_ROKU_APP_IDS: dict[str, int] = {
    "netflix":  12,
    "youtube":  2285,
    "prime":    13,
    "amazon":   13,
    "hulu":     2285,
    "disney":   291097,
    "spotify":  22297,
    "plex":     13535,
    "twitch":   50539,
    "sling":    46041,
    "peacock":  593099,
    "paramount":4291,
}

# Android TV package names for common streaming apps
_ANDROID_PACKAGES: dict[str, str] = {
    "netflix":  "com.netflix.ninja",
    "youtube":  "com.google.android.youtube.tv",
    "prime":    "com.amazon.amazonvideo.livingroom",
    "disney":   "com.disney.disneyplus",
    "spotify":  "com.spotify.tv.android",
    "plex":     "com.plexapp.android",
    "twitch":   "tv.twitch.android.app",
    "hulu":     "com.hulu.livingroomplus",
}


# ── Roku ──────────────────────────────────────────────────────────────────────

def _roku_post(path: str) -> str:
    url = f"http://{TV_IP}:8060/{path}"
    try:
        resp = requests.post(url, timeout=3)
        return "ok" if resp.ok else f"HTTP {resp.status_code}"
    except requests.exceptions.ConnectionError:
        return f"Cannot reach Roku at {TV_IP}:8060 — check TV_IP in .env"
    except Exception as e:
        return str(e)


def _roku_keypress(action: str) -> str:
    key = _ROKU_KEYS.get(action)
    if key is None:
        return f"'{action}' not supported directly on Roku. Try open_app."
    result = _roku_post(f"keypress/{key}")
    return f"Roku: sent {key}." if result == "ok" else f"Roku error: {result}"


def _roku_launch(app_name: str) -> str:
    app_id = _ROKU_APP_IDS.get(app_name.lower())
    if not app_id:
        return f"App '{app_name}' not in built-in list. Available: {', '.join(_ROKU_APP_IDS)}."
    result = _roku_post(f"launch/{app_id}")
    return f"Launched {app_name} on Roku." if result == "ok" else f"Roku launch error: {result}"


# ── Samsung ───────────────────────────────────────────────────────────────────

def _samsung_send(action: str) -> str:
    try:
        from samsungtvws import SamsungTVWS  # type: ignore
    except ImportError:
        return "samsungtvws not installed — run: pip install samsungtvws"

    raw_key = _SAMSUNG_KEYS.get(action, action.upper())
    try:
        tv = SamsungTVWS(host=TV_IP, name=TV_NAME)
        tv.send_key(raw_key)
        return f"Samsung TV: sent {raw_key}."
    except Exception as e:
        return f"Samsung TV error: {e}"


# ── LG WebOS ──────────────────────────────────────────────────────────────────

_LG_BUTTONS: dict[str, str] = {
    "home":        "HOME",
    "back":        "BACK",
    "select":      "ENTER",
    "up":          "UP",
    "down":        "DOWN",
    "left":        "LEFT",
    "right":       "RIGHT",
    "play":        "PLAY",
    "pause":       "PAUSE",
    "stop":        "STOP",
    "fast_forward":"FASTFORWARD",
    "rewind":      "REWIND",
    "volume_up":   "VOLUMEUP",
    "volume_down": "VOLUMEDOWN",
    "mute":        "MUTE",
    "power":       "POWER",
    "power_off":   "POWER",
    "channel_up":  "CHANNELUP",
    "channel_down":"CHANNELDOWN",
}


def _lg_send(action: str) -> str:
    try:
        import asyncio
        from aiowebostv import WebOsClient  # type: ignore
    except ImportError:
        return "aiowebostv not installed — run: pip install aiowebostv"

    button = _LG_BUTTONS.get(action, action.upper())

    async def _run():
        client = WebOsClient(TV_IP)
        await client.connect()
        await client.send_button(button)
        await client.disconnect()

    try:
        asyncio.run(_run())
        return f"LG TV: sent {button}."
    except Exception as e:
        return f"LG TV error: {e}"


# ── Android TV (ADB) ──────────────────────────────────────────────────────────

def _adb(cmd: list[str]) -> tuple[int, str]:
    """Run an adb command, return (returncode, output)."""
    full = ["adb", "-s", f"{TV_IP}:5555"] + cmd
    try:
        r = subprocess.run(full, capture_output=True, text=True, timeout=8)
        out = (r.stdout + r.stderr).strip()
        return r.returncode, out
    except FileNotFoundError:
        return 1, "adb not found — install Android Platform Tools and add to PATH"
    except subprocess.TimeoutExpired:
        return 1, "adb command timed out"


def _android_send(action: str) -> str:
    # Special-case apps via am start
    if action in ("netflix", "youtube", "prime", "disney", "spotify", "plex", "twitch", "hulu"):
        pkg = _ANDROID_PACKAGES.get(action)
        if pkg:
            rc, out = _adb(["shell", "monkey", "-p", pkg, "1"])
            return f"Launched {action} on Android TV." if rc == 0 else f"Launch failed: {out}"

    keycode = _ANDROID_KEYS.get(action)
    if keycode is None or keycode == 0:
        return f"Key '{action}' not mapped for Android TV."
    rc, out = _adb(["shell", "input", "keyevent", str(keycode)])
    return f"Android TV: sent {action}." if rc == 0 else f"ADB error: {out}"


def _android_connect() -> str:
    try:
        r = subprocess.run(
            ["adb", "connect", f"{TV_IP}:5555"],
            capture_output=True, text=True, timeout=8,
        )
        return r.stdout.strip() or r.stderr.strip()
    except FileNotFoundError:
        return "adb not found — install Android Platform Tools and add to PATH"
    except Exception as e:
        return str(e)


def _android_type(text: str) -> str:
    rc, out = _adb(["shell", "input", "text", text.replace(" ", "%s")])
    return f"Typed '{text}' on Android TV." if rc == 0 else f"ADB error: {out}"


# ── Roku discovery (SSDP) ─────────────────────────────────────────────────────

def _discover_roku() -> str:
    """Broadcast SSDP M-SEARCH and return the first Roku IP found."""
    import socket
    SSDP_ADDR = "239.255.255.250"
    SSDP_PORT = 1900
    msg = (
        "M-SEARCH * HTTP/1.1\r\n"
        f"HOST: {SSDP_ADDR}:{SSDP_PORT}\r\n"
        'MAN: "ssdp:discover"\r\n'
        "MX: 3\r\n"
        'ST: roku:ecp\r\n\r\n'
    ).encode()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(4)
        sock.sendto(msg, (SSDP_ADDR, SSDP_PORT))
        data, addr = sock.recvfrom(1024)
        return f"Found Roku at {addr[0]}. Set TV_IP={addr[0]} in your .env file."
    except socket.timeout:
        return "No Roku found on the network — make sure your TV is on and on the same Wi-Fi."
    except Exception as e:
        return f"Discovery error: {e}"
    finally:
        try:
            sock.close()
        except Exception:
            pass


# ── Dispatcher ────────────────────────────────────────────────────────────────

def _require_ip() -> str | None:
    """Return an error string if TV_IP is not set."""
    if not TV_IP:
        return "TV_IP is not set in .env. Add TV_IP=<your TV's local IP address>."
    return None


def execute(tool_name: str, tool_input: dict) -> str:
    if tool_name != "tv_control":
        return f"Unknown tool: {tool_name}"

    action:   str = tool_input.get("action", "").lower().strip()
    app_name: str = tool_input.get("app_name", "").lower().strip()
    text:     str = tool_input.get("text", "").strip()

    # ── Discovery (no IP needed) ───────────────────────────────────────────────
    if action == "discover":
        return _discover_roku()

    if action == "status":
        lines = [
            f"TV_TYPE = {TV_TYPE or '(not set — defaulting to sony)'}",
            f"TV_IP   = {TV_IP   or '(not set)'}",
            f"TV_NAME = {TV_NAME}",
            f"TV_PSK  = {'set' if TV_PSK else '(not set — needed for Sony IRCC auth)'}",
        ]
        return "\n".join(lines)

    err = _require_ip()
    if err:
        return err

    tv = TV_TYPE or "sony"  # default to Sony

    # ── Android TV / Sony Android TV: connect helper ───────────────────────────
    if action == "connect" and tv in ("android", "sony_android"):
        return _android_connect()

    # ── Open app ──────────────────────────────────────────────────────────────
    if action == "open_app":
        name = app_name or text
        if not name:
            return "Please provide an app_name (e.g. netflix, youtube, prime)."
        if tv == "sony":
            return _sony_launch_app(name)
        if tv == "roku":
            return _roku_launch(name)
        if tv == "android":
            return _android_send(name)
        return f"open_app not yet implemented for {tv}."

    # ── Type text (Android only) ───────────────────────────────────────────────
    if action == "type_text":
        if tv not in ("android", "sony_android"):
            return "type_text is only supported for Android TV."
        return _android_type(text or app_name)

    # ── Standard key actions ───────────────────────────────────────────────────
    if tv == "sony":
        # Power-on uses the REST API (works from standby); everything else → IRCC
        if action == "power_on":
            return _sony_power_on()
        return _sony_ircc(action)
    if tv == "roku":
        return _roku_keypress(action)
    if tv == "samsung":
        return _samsung_send(action)
    if tv == "lg":
        return _lg_send(action)
    if tv == "android":
        return _android_send(action)

    return f"Unsupported TV_TYPE '{tv}'. Set TV_TYPE to: sony, roku, samsung, lg, or android."


# ── Tool schema (for Claude) ──────────────────────────────────────────────────

TV_TOOL = {
    "name": "tv_control",
    "description": (
        "Control the user's smart TV. "
        "Supports Sony BRAVIA (IRCC-IP), Roku, Samsung, LG WebOS, and Android/Google TV. "
        "Use this when the user says things like: "
        "'turn on the TV', 'mute it', 'volume up', 'next channel', "
        "'go home', 'open Netflix', 'play/pause', 'go back', "
        "'change input to HDMI 1', 'open YouTube on TV', "
        "'pause the show', 'fast forward', 'rewind'. "
        "Always act immediately — no confirmation needed."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    # Navigation
                    "home", "back", "select",
                    "up", "down", "left", "right",
                    # Playback
                    "play", "pause", "stop", "fast_forward", "rewind",
                    # Power
                    "power", "power_on", "power_off",
                    # Volume
                    "volume_up", "volume_down", "mute",
                    # Channels / Inputs
                    "channel_up", "channel_down",
                    "input_hdmi1", "input_hdmi2", "input_hdmi3",
                    # Apps
                    "open_app",
                    # Text input (Android TV only)
                    "type_text",
                    # Utility
                    "discover", "status", "connect",
                ],
                "description": (
                    "The remote control action. "
                    "Use 'discover' to find the TV IP on the network. "
                    "Use 'open_app' + app_name to launch a streaming service. "
                    "Use 'status' to show current TV configuration."
                ),
            },
            "app_name": {
                "type": "string",
                "description": (
                    "App to launch when action is 'open_app'. "
                    "Examples: netflix, youtube, prime, disney, spotify, hulu, plex."
                ),
            },
            "text": {
                "type": "string",
                "description": "Text to type on screen (Android TV only, with action 'type_text').",
            },
        },
        "required": ["action"],
    },
}

ALL_TOOLS = [TV_TOOL]
