"""Dependency-light bridge from HTTP/mobile requests into the full Trinity runtime."""
from __future__ import annotations

from typing import Any


def ask_runtime(brain: Any, text: str) -> str:
    """Use the full channel-neutral message pipeline when the runtime provides it."""
    process_text = getattr(brain, "process_text", None)
    if callable(process_text):
        return str(process_text(text, source="api"))

    messages = getattr(brain, "messages", None)
    if messages is not None:
        emitted: list[str] = []
        result = messages.handle(text, responder=emitted.append, source="api")
        if result is not None:
            return str(result)
        if emitted:
            return str(emitted[-1])
    conversation = getattr(brain, "conversation", None)
    if conversation is not None:
        return str(conversation.ask_trinity(text))
    return str(brain.ask_trinity(text))


def runtime_capabilities(brain: Any) -> dict:
    """Return the API-visible capability manifest from the runtime registry."""
    registry = getattr(brain, "capabilities", None)
    if registry is not None:
        summary = registry.runtime_summary(interface="api")
        summary.setdefault("runtime_bound", True)
        summary["capabilities"] = registry.interface_manifest("api")
        return summary

    # Compatibility fallback for lightweight tests/older bound runtime objects.
    router = getattr(brain, "model_router", None)
    model_health = router.health() if router is not None else {}
    vision = getattr(brain, "vision", None)
    computer = getattr(brain, "computer", None)
    provider = getattr(computer, "provider", None) if computer is not None else None
    return {
        "runtime_bound": True,
        "local_ai": bool(model_health) and any(model_health.values()) if model_health else router is not None,
        "memory": hasattr(brain, "memory_store"),
        "voice": hasattr(brain, "voice"),
        "vision": bool(vision and vision.available()),
        "computer_control": bool(provider and provider.available()),
        "message_pipeline": hasattr(brain, "messages") or callable(getattr(brain, "process_text", None)),
    }
