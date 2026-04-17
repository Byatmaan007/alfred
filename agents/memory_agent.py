"""
Memory Agent for Alfred.

Tools:
  memory_record_trade   — log a completed trade (P&L, symbol, notes)
  memory_get_trades     — retrieve trade history with optional filters
  memory_trade_summary  — aggregate stats (total P&L, win rate)
  memory_save_fact      — embed and store a long-term memory
  memory_search         — semantic search over stored memories  ← NEW
  memory_get_facts      — list memories by category
  memory_delete_fact    — remove a memory by ID

Storage:
  memory/chroma_db/   — vector store (ChromaDB, semantic search)
  memory/gains.json   — structured trade records
  memory/session.json — conversation history (managed by agent.py)
"""

from memory import gains, vector

# ── Tool definitions ───────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "memory_record_trade",
        "description": (
            "Save a completed trade to the permanent trading log. "
            "Use this when the user mentions closing a trade, taking profit, "
            "cutting a loss, or wants to record a trade result. "
            "Always save the trade before summarising performance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol":      {"type": "string",  "description": "Ticker, e.g. BTCUSD, AAPL, EURUSD"},
                "direction":   {"type": "string",  "description": "'long' or 'short'"},
                "entry":       {"type": "number",  "description": "Entry price"},
                "exit_price":  {"type": "number",  "description": "Exit price"},
                "pnl_usd":     {"type": "number",  "description": "Profit or loss in USD"},
                "pnl_percent": {"type": "number",  "description": "Profit or loss as a percentage"},
                "timeframe":   {"type": "string",  "description": "Chart timeframe, e.g. 4h, 1D"},
                "notes":       {"type": "string",  "description": "Notes about the trade setup or outcome"},
                "screenshot":  {"type": "string",  "description": "Path to chart screenshot if taken"},
            },
            "required": ["symbol", "direction", "entry", "exit_price"],
        },
    },
    {
        "name": "memory_get_trades",
        "description": (
            "Retrieve past trade records. Use when the user asks about trading "
            "history, past trades on a symbol, or recent results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string",  "description": "Filter by ticker. Leave empty for all."},
                "limit":  {"type": "integer", "description": "Max trades to return (default 10)"},
                "since":  {"type": "string",  "description": "ISO date to filter from, e.g. 2026-04-01"},
            },
            "required": [],
        },
    },
    {
        "name": "memory_trade_summary",
        "description": (
            "Aggregate trading performance: total P&L, win rate, number of trades. "
            "Use when the user asks how they're doing or about overall performance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Filter to one symbol. Leave empty for all."},
            },
            "required": [],
        },
    },
    {
        "name": "memory_save_fact",
        "description": (
            "Embed and store a long-term memory in the semantic vector store. "
            "Use when the user shares something important to remember: a preference, "
            "a project decision, a personal detail, or any insight worth keeping. "
            "Category must be one of: trading, personal, project, general."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content":  {"type": "string", "description": "The fact or insight to remember"},
                "category": {"type": "string", "description": "'trading', 'personal', 'project', or 'general'"},
                "tags":     {"type": "array", "items": {"type": "string"}, "description": "Optional tags"},
            },
            "required": ["content", "category"],
        },
    },
    {
        "name": "memory_search",
        "description": (
            "Semantic search over stored memories — finds relevant facts by meaning, "
            "not just keywords. Use when the user asks what Alfred remembers about a topic, "
            "or before answering personal questions to surface relevant context. "
            "Always prefer this over memory_get_facts when you have a specific query."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query":    {"type": "string",  "description": "What to search for, e.g. 'trading preferences', 'project deadlines'"},
                "n":        {"type": "integer", "description": "Number of results (default 5)"},
                "category": {"type": "string",  "description": "Optionally filter by category: trading, personal, project, general"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "memory_get_facts",
        "description": (
            "List stored memories by category. Use for browsing or when the user asks "
            "'what do you know about me' without a specific topic. "
            "For topic-specific recall, prefer memory_search."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string",  "description": "Filter by category. Leave empty for all."},
                "limit":    {"type": "integer", "description": "Max facts to return (default 15)"},
            },
            "required": [],
        },
    },
    {
        "name": "memory_delete_fact",
        "description": "Delete a stored memory by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fact_id": {"type": "string", "description": "The ID of the memory to delete"},
            },
            "required": ["fact_id"],
        },
    },
]

TOOL_NAMES = {t["name"] for t in TOOLS}


# ── Executor ───────────────────────────────────────────────────────────────────

def execute(tool_name: str, tool_input: dict) -> str:

    if tool_name == "memory_record_trade":
        r = gains.record_trade(
            symbol      = tool_input["symbol"],
            direction   = tool_input["direction"],
            entry       = tool_input["entry"],
            exit_price  = tool_input["exit_price"],
            pnl_usd     = tool_input.get("pnl_usd"),
            pnl_percent = tool_input.get("pnl_percent"),
            timeframe   = tool_input.get("timeframe"),
            notes       = tool_input.get("notes"),
            screenshot  = tool_input.get("screenshot"),
        )
        pnl = f"${r['pnl_usd']:+.2f}" if r["pnl_usd"] is not None else "P&L not recorded"
        return (
            f"Trade saved (ID: {r['id']}).\n"
            f"  {r['direction'].upper()} {r['symbol']}  "
            f"Entry: {r['entry']}  Exit: {r['exit']}  P&L: {pnl}"
        )

    elif tool_name == "memory_get_trades":
        records = gains.get_trades(
            symbol=tool_input.get("symbol"),
            limit =tool_input.get("limit", 10),
            since =tool_input.get("since"),
        )
        if not records:
            return "No trades found."
        lines = ["Recent trades:\n"]
        for r in records:
            pnl = f"${r['pnl_usd']:+.2f}" if r["pnl_usd"] is not None else "—"
            lines.append(
                f"  [{r['id']}] {r['timestamp'][:10]}  "
                f"{r['direction'].upper()} {r['symbol']}  "
                f"{r['entry']} → {r['exit']}  P&L: {pnl}"
                + (f"  [{r['timeframe']}]" if r.get("timeframe") else "")
                + (f"  \"{r['notes']}\"" if r.get("notes") else "")
            )
        return "\n".join(lines)

    elif tool_name == "memory_trade_summary":
        s = gains.summary(symbol=tool_input.get("symbol"))
        if s["total_trades"] == 0:
            return "No trades recorded yet."
        sym_str = f" for {tool_input['symbol'].upper()}" if tool_input.get("symbol") else ""
        return (
            f"Trading summary{sym_str}:\n"
            f"  Total trades : {s['total_trades']}\n"
            f"  Total P&L    : ${s['total_pnl_usd']:+.2f}\n"
            f"  Win rate     : {s['win_rate']}%  ({s['wins']}W / {s['losses']}L)"
        )

    elif tool_name == "memory_save_fact":
        r = vector.save(
            content  = tool_input["content"],
            category = tool_input.get("category", "general"),
            tags     = tool_input.get("tags", []),
        )
        return f"Memory saved (ID: {r['id']}): \"{r['content']}\""

    elif tool_name == "memory_search":
        results = vector.search(
            query     = tool_input["query"],
            n_results = tool_input.get("n", 5),
            category  = tool_input.get("category"),
        )
        if not results:
            return "No relevant memories found."
        lines = [f"Memories relevant to \"{tool_input['query']}\":\n"]
        for r in results:
            score = f"  (score: {r['score']})" if r.get("score") is not None else ""
            lines.append(f"  [{r['id']}] [{r['category']}] {r['content']}{score}")
        return "\n".join(lines)

    elif tool_name == "memory_get_facts":
        records = vector.get_all(
            category = tool_input.get("category"),
            limit    = tool_input.get("limit", 15),
        )
        if not records:
            return "No memories stored yet."
        lines = [f"Stored memories ({len(records)}):\n"]
        for r in records:
            lines.append(f"  [{r['id']}] [{r['category']}] {r['content']}")
        return "\n".join(lines)

    elif tool_name == "memory_delete_fact":
        deleted = vector.delete(tool_input["fact_id"])
        return "Memory deleted." if deleted else f"No memory found with ID {tool_input['fact_id']}."

    return f"Unknown memory tool: {tool_name}"
