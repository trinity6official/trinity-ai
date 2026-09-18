"""Interactive Android/Termux pre-hardware Trinity test harness.

This module intentionally avoids booting the full macOS daemon stack.  It uses
Trinity's real local-model router, durable Memory Vault, memory extraction, and
permission engine so conversation quality, recall, voice plumbing, and safety
behavior can be exercised on a phone before the M5 arrives.
"""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from core.ai_service import build_local_ai_from_environment
from core.android_doctor import AndroidTrinityDoctor
from core.memory_pipeline import ConversationMemoryPipeline
from core.local_model_manager import LocalModelManager
from core.memory_store import MemoryStore
from core.models import ChatMessage
from core.permissions import PermissionEngine
from voice.local import LocalVoiceService

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ANDROID_CONFIG = PROJECT_ROOT / "config" / "android_test.yaml"


def prepare_android_environment(env: dict[str, str]) -> dict[str, str]:
    """Apply only temporary Android test overrides to an environment mapping."""
    env["TRINITY_PLATFORM_PROFILE"] = "android_termux"
    env["TRINITY_LOCAL_AI_CONFIG"] = str(ANDROID_CONFIG)
    env["TRINITY_VOICE_PROVIDER"] = "termux"
    env["TRINITY_API_ENABLED"] = "false"
    env["TRINITY_PRESENCE_ENABLED"] = "false"
    env["TRINITY_VOICE_LISTENING_ENABLED"] = "false"
    return env


def phone_readiness(env: dict[str, str] | None = None) -> tuple[bool, list[str]]:
    """Return a compact readiness result for the interactive phone harness."""
    from voice.termux import TermuxSpeechToText, TermuxTTS

    target = dict(os.environ if env is None else env)
    prepare_android_environment(target)
    details: list[str] = []
    try:
        stack = build_local_ai_from_environment(target)
        model_ok = bool(stack.provider_available)
        details.append(f"local model: {'ready' if model_ok else 'not ready'} ({stack.base_url})")
    except Exception as exc:
        model_ok = False
        details.append(f"local model: not ready ({exc})")
    tts_ok = TermuxTTS().available()
    stt_ok = TermuxSpeechToText().available()
    details.append(f"Android TTS: {'ready' if tts_ok else 'not ready'}")
    details.append(f"Android STT: {'ready' if stt_ok else 'not ready'}")
    # Voice is useful but optional; the model is the only hard requirement for text testing.
    return model_ok, details


SYSTEM_PROMPT = """You are Trinity, David's local personal AI assistant.
You are running in Android pre-hardware test mode until the M5 Pro Mac arrives.
Be concise, practical, privacy-first, and honest about limitations.
Use supplied durable memory as context, but never invent memories.
Do not claim to have performed external actions unless they actually happened.
This phone model is temporary; Trinity's identity and memory are independent of the model.
"""


@dataclass
class AndroidTestRuntime:
    root: Path
    model_manager: LocalModelManager | None = None

    def __post_init__(self) -> None:
        prepare_android_environment(os.environ)

        if self.model_manager is None:
            self.model_manager = LocalModelManager(PROJECT_ROOT)

        self.stack = build_local_ai_from_environment(os.environ)

        self.memory = MemoryStore(root=self.root / "memory")
        self.pipeline = ConversationMemoryPipeline(self.memory)
        self.permissions = PermissionEngine()
        self.voice = LocalVoiceService()
        self.history: list[ChatMessage] = []
        self.last_reply = ""

    def ask(self, text: str) -> str:
        text = (text or "").strip()
        if not text:
            return ""
        recall = self.pipeline.recall_context(text, limit=5)
        messages = [ChatMessage("system", SYSTEM_PROMPT)]
        if recall:
            messages.append(ChatMessage("system", "Relevant durable memory:\n" + recall))
        messages.extend(self.history[-8:])
        messages.append(ChatMessage("user", text))
        task = self.stack.service.classify_task(text)

        # Qwen3 thinking is useful for reasoning/coding, but on the temporary
        # Android CPU runtime it can consume hundreds of tokens before
        # producing visible text. Keep normal conversation responsive while
        # preserving thinking capability for harder tasks.
        if task in {"fast", "general"}:
            messages.append(
                ChatMessage(
                    "system",
                    "/no_think",
                )
            )

        reply = self.stack.router.chat(messages, task=task)
        self.history.extend((ChatMessage("user", text), ChatMessage("assistant", reply)))
        self.history = self.history[-16:]
        self.pipeline.persist(text, reply)
        self.last_reply = reply
        return reply

    def listen_once(self) -> str:
        if not self.voice.can_listen():
            raise RuntimeError("Android speech-to-text is unavailable. Install/configure Termux:API.")
        result = self.voice.listen("") or {}
        text = str(result.get("text", "")).strip()

        # Ignore obvious STT garbage such as isolated punctuation.
        if text and not any(ch.isalnum() for ch in text):
            return ""

        return text

    def speak(self, text: str | None = None) -> bool:
        payload = (text if text is not None else self.last_reply).strip()
        return bool(payload and self.voice.speak(payload))

    def close(self) -> None:
        """Release Android test resources."""
        self.model_manager.stop()


def _print_help() -> None:
    print("Commands: /voice  /speak  /status  /memory <query>  /text  /quit")


def interactive(root: Path) -> int:
    model_manager = LocalModelManager(PROJECT_ROOT)

    try:
        model_manager.start()
        runtime = AndroidTestRuntime(
            root,
            model_manager=model_manager,
        )
    except Exception as exc:
        model_manager.stop()
        print(f"[FAIL] Unable to start Trinity local model: {exc}")
        return 2

    try:
        if not runtime.stack.provider_available:
            print("[FAIL] llama.cpp server is not reachable.")
            return 2

        print("Trinity Android pre-hardware test is ready.")
        _print_help()

        while True:
            try:
                raw = input("You > ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0

            if not raw:
                continue

            if raw in {"/quit", "/exit"}:
                return 0

            if raw == "/help":
                _print_help()
                continue

            if raw == "/status":
                print(
                    f"Provider: {runtime.stack.provider_name} "
                    f"@ {runtime.stack.base_url}"
                )
                print(f"Model: {runtime.stack.general_model_name}")
                print(
                    f"Local server: "
                    f"{runtime.model_manager.status()}"
                )
                print("Idle model sleep: 180 seconds")
                print(
                    f"Voice in: "
                    f"{'yes' if runtime.voice.can_listen() else 'no'} "
                    f"| voice out: "
                    f"{'yes' if runtime.voice.can_speak() else 'no'}"
                )
                continue

            if raw.startswith("/memory"):
                query = raw[len("/memory"):].strip()
                rows = runtime.memory.search(
                    query or "Trinity",
                    limit=10,
                )

                for item in rows:
                    print(
                        f"- [{item.kind}/{item.category}] "
                        f"{item.content}"
                    )

                if not rows:
                    print("No matching durable memory.")

                continue

            if raw == "/speak":
                print(
                    "Spoken."
                    if runtime.speak()
                    else "TTS unavailable or nothing to speak."
                )
                continue

            if raw == "/voice":
                try:
                    raw = runtime.listen_once()
                except Exception as exc:
                    print(f"Voice error: {exc}")
                    continue

                if not raw:
                    print("No valid speech recognized.")
                    continue

                print(f"You (voice) > {raw}")

            elif raw == "/text":
                continue

            elif raw.startswith("/"):
                print(
                    f"Unknown command: {raw}. "
                    f"Type /help for available commands."
                )
                continue

            try:
                reply = runtime.ask(raw)
            except Exception as exc:
                print(f"Trinity error: {exc}")
                continue

            print(f"Trinity > {reply}")

    finally:
        runtime.close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Trinity Android pre-hardware test")
    parser.add_argument("--check", action="store_true", help="run Android readiness checks only")
    parser.add_argument("--json", action="store_true", help="JSON output for --check")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent.parent
    if args.check:
        report = AndroidTrinityDoctor(root).run()
        if args.json:
            import json
            print(json.dumps(report.to_dict(), indent=2))
        else:
            for item in report.checks:
                marker = "OK" if item.ok else ("FAIL" if item.required else "WARN")
                print(f"[{marker}] {item.name}: {item.detail}")
            print("READY" if report.ready else "NOT READY")
        return 0 if report.ready else 1
    return interactive(root)


if __name__ == "__main__":
    raise SystemExit(main())
