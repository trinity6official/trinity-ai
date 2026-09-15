"""Human-readable Trinity status/help presentation."""
from __future__ import annotations

from typing import Any


class StatusService:
    """Build and deliver status/help messages without owning runtime state."""

    def __init__(self, host: Any) -> None:
        self.host = host

    def send_help(self, language: str = "english") -> str:
        if language == "tamil":
            message = """Trinity Commands

/briefing - Morning briefing
/progress - Project progress
/next - Weekly priorities
/security - Security check
/business - Business status
/client - Client strategy
/status - Trinity status
/brain - Brain and memory status
/pending - Pending changes

Skills: GitHub, Web, Memory, Search, Code, Business, Consciousness

Just ask me anything naturally!"""
        else:
            message = """Trinity Commands

/briefing - Morning briefing
/progress - Project progress
/next - Weekly priorities
/security - Security check
/business - Business status
/client - Client strategy
/status - Trinity status
/brain - Brain and memory status
/pending - Pending changes

Skills available:
GitHub - Read write revert files
Web - Monitor websites and SSL
Memory - Brain and history
Search - News and prospects
Code - Review and audit code
Business - Revenue and clients
Consciousness - Memory patterns and learning

Just ask me anything naturally!"""
        self.host.send_telegram(message)
        return message

    def send_status(self) -> str:
        h = self.host
        days = h.memory.get_days_alive()
        health = h.skills.get_health_summary()
        brain_stats = h.consciousness.get_memory_stats()
        brain_state = h.consciousness.get_state()

        runtime_mode = getattr(h, "runtime_mode", None)
        runtime_value = getattr(runtime_mode, "value", str(runtime_mode or ""))
        if h.daemon:
            mode = "Local Daemon"
        elif runtime_value in {"local_interactive", "local"}:
            mode = "Local Interactive"
        else:
            mode = "Local Runtime"

        message = f"""Trinity Status

AI Brain: Local Model Router ({getattr(h, '_local_model_name', 'configured model')})
Memory: Active - Day {days}
Language: Auto Tamil and English
Mode: {mode}

Skills Loaded: {health.get('skills_loaded', 0)}
GitHub: Active
Web Monitor: Active
Memory: Active
Search: Active
Code Review: Active
Business: Active

Website: {'Online' if health.get('website_live') else 'Offline'}
Hardware: {'Active' if h.daemon else 'Local runtime ready'}

Consciousness:
Boot #{brain_stats['total_boots']} | {brain_stats['total_actions']} actions
Mood: {brain_state['mood']} | Confidence: {brain_state['confidence']:.0%}
Memories: {brain_stats['episodic_count']}E {brain_stats['semantic_count']}S {brain_stats['procedural_count']}P
Patterns: {brain_stats['patterns_detected']}

trinity6.com"""
        h.send_telegram(message)
        return message

    def send_brain_status(self) -> str:
        h = self.host
        stats = h.consciousness.get_memory_stats()
        state = h.consciousness.get_state()
        patterns = h.consciousness.brain.get("patterns", [])

        msg = f"""Trinity Brain Status

Boot: #{stats['total_boots']}
Lifetime Actions: {stats['total_actions']}
Decisions Made: {stats['decisions_logged']}

Memory:
  Episodic: {stats['episodic_count']} memories
  Semantic: {stats['semantic_count']} facts
  Procedural: {stats['procedural_count']} procedures
  Working: {stats['working_count']} items

State:
  Mood: {state['mood']}
  Confidence: {state['confidence']:.0%}
  Energy: {state['energy']:.0%}
  Focus: {state.get('current_focus', 'none')}

Patterns Detected: {stats['patterns_detected']}"""

        if patterns:
            msg += "\n\nRecent Patterns:"
            for pattern in patterns[-3:]:
                msg += f"\n- [{pattern['type']}] {pattern['description'][:80]}"

        recent_failures = h.consciousness.get_recent_failures(3)
        if recent_failures:
            msg += "\n\nRecent Failures:"
            for failure in recent_failures:
                msg += f"\n- {failure['tool']}: {failure['details'][:60]}"

        if h.daemon:
            dstats = h.daemon.get_daemon_stats()
            msg += "\n\nDaemon Mode: Active"
            msg += f"\nUptime: {dstats.get('uptime_human', '?')}"
            msg += f"\nAuto-saves: {dstats['total_saves']}"
            msg += f"\nMemory rotations: {dstats['total_rotations']}"

        h.send_telegram(msg)
        return msg
