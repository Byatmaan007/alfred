"""
FRED (Federal Reserve Economic Data) tool for Alfred.

Fetches US macroeconomic data from the St. Louis Fed API:
  get_series    — fetch observations for a known series ID (e.g. UNRATE, GDP)
  search_series — search for series by keyword
  series_info   — get metadata (title, frequency, units) for a series ID

Common series IDs:
  GDP       Gross Domestic Product
  UNRATE    Unemployment Rate
  CPIAUCSL  Consumer Price Index (inflation)
  FEDFUNDS  Federal Funds Rate
  DGS10     10-Year Treasury Yield
  DGS2      2-Year Treasury Yield
  SP500     S&P 500 Index
  DEXUSEU   USD/EUR Exchange Rate
  HOUST     Housing Starts
  INDPRO    Industrial Production Index
"""

import os
import requests
from datetime import datetime, timedelta

_KEY  = os.getenv("FRED_API_KEY", "")
_BASE = "https://api.stlouisfed.org/fred"


def _get(endpoint: str, params: dict) -> dict:
    params["api_key"]       = _KEY
    params["file_type"]     = "json"
    r = requests.get(f"{_BASE}/{endpoint}", params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def get_series(series_id: str, limit: int = 10, start_date: str = "") -> str:
    """Fetch the most recent observations for a FRED series."""
    if not _KEY:
        return "FRED_API_KEY not set. Add it to your .env file."
    try:
        params: dict = {"series_id": series_id.upper(), "sort_order": "desc", "limit": limit}
        if start_date:
            params["observation_start"] = start_date
        data = _get("series/observations", params)
        obs  = data.get("observations", [])
        if not obs:
            return f"No data found for series {series_id}."

        # Also pull metadata for units/title
        meta  = _get("series", {"series_id": series_id.upper()})
        info  = meta.get("seriess", [{}])[0]
        title = info.get("title", series_id.upper())
        units = info.get("units_short", info.get("units", ""))

        lines = [f"{title} ({series_id.upper()}) — {units}"]
        for o in reversed(obs):
            if o.get("value") != ".":
                lines.append(f"  {o['date']}: {o['value']}")
        return "\n".join(lines)
    except requests.HTTPError as e:
        return f"FRED API error: {e}"
    except Exception as e:
        return f"Failed to fetch FRED data: {e}"


def search_series(query: str, limit: int = 5) -> str:
    """Search FRED for series matching a keyword."""
    if not _KEY:
        return "FRED_API_KEY not set."
    try:
        data   = _get("series/search", {"search_text": query, "limit": limit, "order_by": "popularity"})
        series = data.get("seriess", [])
        if not series:
            return f"No FRED series found for '{query}'."
        lines  = [f"FRED series matching '{query}':"]
        for s in series:
            lines.append(f"  {s['id']:12s}  {s['title']}  [{s.get('units_short', s.get('units', ''))}]")
        return "\n".join(lines)
    except Exception as e:
        return f"FRED search failed: {e}"


def series_info(series_id: str) -> str:
    """Get metadata for a FRED series (title, frequency, units, last updated)."""
    if not _KEY:
        return "FRED_API_KEY not set."
    try:
        data = _get("series", {"series_id": series_id.upper()})
        s    = data.get("seriess", [{}])[0]
        if not s:
            return f"Series '{series_id}' not found."
        return (
            f"{s.get('title', '?')}  |  ID: {s.get('id', '?')}\n"
            f"  Frequency : {s.get('frequency', '?')}\n"
            f"  Units     : {s.get('units', '?')}\n"
            f"  Updated   : {s.get('last_updated', '?')}\n"
            f"  Seasonal  : {s.get('seasonal_adjustment', '?')}"
        )
    except Exception as e:
        return f"Failed to get series info: {e}"


# ── Tool definition (for Claude) ──────────────────────────────────────────────

FRED_TOOL = {
    "name": "fred_data",
    "description": (
        "Fetch US macroeconomic and financial data from the Federal Reserve (FRED). "
        "Use this when the user asks about: GDP, unemployment, inflation (CPI), "
        "interest rates (Fed funds rate, Treasury yields), S&P 500, housing starts, "
        "industrial production, exchange rates, or any other US economic indicator. "
        "Examples: 'what is the current unemployment rate', 'show me Fed funds rate history', "
        "'search FRED for inflation data', 'what is GDP growth'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get_series", "search_series", "series_info"],
                "description": (
                    "get_series — fetch recent observations for a known series ID. "
                    "search_series — find series by keyword when you don't know the ID. "
                    "series_info — get metadata (title, units, frequency) for a series ID."
                ),
            },
            "series_id": {
                "type": "string",
                "description": "FRED series ID, e.g. UNRATE, GDP, CPIAUCSL, FEDFUNDS, DGS10. Required for get_series and series_info.",
            },
            "query": {
                "type": "string",
                "description": "Search keyword for search_series, e.g. 'unemployment', 'inflation', 'housing'.",
            },
            "limit": {
                "type": "integer",
                "description": "Number of results to return. Default 10 for observations, 5 for search.",
            },
            "start_date": {
                "type": "string",
                "description": "Optional start date for get_series in YYYY-MM-DD format.",
            },
        },
        "required": ["action"],
    },
}

TOOL_NAMES = {"fred_data"}
ALL_TOOLS  = [FRED_TOOL]


def execute(tool_name: str, tool_input: dict) -> str:
    if tool_name != "fred_data":
        return f"Unknown tool: {tool_name}"

    action = tool_input.get("action", "")

    if action == "get_series":
        sid = tool_input.get("series_id", "")
        if not sid:
            return "Please provide a series_id, e.g. UNRATE or GDP."
        return get_series(
            sid,
            limit=tool_input.get("limit", 10),
            start_date=tool_input.get("start_date", ""),
        )

    if action == "search_series":
        query = tool_input.get("query", "")
        if not query:
            return "Please provide a search query."
        return search_series(query, limit=tool_input.get("limit", 5))

    if action == "series_info":
        sid = tool_input.get("series_id", "")
        if not sid:
            return "Please provide a series_id."
        return series_info(sid)

    return f"Unknown FRED action: {action}"
