"""Alfred self-control tools — voice, settings, etc."""
from voice import tts

TOOL_NAMES = {"alfred_set_voice"}

TOOLS = [
    {
        "name": "alfred_set_voice",
        "description": (
            "Change Alfred's text-to-speech voice at runtime. "
            "Use the exact edge-tts voice name (e.g. 'en-NG-AbeoNeural'). "
            "Common voices:\n"
            "  Nigerian male   → en-NG-AbeoNeural\n"
            "  Nigerian female → en-NG-EzinneNeural\n"
            "  US male         → en-US-AndrewMultilingualNeural\n"
            "  British male    → en-GB-RyanNeural\n"
            "  Australian male → en-AU-WilliamNeural\n"
            "  Indian male     → en-IN-PrabhatNeural\n"
            "  Indian female   → en-IN-NeerjaNeural\n"
            "  Vietnamese male → vi-VN-NamMinhNeural\n"
            "  Vietnamese fem  → vi-VN-HoaiMyNeural\n"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "voice": {
                    "type": "string",
                    "description": "The edge-tts voice name to switch to.",
                }
            },
            "required": ["voice"],
        },
    }
]


def execute(tool_name: str, tool_input: dict) -> str:
    if tool_name == "alfred_set_voice":
        voice = tool_input["voice"]
        tts.set_voice(voice)
        return f"Voice changed to {voice}."
    return f"Unknown tool: {tool_name}"
