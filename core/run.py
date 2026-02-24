# “””
Trinity AI — Dual-Mode Runner

Detects environment and runs in the right mode:

- GitHub Actions → boot/shutdown cycle (50 min)
- Mac Mini / hardware → daemon mode (runs forever)

Usage:
python core/run.py                   # auto-detect
python core/run.py –mode=actions    # force Actions mode
python core/run.py –mode=daemon     # force daemon mode
“””

import os
import sys
import time
import argparse

from core.consciousness_integration import ConsciousTrinity
from core.daemon import DaemonMode, ThreadSafeTrinity

def detect_mode() -> str:
“”“Auto-detect whether we’re on GitHub Actions or hardware.”””
if os.getenv(“GITHUB_ACTIONS”) == “true”:
return “actions”
if os.getenv(“CI”):
return “actions”
return “daemon”

def send_telegram_alert(warnings: list):
“””
Replace with your real Telegram notification code.
This is the callback for daemon health warnings.
“””
# from skills.telegram_skill import send_message
msg = “⚠️ Trinity Health Warning:\n” + “\n”.join(f”• {w}” for w in warnings)
print(f”[TELEGRAM] {msg}”)
# send_message(msg)

def run_actions_mode():
“””
GitHub Actions mode — 50 minute execution window.
Boot → do work → shutdown → commit brain.
“””
print(”=” * 60)
print(“TRINITY AI — GitHub Actions Mode”)
print(”=” * 60)

```
trinity = ConsciousTrinity()
trinity.boot()

try:
    # ── Your existing 50-minute work loop ──
    # Replace this with your actual trinity cycle
    trinity.set_focus("Scheduled Actions run")

    # Example work cycle
    trinity.learn("Running in GitHub Actions mode", tags=["environment"])
    trinity.remember("Actions run started", tags=["actions", "boot"])

    # ... your skill execution here ...
    # trinity.execute_skill("github_skill", "check_issues", ...)
    # trinity.execute_skill("web_skill", "monitor", ...)

    time.sleep(2)  # placeholder for actual work

except Exception as e:
    trinity.remember(
        f"Actions run error: {e}",
        tags=["error", "actions"],
        outcome="failure",
        importance=0.9,
    )
finally:
    trinity.shutdown()

# Commit brain to repo
os.system("git config user.name 'Trinity AI' 2>/dev/null")
os.system("git config user.email 'trinity@trinity6.com' 2>/dev/null")
os.system("git add trinity_brain.json 2>/dev/null")
os.system('git diff --cached --quiet 2>/dev/null || '
          'git commit -m "🧠 Trinity brain update" 2>/dev/null')
os.system("git push 2>/dev/null")
```

def run_daemon_mode():
“””
Hardware mode — runs continuously until stopped.
Handles its own memory management, saves, and git commits.
“””
print(”=” * 60)
print(“TRINITY AI — Daemon Mode (Continuous)”)
print(”=” * 60)

```
trinity = ConsciousTrinity()
trinity.boot()

# Start daemon with health callback
daemon = DaemonMode(
    trinity,
    git_commit=True,
    on_health_warning=send_telegram_alert,
)
daemon.start()

# Thread-safe wrapper for multi-threaded access
safe = ThreadSafeTrinity(trinity, daemon)

# Seed daemon-specific knowledge
safe.learn("Running in daemon mode on dedicated hardware", tags=["environment", "daemon"])
safe.learn("No 50-minute time limit — continuous operation", tags=["environment", "daemon"])

try:
    # ── Main loop — runs forever ──
    cycle = 0
    while True:
        cycle += 1

        # Your main Trinity logic goes here
        # This runs your skill checks, LLM calls, etc.

        safe.set_focus(f"Daemon cycle #{cycle}")

        # ── Example: periodic task checks ──

        # Check GitHub every 5 minutes
        if cycle % 5 == 0:
            try:
                safe.execute_skill(
                    "github_skill", "check_notifications",
                    args={"repo": "trinity6official/trinity-ai"},
                    execute_fn=lambda: {"notifications": []},  # replace
                )
            except Exception as e:
                safe.remember(
                    f"GitHub check failed: {e}",
                    tags=["github", "error"],
                    outcome="failure",
                )

        # Monitor website every 3 minutes
        if cycle % 3 == 0:
            try:
                safe.execute_skill(
                    "web_skill", "check_uptime",
                    args={"url": "https://trinity6.com"},
                    execute_fn=lambda: {"status": 200},  # replace
                )
            except Exception as e:
                safe.remember(
                    f"Uptime check failed: {e}",
                    tags=["monitoring", "error"],
                    outcome="failure",
                )

        # Print status every 10 cycles
        if cycle % 10 == 0:
            stats = safe.stats
            dstats = daemon.get_daemon_stats()
            print(f"[CYCLE {cycle}] "
                  f"Memories: {stats['episodic_count']}E/{stats['semantic_count']}S "
                  f"| Ops: {stats['operations_logged']} "
                  f"| Saves: {dstats['total_saves']} "
                  f"| Rotations: {dstats['total_rotations']} "
                  f"| Uptime: {dstats.get('uptime_human', '?')}")

        # Sleep between cycles (adjust to your needs)
        # 60 seconds = check things every minute
        time.sleep(60)

except (KeyboardInterrupt, SystemExit):
    print("\n[TRINITY] Shutting down...")
finally:
    daemon.stop()
    trinity.shutdown()
    print("[TRINITY] Goodbye.")
```

# ═══════════════════════════════════════════════════════════════

def main():
parser = argparse.ArgumentParser(description=“Trinity AI Runner”)
parser.add_argument(”–mode”, choices=[“actions”, “daemon”, “auto”],
default=“auto”, help=“Operation mode”)
args = parser.parse_args()

```
if args.mode == "auto":
    mode = detect_mode()
    print(f"[TRINITY] Auto-detected mode: {mode}")
else:
    mode = args.mode

if mode == "actions":
    run_actions_mode()
else:
    run_daemon_mode()
```

if **name** == “**main**”:
main()
