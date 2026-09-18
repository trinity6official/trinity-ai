"""
Trinity AI — Daemon Mode (Continuous Operation)
=================================================
When Trinity runs on hardware (Mac mini M6 32 GB) instead of GitHub Actions,
it needs to handle running for days/weeks without shutdown.

Problems this solves:
  1. Working memory grows forever        → Auto-rotation with summarization
  2. Crash loses all unsaved state       → Periodic auto-save + WAL journal
  3. Memory decay only runs at boot      → Scheduled maintenance cycles
  4. Pattern detection only at boot      → Periodic analysis
  5. Energy drains to zero permanently   → Natural recovery cycles
  6. No concept of "sessions" in daemon  → Time-based session windowing
  7. No health monitoring                → Heartbeat + self-diagnostics

Usage:
    from core.trinity import Trinity
    from core.daemon import DaemonMode

    trinity = Trinity()

    daemon = DaemonMode(trinity)
    daemon.start()       # starts background maintenance thread

    # ... Trinity runs forever ...
    # daemon handles everything automatically

    daemon.stop()        # graceful shutdown (optional — handles crashes too)
"""

import os
import json
import time
import signal
import atexit
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Callable


# ─── Timing Constants (seconds) ────────────────────────────────
AUTOSAVE_INTERVAL = 120          # save brain every 2 minutes
WORKING_MEMORY_ROTATION = 1800   # summarize working memory every 30 minutes
DECAY_CYCLE = 3600               # run memory decay every hour
PATTERN_CYCLE = 1800             # detect patterns every 30 minutes
ENERGY_RECOVERY_CYCLE = 900      # energy recovery tick every 15 minutes
HEARTBEAT_INTERVAL = 60          # heartbeat every 60 seconds
HEALTH_CHECK_INTERVAL = 300      # self-diagnostics every 5 minutes
SESSION_WINDOW = 3600            # define "session" as 1-hour windows

# ─── Working Memory Limits ─────────────────────────────────────
MAX_WORKING_DAEMON = 100         # higher limit for daemon mode
ROTATION_KEEP_RECENT = 15        # keep last 15 items after rotation
ROTATION_KEEP_HIGH_PRIORITY = 25 # keep up to 25 high-priority items


class DaemonMode:
    """
    Background maintenance layer for continuous operation.

    Runs a maintenance thread that handles:
    - Periodic auto-save (crash protection)
    - Working memory rotation (prevents unbounded growth)
    - Memory decay cycles (old memories fade)
    - Pattern detection (continuous learning)
    - Energy recovery (natural rhythm)
    - Health monitoring (self-diagnostics)
    - Write-ahead log (survives mid-write crashes)
    """

    def __init__(self, trinity,
                 on_health_warning: Optional[Callable] = None, event_bus=None):
        """
        Args:
            trinity:           Trinity runtime instance
            on_health_warning: Callback for health alerts
            event_bus:          Optional EventBus for runtime awareness
        """
        self.trinity = trinity
        self.c = trinity.consciousness
        self.on_health_warning = on_health_warning
        self.event_bus = event_bus or getattr(trinity, "events", None)

        self._running = False
        self._thread = None
        self._lock = threading.Lock()  # protects brain reads/writes

        # Track timing
        self._last_save = time.time()
        self._last_rotation = time.time()
        self._last_decay = time.time()
        self._last_pattern = time.time()
        self._last_energy = time.time()
        self._last_heartbeat = time.time()
        self._last_health = time.time()
        self._session_counter = 0
        self._session_start = time.time()

        # Crash recovery
        self._wal_path = Path(str(self.c.brain_path) + ".wal")
        self._heartbeat_path = Path(str(self.c.brain_path) + ".heartbeat")

        # Stats
        self._daemon_stats = {
            "started_at": None,
            "total_saves": 0,
            "total_rotations": 0,
            "total_decay_cycles": 0,
            "total_pattern_cycles": 0,
            "crash_recoveries": 0,
            "uptime_seconds": 0,
        }

    def _emit(self, event_type: str, **payload):
        """Publish daemon lifecycle/maintenance events when an event bus is available."""
        if self.event_bus is not None:
            try:
                self.event_bus.publish(event_type, **payload)
            except Exception:
                pass

    # ═════════════════════════════════════════════════════════════
    # START / STOP
    # ═════════════════════════════════════════════════════════════

    def start(self):
        """Start the daemon maintenance thread."""
        if self._running:
            return

        # Check for crash recovery
        self._check_crash_recovery()

        self._running = True
        self._daemon_stats["started_at"] = _now()

        # Register shutdown hooks
        atexit.register(self._emergency_save)
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        # Start maintenance thread
        self._thread = threading.Thread(
            target=self._maintenance_loop,
            name="trinity-daemon",
            daemon=True,
        )
        self._thread.start()

        self.c.add_working("Daemon mode started — continuous operation active", priority="high")
        self.c.remember(
            "Daemon mode activated for continuous operation",
            "episodic",
            tags=["daemon", "mode_change"],
            importance=0.6,
        )
        self._save()

        self._emit("daemon.started")

        print(f"[DAEMON] Started — autosave every {AUTOSAVE_INTERVAL}s, "
              f"rotation every {WORKING_MEMORY_ROTATION}s")

    def stop(self):
        """Graceful shutdown."""
        if not self._running:
            return

        print("[DAEMON] Stopping...")
        self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)

        # Final maintenance pass
        with self._lock:
            self._rotate_working_memory(force=True)
            self.c._decay_memories()
            self.c._detect_patterns()
            self._save()

        # Clean up
        self._cleanup_wal()
        self._cleanup_heartbeat()

        uptime = time.time() - (self._daemon_stats.get("_start_time", time.time()))
        self._daemon_stats["uptime_seconds"] = uptime

        self.c.remember(
            f"Daemon shutdown after {_format_duration(uptime)}. "
            f"Stats: {json.dumps(self._daemon_stats, default=str)}",
            "episodic",
            tags=["daemon", "shutdown"],
            importance=0.5,
        )
        self._save()

        self._emit("daemon.stopped", uptime_seconds=uptime)
        print(f"[DAEMON] Stopped. Uptime: {_format_duration(uptime)}")

    # ═════════════════════════════════════════════════════════════
    # MAIN MAINTENANCE LOOP
    # ═════════════════════════════════════════════════════════════

    def _maintenance_loop(self):
        """Background thread — runs periodic maintenance tasks."""
        self._daemon_stats["_start_time"] = time.time()

        while self._running:
            try:
                now = time.time()

                # ── Heartbeat (every 60s)
                if now - self._last_heartbeat >= HEARTBEAT_INTERVAL:
                    self._write_heartbeat()
                    self._last_heartbeat = now
                    self._emit("daemon.heartbeat")

                # ── Auto-save (every 2 min)
                if now - self._last_save >= AUTOSAVE_INTERVAL:
                    with self._lock:
                        self._write_wal()
                        self._save()
                        self._cleanup_wal()
                    self._last_save = now
                    self._daemon_stats["total_saves"] += 1
                    self._emit("daemon.autosaved", total_saves=self._daemon_stats["total_saves"])

                # ── Energy recovery (every 15 min)
                if now - self._last_energy >= ENERGY_RECOVERY_CYCLE:
                    with self._lock:
                        self._recover_energy()
                    self._last_energy = now

                # ── Working memory rotation (every 30 min)
                if now - self._last_rotation >= WORKING_MEMORY_ROTATION:
                    with self._lock:
                        self._rotate_working_memory()
                    self._last_rotation = now
                    self._daemon_stats["total_rotations"] += 1
                    self._emit("daemon.memory_rotated", total_rotations=self._daemon_stats["total_rotations"])

                # ── Pattern detection (every 30 min)
                if now - self._last_pattern >= PATTERN_CYCLE:
                    with self._lock:
                        self.c._detect_patterns()
                        self._detect_time_patterns()
                    self._last_pattern = now
                    self._daemon_stats["total_pattern_cycles"] += 1
                    self._emit("daemon.pattern_cycle", total_cycles=self._daemon_stats["total_pattern_cycles"])

                # ── Memory decay (every hour)
                if now - self._last_decay >= DECAY_CYCLE:
                    with self._lock:
                        self.c._decay_memories()
                    self._last_decay = now
                    self._daemon_stats["total_decay_cycles"] += 1
                    self._emit("daemon.decay_cycle", total_cycles=self._daemon_stats["total_decay_cycles"])

                # ── Health check (every 5 min)
                if now - self._last_health >= HEALTH_CHECK_INTERVAL:
                    with self._lock:
                        self._health_check()
                    self._last_health = now
                    self._emit("daemon.health_checked")

                # ── Session windowing (every hour)
                if now - self._session_start >= SESSION_WINDOW:
                    with self._lock:
                        self._end_session_window()
                    self._session_start = now

            except Exception as e:
                print(f"[DAEMON] Maintenance error: {e}")
                # Don't crash the thread on errors
                self.c.remember(
                    f"Daemon maintenance error: {type(e).__name__}: {str(e)[:200]}",
                    "episodic",
                    tags=["daemon", "error"],
                    outcome="failure",
                    importance=0.7,
                )

            # Sleep in short intervals so stop() is responsive
            for _ in range(10):
                if not self._running:
                    break
                time.sleep(1)

    # ═════════════════════════════════════════════════════════════
    # WORKING MEMORY ROTATION
    # ═════════════════════════════════════════════════════════════

    def _rotate_working_memory(self, force: bool = False):
        """
        Prevent working memory from growing forever.

        Strategy:
        1. If working memory exceeds threshold, trigger rotation
        2. Summarize old items into an episodic memory
        3. Keep recent items + all high-priority items
        4. Clear the rest
        """
        working = self.c.brain.get("working", [])

        if not force and len(working) < MAX_WORKING_DAEMON:
            return

        if len(working) <= ROTATION_KEEP_RECENT:
            return

        # Split into keep vs archive
        high_priority = [w for w in working if w.get("priority") == "high"]
        recent = working[-ROTATION_KEEP_RECENT:]

        # Items to archive (everything else)
        keep_ids = set(id(w) for w in high_priority + recent)
        to_archive = [w for w in working if id(w) not in keep_ids]

        if not to_archive:
            return

        # Summarize archived items
        summary = self._summarize_for_rotation(to_archive)

        # Store summary as episodic memory
        self.c.remember(
            f"Working memory rotation ({len(to_archive)} items archived): {summary}",
            "episodic",
            tags=["memory_rotation", "auto", "daemon"],
            importance=0.4,
        )

        # Keep high priority + recent, deduplicated
        new_working = []
        seen = set()
        for w in high_priority:
            key = w["content"][:100]
            if key not in seen:
                new_working.append(w)
                seen.add(key)

        for w in recent:
            key = w["content"][:100]
            if key not in seen:
                new_working.append(w)
                seen.add(key)

        self.c.brain["working"] = new_working

        print(f"[DAEMON] Rotated working memory: {len(working)} → {len(new_working)} "
              f"({len(to_archive)} archived)")

    def _summarize_for_rotation(self, items: list) -> str:
        """Create a compact summary of working memory items being archived."""
        if not items:
            return "No items"

        # Group by priority
        high = [i["content"] for i in items if i.get("priority") == "high"]
        normal = [i["content"] for i in items if i.get("priority") != "high"]

        parts = []
        if high:
            parts.append(f"Key actions: {'; '.join(high[:5])}")
        if normal:
            # Just count normals and show a few
            parts.append(f"{len(normal)} routine actions")
            parts.append(f"Including: {'; '.join(normal[:3])}")

        # Time span
        if items:
            first_ts = items[0].get("timestamp", "?")
            last_ts = items[-1].get("timestamp", "?")
            parts.append(f"Span: {first_ts[:19]} to {last_ts[:19]}")

        return " | ".join(parts)

    # ═════════════════════════════════════════════════════════════
    # ENERGY RECOVERY
    # ═════════════════════════════════════════════════════════════

    def _recover_energy(self):
        """
        Natural energy recovery for daemon mode.

        Instead of energy only draining from boot → shutdown,
        energy follows a natural rhythm:
        - Recovers slowly when idle
        - Drains faster during heavy activity
        - Has a daily cycle (simulated circadian)
        """
        state = self.c.brain["state"]

        # Base recovery
        recovery = 0.05

        # Activity-based adjustment
        recent_ops = self.c.brain.get("operations_log", [])[-20:]
        if recent_ops:
            try:
                last_op_time = datetime.fromisoformat(
                    recent_ops[-1]["timestamp"].replace("Z", "+00:00")
                )
                idle_minutes = (datetime.now(timezone.utc) - last_op_time).total_seconds() / 60

                if idle_minutes > 15:
                    recovery = 0.10  # more recovery when idle
                elif idle_minutes < 2:
                    recovery = 0.01  # barely any recovery during heavy use
            except (ValueError, KeyError):
                pass

        # Apply recovery
        current = state.get("energy", 0.5)
        state["energy"] = min(1.0, current + recovery)

        # Also calibrate confidence toward baseline over time
        conf = state.get("confidence", 0.7)
        baseline = 0.7
        state["confidence"] = conf + (baseline - conf) * 0.05

    # ═════════════════════════════════════════════════════════════
    # SESSION WINDOWING
    # ═════════════════════════════════════════════════════════════

    def _end_session_window(self):
        """
        In daemon mode there's no shutdown, so we create artificial
        "session windows" every hour. This gives Trinity a sense of
        time passing and creates natural reflection points.
        """
        self._session_counter += 1

        working = self.c.brain.get("working", [])
        window_summary = self._summarize_for_rotation(working[-20:]) if working else "Idle period"

        self.c.remember(
            f"Session window #{self._session_counter} completed. {window_summary}",
            "episodic",
            tags=["session_window", "daemon", "auto"],
            importance=0.3,
        )

        # Update mood based on recent outcomes
        recent_ops = self.c.brain.get("operations_log", [])[-20:]
        if recent_ops:
            successes = sum(1 for o in recent_ops if o.get("result") == "success")
            failures = sum(1 for o in recent_ops if o.get("result") in ("failure", "error"))
            total = successes + failures

            if total > 0:
                success_rate = successes / total
                if success_rate >= 0.8:
                    self.c.brain["state"]["mood"] = "positive"
                elif success_rate <= 0.4:
                    self.c.brain["state"]["mood"] = "cautious"
                else:
                    self.c.brain["state"]["mood"] = "neutral"

        print(f"[DAEMON] Session window #{self._session_counter} ended")

    # ═════════════════════════════════════════════════════════════
    # TIME-BASED PATTERN DETECTION
    # ═════════════════════════════════════════════════════════════

    def _detect_time_patterns(self):
        """
        Detect patterns that only emerge over long runtimes:
        - Hour-of-day activity patterns
        - Quiet periods (nothing happening)
        - Burst activity (lots of actions in short window)
        """
        ops = self.c.brain.get("operations_log", [])
        if len(ops) < 10:
            return

        # ── Activity bursts
        recent = ops[-50:]
        timestamps = []
        for op in recent:
            try:
                ts = datetime.fromisoformat(op["timestamp"].replace("Z", "+00:00"))
                timestamps.append(ts)
            except (ValueError, KeyError):
                continue

        if len(timestamps) >= 5:
            # Check for bursts (>5 actions in 5 minutes)
            for i in range(len(timestamps) - 5):
                window = (timestamps[i + 4] - timestamps[i]).total_seconds()
                if window < 300:  # 5 minutes
                    existing = [p for p in self.c.brain.get("patterns", [])
                               if p.get("type") == "activity_burst"]
                    if not existing or len(existing) < 3:
                        self.c.brain["patterns"].append({
                            "type": "activity_burst",
                            "description": f"Burst of 5+ actions in {window:.0f}s detected",
                            "recommendation": "High activity period — ensure quality isn't sacrificed for speed",
                            "detected_at": _now(),
                            "severity": "info",
                        })
                    break

        # ── Quiet periods (no activity for 30+ minutes)
        if timestamps:
            last_action = timestamps[-1]
            idle = (datetime.now(timezone.utc) - last_action).total_seconds()
            if idle > 1800:  # 30 minutes
                self.c.add_working(
                    f"Idle for {idle/60:.0f} minutes — monitoring continues",
                    priority="normal"
                )

    # ═════════════════════════════════════════════════════════════
    # CRASH RECOVERY
    # ═════════════════════════════════════════════════════════════

    def _write_wal(self):
        """Write-ahead log — snapshot of brain before save."""
        try:
            with open(self._wal_path, "w") as f:
                json.dump(self.c.brain, f, default=str)
        except Exception as e:
            print(f"[DAEMON] WAL write failed: {e}")

    def _cleanup_wal(self):
        """Remove WAL after successful save."""
        try:
            if self._wal_path.exists():
                self._wal_path.unlink()
        except OSError:
            pass

    def _check_crash_recovery(self):
        """Check if Trinity crashed mid-operation last time."""
        had_crash = False
        crash_time = "unknown"

        # Check for stale heartbeat (means crash happened)
        if self._heartbeat_path.exists():
            try:
                with open(self._heartbeat_path) as f:
                    last_hb = json.load(f)
                crash_time = last_hb.get("timestamp", "unknown")
                had_crash = True
                self._daemon_stats["crash_recoveries"] += 1
                print(f"[DAEMON] Crash recovery — last heartbeat was {crash_time}")
            except (json.JSONDecodeError, OSError):
                pass

        # Check for WAL (means save was interrupted) — restore BEFORE logging
        if self._wal_path.exists():
            try:
                with open(self._wal_path) as f:
                    wal_brain = json.load(f)

                # WAL is more recent than main brain — restore it
                brain_mtime = self.c.brain_path.stat().st_mtime if self.c.brain_path.exists() else 0
                wal_mtime = self._wal_path.stat().st_mtime

                if wal_mtime > brain_mtime:
                    print("[DAEMON] Restoring from WAL (more recent than brain file)")
                    self.c.brain = self.c._migrate(wal_brain)
                    self._save()

                self._cleanup_wal()
            except (json.JSONDecodeError, OSError) as e:
                print(f"[DAEMON] WAL recovery failed: {e}")
                self._cleanup_wal()

        # Log crash AFTER WAL restore so the memory isn't overwritten
        if had_crash:
            self.c.remember(
                f"Recovered from crash/unexpected shutdown. Last heartbeat: {crash_time}",
                "episodic",
                tags=["crash", "recovery", "daemon"],
                outcome="failure",
                importance=0.9,
            )

        self._cleanup_heartbeat()

    def _write_heartbeat(self):
        """Write heartbeat file — absence of this on next boot means crash."""
        try:
            with open(self._heartbeat_path, "w") as f:
                json.dump({
                    "timestamp": _now(),
                    "uptime": time.time() - self._daemon_stats.get("_start_time", time.time()),
                    "energy": self.c.brain["state"].get("energy", 0),
                    "working_memory_size": len(self.c.brain.get("working", [])),
                    "pid": os.getpid(),
                }, f)
        except OSError:
            pass

    def _cleanup_heartbeat(self):
        """Remove heartbeat file (indicates clean state)."""
        try:
            if self._heartbeat_path.exists():
                self._heartbeat_path.unlink()
        except OSError:
            pass

    # ═════════════════════════════════════════════════════════════
    # HEALTH MONITORING
    # ═════════════════════════════════════════════════════════════

    def _health_check(self):
        """Run self-diagnostics and alert on issues."""
        warnings = []
        state = self.c.brain["state"]
        stats = self.c.get_memory_stats()

        # Memory pressure
        if stats["episodic_count"] > 450:
            warnings.append(f"Episodic memory at {stats['episodic_count']}/500 — approaching limit")
        if stats["operations_logged"] > 180:
            warnings.append(f"Operations log at {stats['operations_logged']}/200 — old entries will be pruned")

        # Energy
        if state.get("energy", 0) < 0.15:
            warnings.append(f"Energy critically low: {state['energy']:.0%}")

        # Confidence drift
        if state.get("confidence", 0.7) < 0.3:
            warnings.append(f"Confidence very low: {state['confidence']:.0%} — too many failures?")

        # Brain file size
        try:
            brain_size = self.c.brain_path.stat().st_size
            if brain_size > 5_000_000:  # 5MB
                warnings.append(f"Brain file is {brain_size/1_000_000:.1f}MB — consider pruning")
        except OSError:
            pass

        # Working memory buildup
        working_count = len(self.c.brain.get("working", []))
        if working_count > 80:
            warnings.append(f"Working memory at {working_count} items — rotation may be failing")

        # Report warnings
        if warnings:
            warning_str = "; ".join(warnings)
            self.c.add_working(f"Health warning: {warning_str}", priority="high")
            print(f"[DAEMON] Health warnings: {warning_str}")
            self._emit("health.warning", message=warning_str, warnings=list(warnings))

            if self.on_health_warning:
                try:
                    self.on_health_warning(warnings)
                except Exception as e:
                    print(f"[DAEMON] Health callback failed: {e}")

    # ═════════════════════════════════════════════════════════════
    # SIGNAL HANDLING
    # ═════════════════════════════════════════════════════════════

    def _handle_signal(self, signum, frame):
        """Handle SIGTERM/SIGINT gracefully."""
        sig_name = signal.Signals(signum).name
        print(f"\n[DAEMON] Received {sig_name} — shutting down gracefully...")
        self.c.remember(
            f"Received {sig_name} — performing graceful shutdown",
            "episodic",
            tags=["signal", "shutdown", "daemon"],
            importance=0.6,
        )
        self.stop()
        # After stopping daemon, let the original signal handler run
        raise SystemExit(0)

    def _emergency_save(self):
        """Last-resort save on unexpected exit."""
        if self._running:
            try:
                self.c.save()
                print("[DAEMON] Emergency save completed")
            except Exception:
                pass

    # ═════════════════════════════════════════════════════════════
    # HELPERS
    # ═════════════════════════════════════════════════════════════

    def _save(self):
        """Save with error handling."""
        try:
            self.c.save()
        except Exception as e:
            print(f"[DAEMON] Save failed: {e}")
            self._emit("daemon.save_failed", error=str(e))

    def get_daemon_stats(self) -> dict:
        """Return daemon operation stats."""
        stats = self._daemon_stats.copy()
        stats.pop("_start_time", None)
        if self._running:
            start = self._daemon_stats.get("_start_time", time.time())
            stats["uptime_seconds"] = time.time() - start
            stats["uptime_human"] = _format_duration(stats["uptime_seconds"])
        return stats

    @property
    def lock(self):
        """Expose lock for external code that needs thread-safe brain access."""
        return self._lock


# ═════════════════════════════════════════════════════════════════
# THREAD-SAFE WRAPPER
# ═════════════════════════════════════════════════════════════════

class ThreadSafeTrinity:
    """
    Thread-safe compatibility wrapper around a Trinity runtime instance.
    Use this when running in daemon mode.

    Usage:
        trinity = Trinity()
        daemon = DaemonMode(trinity)
        safe = ThreadSafeTrinity(trinity, daemon)

        # Now safe.* methods can be called from any thread
        safe.remember("something happened")
        safe.execute_skill("github", "list_issues", ...)
    """

    def __init__(self, trinity, daemon: DaemonMode):
        self._trinity = trinity
        self._lock = daemon.lock

    def remember(self, what, **kwargs):
        with self._lock:
            return self._trinity.remember(what, **kwargs)

    def learn(self, fact, **kwargs):
        with self._lock:
            return self._trinity.learn(fact, **kwargs)

    def recall(self, query, **kwargs):
        with self._lock:
            return self._trinity.recall(query, **kwargs)

    def execute_skill(self, skill_name, method, args=None, execute_fn=None):
        with self._lock:
            return self._trinity.execute_skill(skill_name, method, args, execute_fn)

    def decide(self, decision, reasoning, **kwargs):
        with self._lock:
            return self._trinity.decide(decision, reasoning, **kwargs)

    def set_focus(self, focus):
        with self._lock:
            return self._trinity.set_focus(focus)

    def build_system_prompt(self, base_prompt):
        with self._lock:
            return self._trinity.build_system_prompt(base_prompt)

    @property
    def state(self):
        with self._lock:
            return self._trinity.state

    @property
    def stats(self):
        with self._lock:
            return self._trinity.stats


# ═════════════════════════════════════════════════════════════════
# UTILITIES
# ═════════════════════════════════════════════════════════════════

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _format_duration(seconds: float) -> str:
    """Format seconds into human-readable duration."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.0f}m"
    elif seconds < 86400:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h}h {m}m"
    else:
        d = int(seconds // 86400)
        h = int((seconds % 86400) // 3600)
        return f"{d}d {h}h"
