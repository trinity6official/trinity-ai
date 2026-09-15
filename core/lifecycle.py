"""Local runtime lifecycle and optional Telegram remote-chat polling for Trinity."""
from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any, Callable

from core.daemon import DaemonMode
from core.scheduler import RuntimeScheduler


class RuntimeLoop:
    """Own the always-on local runtime, channels, scheduling and graceful shutdown."""

    def __init__(
        self,
        host: Any,
        *,
        daemon_factory: Callable[..., Any] = DaemonMode,
        clock: Callable[[], float] = time.time,
        sleeper: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.host = host
        self.daemon_factory = daemon_factory
        self.clock = clock
        self.sleeper = sleeper
        self.now = now

    def dispatch_update(self, update: dict[str, Any]) -> None:
        """Route one Telegram update into Trinity's normal message pipeline."""
        message = update.get("message", {})
        chat_id = str(message.get("chat", {}).get("id", ""))
        if not chat_id:
            return

        text = message.get("text", "")
        if text:
            print(f"David: {text}")
            self.host.handle_message(text, chat_id)
            return

        caption = message.get("caption", "")
        if message.get("photo"):
            print(f"David sent a photo. Caption: {caption}")
            self.host.handle_photo_message(message["photo"], caption, chat_id)
            return

        doc = message.get("document")
        if not doc:
            return
        mime = doc.get("mime_type", "")
        fname = doc.get("file_name", "").lower()
        is_image = mime.startswith("image/") or fname.endswith(
            (".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic")
        )
        if is_image:
            print(f"David sent an image file: {doc.get('file_name')}. Caption: {caption}")
            self.host.handle_photo_message(
                [{"file_id": doc["file_id"], "file_size": doc.get("file_size", 0)}],
                caption,
                chat_id,
            )
        else:
            print(f"David sent a document: {doc.get('file_name')}. Caption: {caption}")
            self.host.handle_document_message(doc, caption, chat_id)

    def start_daemon_if_needed(self, hardware_mode: bool) -> None:
        """Start local background maintenance for the daemon runtime."""
        if not hardware_mode:
            return
        print("[TRINITY] Starting local daemon mode")
        self.host.daemon = self.daemon_factory(
            self.host,
            on_health_warning=self.host._handle_health_warning,
            event_bus=getattr(self.host, "events", None),
        )
        self.host.daemon.start()
        self.host.consciousness.remember(
            "Started in always-on local daemon mode",
            "episodic",
            tags=["daemon", "local", "mode"],
            outcome="success",
            importance=0.7,
        )

    def shutdown(self) -> None:
        """Stop local services and persist Trinity state."""
        print("[TRINITY] Running shutdown sequence...")
        if self.host.daemon:
            self.host.daemon.stop()
        presence_server = getattr(self.host, "presence_server", None)
        if presence_server is not None:
            presence_server.stop()
        api_server = getattr(self.host, "api_server", None)
        if api_server is not None:
            api_server.stop()
        voice_runtime = getattr(self.host, "voice_runtime", None)
        if voice_runtime is not None:
            voice_runtime.stop()
        proactive_events = getattr(self.host, "proactive_events", None)
        if proactive_events is not None:
            proactive_events.stop()
        self.host.consciousness.shutdown()
        self.host._commit_brain()
        print("[TRINITY] Shutdown complete.")

    def health_warning(self, warnings: list[str]) -> None:
        message = "Trinity Health Warning\n\n" + "".join(f"- {warning}\n" for warning in warnings)
        events = getattr(self.host, "events", None)
        if events is not None:
            events.publish("health.warning", message=message, warnings=list(warnings))
        notifier = getattr(self.host, "notify", None)
        if callable(notifier):
            notifier(message, category="health", urgent=True)
        else:
            self.host.send_telegram(message)

    def _start_optional_services(self) -> None:
        host = self.host

        presence_enabled = os.environ.get(
            "TRINITY_PRESENCE_ENABLED", "true"
        ).lower() in {"1", "true", "yes"}
        presence_server = getattr(host, "presence_server", None)
        if presence_enabled and presence_server is not None:
            if presence_server.start():
                print(f"[TRINITY] Presence UI: http://127.0.0.1:{presence_server.port}")

        api_enabled = os.environ.get("TRINITY_API_ENABLED", "true").lower() in {
            "1", "true", "yes"
        }
        api_server = getattr(host, "api_server", None)
        if api_enabled and api_server is not None:
            if api_server.start():
                print(f"[TRINITY] API: http://{api_server.host}:{api_server.port}")
            elif api_server.error:
                print(f"[TRINITY] API not started: {api_server.error}")

        voice_listening = os.environ.get(
            "TRINITY_VOICE_LISTENING_ENABLED", "false"
        ).lower() in {"1", "true", "yes"}
        voice_runtime = getattr(host, "voice_runtime", None)
        if voice_listening and voice_runtime is not None:
            if voice_runtime.start():
                print("[TRINITY] Local microphone listening enabled")
            elif voice_runtime.error:
                print(f"[TRINITY] Voice listening not started: {voice_runtime.error}")

    def _build_scheduler(self) -> RuntimeScheduler:
        host = self.host
        scheduler = RuntimeScheduler(getattr(host, "events", None))
        scheduler.add_daily(
            "morning_briefing",
            6,
            0,
            host.deliver_morning_briefing,
            last_run_date=self.now().date(),
        )
        scheduler.add_interval(
            "proactive_check",
            1800,
            host._proactive_initiative_check,
            now_seconds=self.clock(),
        )

        screen_awareness_enabled = os.environ.get(
            "TRINITY_SCREEN_AWARENESS_ENABLED", "false"
        ).lower() in {"1", "true", "yes"}
        perception = getattr(host, "perception", None)
        if screen_awareness_enabled and perception is not None:
            interval = max(
                30,
                int(os.environ.get("TRINITY_SCREEN_AWARENESS_INTERVAL_SECONDS", "300")),
            )
            scheduler.add_interval(
                "screen_awareness",
                interval,
                perception.analyze_screen,
                now_seconds=self.clock(),
            )
        return scheduler

    def run(self) -> None:
        """Run Trinity continuously on the local machine until interrupted."""
        host = self.host
        if not host._is_hardware_mode():
            raise RuntimeError(
                "RuntimeLoop.run() is only for the local daemon runtime; "
                "use `python -m core.run --mode ci` or `--mode oneshot` for finite runs"
            )

        print("\nTrinity is now running locally...")
        print("=" * 50)
        self.start_daemon_if_needed(True)
        self._start_optional_services()
        host.consciousness.set_focus("Local runtime startup")

        telegram = getattr(host, "telegram", None)
        telegram_configured = bool(getattr(telegram, "configured", False))
        offset = host.get_latest_offset() if telegram_configured else None

        startup_msg = """Trinity is online.

Local models, Memory Vault, agents and skills are ready.
Telegram is an optional remote-chat channel.
Send /help for commands or ask me anything."""
        notifier = getattr(host, "notify", None)
        if callable(notifier):
            notifier(startup_msg, category="runtime")
        elif telegram_configured:
            host.send_telegram(startup_msg)

        host.deliver_morning_briefing()
        scheduler = self._build_scheduler()
        events = getattr(host, "events", None)
        if events is not None:
            events.publish(
                "runtime.started",
                mode="local_daemon",
                telegram_remote_chat=telegram_configured,
            )

        try:
            while True:
                if telegram_configured:
                    updates = host.get_updates(offset)
                    if updates.get("ok"):
                        for update in updates.get("result", []):
                            offset = update["update_id"] + 1
                            self.dispatch_update(update)

                scheduler.tick(current=self.now(), now_seconds=self.clock())

                # Telegram long polling already blocks for ~30 seconds. When the
                # remote channel is disabled, sleep briefly to keep scheduling
                # responsive without busy-spinning.
                if not telegram_configured:
                    self.sleeper(1)
        except KeyboardInterrupt:
            print("\n[TRINITY] Interrupted - shutting down...")
        except Exception as exc:
            print(f"Trinity error: {str(exc)}")
            host.consciousness.remember(
                f"Main loop error: {type(exc).__name__}: {str(exc)[:200]}",
                "episodic",
                tags=["error", "main_loop"],
                outcome="failure",
                importance=0.8,
            )
            raise
        finally:
            self.shutdown()
