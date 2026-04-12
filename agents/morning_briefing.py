"""
MorningBriefingAgent — generates a personalized spoken briefing on startup.

Reads real data from the database (habits, last session, days active),
builds a concise prompt, and calls Groq to produce a 2-3 sentence briefing
that sounds like a helpful friend, not a corporate assistant.

Day 1 fallback: if no data exists yet, returns a pre-written intro string
with no API call — startup never blocks on a network request when there's
nothing to say yet.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# These are imported lazily inside the function to avoid circular imports
# and to allow morning_briefing.py to be imported without all deps loaded.


SYSTEM_PROMPT = (
    "You are HoloDesk, an ambient AI layer on the user's Windows desktop. "
    "Generate a warm, natural, specific 2-3 sentence morning briefing based "
    "on the user's recent activity. "
    "Mention real app names from the data provided. "
    "Sound like a helpful friend, not a corporate assistant. "
    "Be specific — reference actual apps and times, not generic advice. "
    "Never say 'Good morning' as the first words — start with 'Hey' instead. "
    "Keep it under 50 words total — this will be spoken aloud."
)

DAY_1_MESSAGE = (
    "Hey, I'm HoloDesk — your ambient AI layer. "
    "I'm learning which apps you use and when. "
    "Give me a few days and I'll brief you on your own routine every morning."
)


def generate_briefing(demo_mode: bool = False) -> str:
    """
    Generate a morning briefing string.

    Args:
        demo_mode: If True, skip the Day 1 check — demo data is present.

    Returns:
        A 2-3 sentence string ready to be spoken by TTS. Never raises.
    """
    try:
        from agents.memory_agent import memory_agent
        from connectors.groq_client import GroqClient

        days_active = memory_agent.get_days_active()

        # Day 1 fallback — no data yet, no API call needed
        if days_active == 0 and not demo_mode:
            logger.info("[Briefing] Day 1 — returning intro message")
            return DAY_1_MESSAGE

        # Pull context from memory_agent (all methods already exist)
        habits_str = memory_agent.format_habits_for_prompt()
        unfinished = memory_agent.format_unfinished_for_prompt()

        user_prompt = (
            f"User data:\n"
            f"  Days HoloDesk has been running: {days_active}\n"
            f"  Detected habits: {habits_str}\n"
            f"  Last session activity: {unfinished}\n"
            f"  Current time: {datetime.now().strftime('%A %I:%M %p')}\n\n"
            f"Generate the morning briefing now."
        )

        logger.info("[Briefing] Calling Groq (llama-3.3-70b-versatile)...")
        client = GroqClient()
        briefing = client.complete(
            prompt=user_prompt,
            system=SYSTEM_PROMPT,
            max_tokens=120,  # ~50 words spoken = plenty for a morning briefing
        )

        logger.info("[Briefing] Generated: %s", briefing[:80])
        return briefing

    except RuntimeError as e:
        # Missing API key or package — tell the user clearly
        logger.warning("[Briefing] Config error: %s", e)
        return f"Hey, morning briefing needs your Groq API key — check the .env file."

    except Exception as e:
        # Network error, API down, etc. — don't crash startup
        logger.warning("[Briefing] Failed to generate briefing: %s", e)
        return (
            "Hey, I couldn't reach the AI right now. "
            "Everything else is working — just ask me anything."
        )
