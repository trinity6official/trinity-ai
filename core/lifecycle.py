"""Local runtime lifecycle, scheduling and graceful shutdown for Trinity."""
from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any, Callable

from core.daemon import DaemonMode
from core.scheduler import PersistentScheduler
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
        scheduler_path: str = "memory/runtime/schedules.db",
    ) -> None:
        self.host = host
        self.daemon_factory = daemon_factory
        self.clock = clock
        self.sleeper = sleeper
        self.now = now
        self.scheduler_path = scheduler_path

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
        mcp = getattr(self.host, "mcp", None)
        if mcp is not None:
            mcp.stop_all()
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

        mcp_enabled = os.environ.get("TRINITY_MCP_ENABLED", "true").lower() in {
            "1", "true", "yes"
        }
        mcp = getattr(host, "mcp", None)
        if mcp_enabled and mcp is not None:
            for name, health in mcp.start_enabled().items():
                if health.healthy:
                    print(f"[TRINITY] MCP server ready: {name}")
                elif health.last_error:
                    print(f"[TRINITY] MCP server not started ({name}): {health.last_error}")

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

    def _scheduled_handler(self, name: str, callback: Callable[[], Any]):
        """Wrap scheduled work with scheduler lifecycle events.

        ProcessManager owns retries/cancellation/timeouts; this wrapper preserves
        the scheduler-facing awareness/event contract around the actual callback.
        """
        events = getattr(self.host, "events", None)

        def handler(context, _payload):
            if events is not None:
                events.publish("scheduler.task_started", task=name, process_id=context.process_id)
            try:
                context.checkpoint()
                result = callback()
                context.checkpoint()
            except Exception as exc:
                if events is not None:
                    events.publish(
                        "scheduler.task_failed",
                        task=name,
                        process_id=context.process_id,
                        error=str(exc),
                    )
                raise
            if events is not None:
                events.publish(
                    "scheduler.task_completed",
                    task=name,
                    process_id=context.process_id,
                )
            return result

        return handler

    def _build_scheduler(self) -> PersistentScheduler:
        host = self.host
        processes = getattr(host, "processes", None)
        if processes is None:
            raise RuntimeError("PersistentScheduler requires Trinity's ProcessManager")

        scheduler = PersistentScheduler(
            processes,
            self.scheduler_path,
            event_bus=getattr(host, "events", None),
        )
        current = self.now()

        processes.register_handler(
            "schedule.morning_briefing",
            self._scheduled_handler("morning_briefing", host.briefings.deliver_morning),
        )
        scheduler.add_daily(
            "morning_briefing",
            6,
            0,
            "schedule.morning_briefing",
            start_at=current,
        )

        processes.register_handler(
            "schedule.proactive_check",
            self._scheduled_handler("proactive_check", host.proactive_service.check),
        )
        scheduler.add_interval(
            "proactive_check",
            1800,
            "schedule.proactive_check",
            start_at=current,
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
            processes.register_handler(
                "schedule.knowledge_refresh",
                self._scheduled_handler("knowledge_refresh", self._refresh_knowledge_index),
            )
            scheduler.add_interval(
                "knowledge_refresh",
                knowledge_refresh_interval,
                "schedule.knowledge_refresh",
                start_at=current,
            )
        elif scheduler.get("knowledge_refresh") is not None:
            scheduler.pause("knowledge_refresh")

        screen_awareness_enabled = os.environ.get(
            "TRINITY_SCREEN_AWARENESS_ENABLED", "false"
        ).lower() in {"1", "true", "yes"}
        perception = getattr(host, "perception", None)
        if screen_awareness_enabled and perception is not None:
            interval = max(
                30,
                int(os.environ.get("TRINITY_SCREEN_AWARENESS_INTERVAL_SECONDS", "300")),
            )
            processes.register_handler(
                "schedule.screen_awareness",
                self._scheduled_handler("screen_awareness", perception.analyze_screen),
            )
            scheduler.add_interval(
                "screen_awareness",
                interval,
                "schedule.screen_awareness",
                start_at=current,
            )
        elif scheduler.get("screen_awareness") is not None:
            scheduler.pause("screen_awareness")
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

        scheduler = self._build_scheduler()
        events = getattr(host, "events", None)
        if events is not None:
            events.publish("runtime.started", mode="local_daemon")

        try:
            while True:
                scheduler.tick(current=self.now())
                # Keep queue draining bounded so one hot producer cannot starve
                # runtime health/voice/presence ticks. Handlers themselves remain
                # synchronous and cooperative with ProcessManager cancellation.
                for _ in range(4):
                    if host.processes.run_next() is None:
                        break
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
