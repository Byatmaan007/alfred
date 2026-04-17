"""
Obsidian integration for Alfred.

Connects to the Obsidian Local REST API (port 27124) to search and read notes.
Alfred uses this to pull personal context — projects, goals, preferences —
directly from your vault, making answers far more personalized and accurate.

API docs: https://github.com/coddingtonbear/obsidian-local-rest-api
"""

import os
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import requests
from urllib.parse import quote

# ── Config (loaded from .env) ────────────────────────────────────────────────
_HOST = os.getenv("OBSIDIAN_HOST", "127.0.0.1")
_PORT = os.getenv("OBSIDIAN_PORT", "27124")
_KEY  = os.getenv("OBSIDIAN_API_KEY", "")
_BASE = f"https://{_HOST}:{_PORT}"
_HDR  = {"Authorization": f"Bearer {_KEY}"}


# ── Claude tool definitions ──────────────────────────────────────────────────

OBSIDIAN_SEARCH_TOOL = {
    "name": "obsidian_search",
    "description": (
        "Search the user's personal Obsidian knowledge vault. "
        "Use this whenever the user references their projects, goals, preferences, "
        "university courses, or anything personal. The vault contains notes on: "
        "who the user is, their active projects (Alfred, Restaurant Agents, UIGen), "
        "goals, coding preferences, and knowledge areas. "
        "Always search before answering personal or project-specific questions."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search terms — e.g. 'alfred project', 'my goals', 'python preferences'",
            }
        },
        "required": ["query"],
    },
}

OBSIDIAN_READ_TOOL = {
    "name": "obsidian_read",
    "description": (
        "Read the full content of a specific note from the user's Obsidian vault. "
        "Use the file path returned by obsidian_search. "
        "Good for reading detailed project notes, full goal lists, or preference pages."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Vault-relative path to the note, e.g. 'Alfred/02 - My Projects.md'",
            }
        },
        "required": ["path"],
    },
}


# ── API functions ────────────────────────────────────────────────────────────

def search(query: str, context_length: int = 300) -> str:
    """
    Search the Obsidian vault for notes matching the query.
    Returns a formatted summary of matching notes with context snippets.
    """
    try:
        resp = requests.post(
            f"{_BASE}/search/simple/",
            headers=_HDR,
            params={"query": query, "contextLength": context_length},
            timeout=5,
            verify=False,
        )
        resp.raise_for_status()
        results = resp.json()

        if not results:
            return f"No notes found for query: '{query}'"

        lines = [f"Found {len(results)} note(s) matching '{query}':\n"]
        for item in results[:5]:  # limit to top 5
            path = item.get("filename", "unknown")
            lines.append(f"[note] {path}")
            for match in item.get("matches", [])[:2]:
                ctx = match.get("context", "").strip().replace("\n", " ")
                if ctx:
                    lines.append(f"   …{ctx}…")
            lines.append("")

        return "\n".join(lines)

    except requests.exceptions.ConnectionError:
        return (
            "Obsidian vault is not reachable. "
            "Make sure Obsidian is open and the Local REST API plugin is enabled."
        )
    except Exception as e:
        return f"Obsidian search error: {e}"


def read_note(path: str) -> str:
    """
    Read the full content of a note at the given vault-relative path.
    """
    try:
        encoded = quote(path, safe="/")
        resp = requests.get(
            f"{_BASE}/vault/{encoded}",
            headers={**_HDR, "Accept": "text/markdown"},
            timeout=5,
            verify=False,
        )
        if resp.status_code == 404:
            return f"Note not found: '{path}'"
        resp.raise_for_status()
        content = resp.text.strip()
        # Truncate very long notes to avoid overloading context
        if len(content) > 3000:
            content = content[:3000] + "\n\n[...note truncated for brevity...]"
        return content

    except requests.exceptions.ConnectionError:
        return "Obsidian vault is not reachable. Make sure Obsidian is open."
    except Exception as e:
        return f"Obsidian read error: {e}"


OBSIDIAN_APPEND_TOOL = {
    "name": "obsidian_append",
    "description": (
        "Append new content to the end of an existing note in the user's Obsidian vault. "
        "Use this when the user asks Alfred to remember something, add a note, log a decision, "
        "update a goal, or record anything new. "
        "Good default paths: 'Alfred/01 - About Me.md', 'Alfred/02 - My Projects.md', "
        "'Alfred/03 - My Goals.md', 'Alfred/04 - My Preferences.md', 'Alfred/05 - Knowledge Areas.md'. "
        "Always append — never overwrite — unless the user explicitly asks to replace content."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Vault-relative path to the note, e.g. 'Alfred/03 - My Goals.md'",
            },
            "content": {
                "type": "string",
                "description": "The text to append. Use markdown. Start with a newline for clean spacing.",
            },
        },
        "required": ["path", "content"],
    },
}

OBSIDIAN_WRITE_TOOL = {
    "name": "obsidian_write",
    "description": (
        "Create a new note or fully overwrite an existing note in the user's Obsidian vault. "
        "Use this to create brand-new notes (e.g. a new project page, daily note, or research note). "
        "WARNING: this replaces the entire file. Only use when creating new notes or when the user "
        "explicitly asks to replace a note's content."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Vault-relative path for the note, e.g. 'Alfred/Daily/2026-04-13.md'",
            },
            "content": {
                "type": "string",
                "description": "Full markdown content to write to the file.",
            },
        },
        "required": ["path", "content"],
    },
}


# ── Write functions ──────────────────────────────────────────────────────────

def append_note(path: str, content: str) -> str:
    """Append content to an existing note. Creates the note if it doesn't exist."""
    try:
        encoded = quote(path, safe="/")

        # Try to read existing content first
        resp = requests.get(
            f"{_BASE}/vault/{encoded}",
            headers={**_HDR, "Accept": "text/markdown"},
            timeout=5,
            verify=False,
        )
        existing = resp.text.strip() if resp.status_code == 200 else ""

        # Combine and write back
        separator = "\n\n" if existing else ""
        new_content = existing + separator + content.strip()

        put_resp = requests.put(
            f"{_BASE}/vault/{encoded}",
            headers={**_HDR, "Content-Type": "text/markdown"},
            data=new_content.encode("utf-8"),
            timeout=5,
            verify=False,
        )
        put_resp.raise_for_status()
        return f"Appended to '{path}' successfully."

    except requests.exceptions.ConnectionError:
        return "Obsidian vault is not reachable. Make sure Obsidian is open."
    except Exception as e:
        return f"Obsidian append error: {e}"


def write_note(path: str, content: str) -> str:
    """Create or overwrite a note at the given vault-relative path."""
    try:
        encoded = quote(path, safe="/")
        resp = requests.put(
            f"{_BASE}/vault/{encoded}",
            headers={**_HDR, "Content-Type": "text/markdown"},
            data=content.encode("utf-8"),
            timeout=5,
            verify=False,
        )
        resp.raise_for_status()
        return f"Written to '{path}' successfully."

    except requests.exceptions.ConnectionError:
        return "Obsidian vault is not reachable. Make sure Obsidian is open."
    except Exception as e:
        return f"Obsidian write error: {e}"


def execute(tool_name: str, tool_input: dict) -> str:
    """Dispatch a tool call by name."""
    if tool_name == "obsidian_search":
        return search(tool_input["query"])
    if tool_name == "obsidian_read":
        return read_note(tool_input["path"])
    if tool_name == "obsidian_append":
        return append_note(tool_input["path"], tool_input["content"])
    if tool_name == "obsidian_write":
        return write_note(tool_input["path"], tool_input["content"])
    return f"Unknown Obsidian tool: {tool_name}"


TOOL_NAMES = {"obsidian_search", "obsidian_read", "obsidian_append", "obsidian_write"}
ALL_TOOLS  = [OBSIDIAN_SEARCH_TOOL, OBSIDIAN_READ_TOOL, OBSIDIAN_APPEND_TOOL, OBSIDIAN_WRITE_TOOL]
