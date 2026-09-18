"""Local runtime lifecycle, scheduling and graceful shutdown for Trinity."""
from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any, Callable

from core.daemon import DaemonMode
from core.scheduler import RuntimeScheduler
from core.runtime import RuntimeMode


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

    def start_daemon_if_needed(self, hardware_mode: bool) -> None:
        """Start local background maintenance for the daemon runtime."""
        if not hardware_mode:
            return
        print("[TRINITY] Starting local daemon mode")
        self.host.daemon = self.daemon_factory(
            self.host,
            on_health_warning=self.health_warning,
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
        report = self.host.persistence.save()
        if report.success:
            print(f"[TRINITY] State persisted locally: {report.brain_path or 'memory vault'}")
        else:
            print(f"[TRINITY] Local persistence failed: {report.error}")
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
            self.host.respond(message)

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

    def _refresh_knowledge_index(self):
        """Incrementally refresh only roots David already approved."""
        skills = getattr(self.host, "skills", None)
        if skills is None:
            return None
        result = skills.execute("knowledge", "refresh_knowledge_index", {})
        if not isinstance(result, dict) or not result.get("success", False):
            error = result.get("error", "unknown error") if isinstance(result, dict) else str(result)
            raise RuntimeError(f"Knowledge refresh failed: {error}")
        events = getattr(self.host, "events", None)
        if events is not None:
            events.publish(
                "knowledge.refresh_completed",
                indexed=int(result.get("indexed", 0)),
                updated=int(result.get("updated", 0)),
                pruned_missing=int(result.get("pruned_missing", 0)),
            )
        return result

    def _build_scheduler(self) -> RuntimeScheduler:
        host = self.host
        scheduler = RuntimeScheduler(getattr(host, "events", None))
        scheduler.add_daily(
            "morning_briefing",
            6,
            0,
            host.briefings.deliver_morning,
            last_run_date=self.now().date(),
        )
        scheduler.add_interval(
            "proactive_check",
            1800,
            host.proactive_service.check,
            now_seconds=self.clock(),
        )

        knowledge_refresh_enabled = os.environ.get(
            "TRINITY_KNOWLEDGE_AUTO_REFRESH_ENABLED", "true"
        ).lower() in {"1", "true", "yes"}
        if knowledge_refresh_enabled:
            knowledge_refresh_interval = max(
                300,
                int(os.environ.get(
                    "TRINITY_KNOWLEDGE_REFRESH_INTERVAL_SECONDS", "900"
                )),
            )
            scheduler.add_interval(
                "knowledge_refresh",
                knowledge_refresh_interval,
                self._refresh_knowledge_index,
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
        if getattr(host, "runtime_mode", None) != RuntimeMode.LOCAL_DAEMON:
            raise RuntimeError(
                "RuntimeLoop.run() is only for the local daemon runtime; "
                "use `python -m core.run --mode ci` or `--mode oneshot` for finite runs"
            )

        print("\nTrinity is now running locally...")
        print("=" * 50)
        self.start_daemon_if_needed(True)
        self._start_optional_services()
        host.consciousness.set_focus("Local runtime startup")

        startup_msg = """Trinity is online.

Local models, Memory Vault, agents and skills are ready.
Local voice, API/mobile and Presence share this runtime.
Send /help from any connected interface or ask me anything."""
        notifier = getattr(host, "notify", None)
        if callable(notifier):
            notifier(startup_msg, category="runtime")
        else:
            host.respond(startup_msg)

        host.briefings.deliver_morning()
        scheduler = self._build_scheduler()
        events = getattr(host, "events", None)
        if events is not None:
            events.publish("runtime.started", mode="local_daemon")

        try:
            while True:
                scheduler.tick(current=self.now(), now_seconds=self.clock())
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
