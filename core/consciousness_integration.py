# “””
Trinity AI — Consciousness Integration

Drop-in integration for Trinity’s existing architecture.

This module wraps the Consciousness engine into Trinity’s skill/action
pattern so every tool call, decision, and interaction flows through
the memory system automatically.

Usage in core/trinity.py:
from core.consciousness_integration import ConsciousTriinity

```
trinity = ConsciousTriinity()
trinity.boot()
# ... run your 50-minute loop ...
trinity.shutdown()
```

“””

import time
import traceback
from functools import wraps
from core.consciousness import Consciousness

class ConsciousTrinity:
“””
Wraps Trinity’s brain with consciousness.

```
This is the main integration point. It:
1. Loads trinity_brain.json at boot
2. Injects consciousness context into every LLM call
3. Logs every tool call automatically
4. Logs every decision
5. Saves state after every action cycle
6. Summarizes and persists at shutdown
"""

def __init__(self, brain_path: str = "trinity_brain.json"):
    self.consciousness = Consciousness(brain_path)
    self.is_booted = False

def boot(self):
    """Call at the start of every GitHub Actions run."""
    self.consciousness.boot()
    self.is_booted = True
    print(f"[TRINITY] {self.consciousness}")

def shutdown(self):
    """Call at the end of every run."""
    self.consciousness.shutdown()
    self.is_booted = False
    print(f"[TRINITY] Shutdown complete. {self.consciousness}")

# ─── LLM Integration ────────────────────────────────────────

def build_system_prompt(self, base_prompt: str) -> str:
    """
    Inject consciousness context into the system prompt.
    Call this before every Anthropic API request.

    Example:
        prompt = trinity.build_system_prompt(your_existing_system_prompt)
        response = anthropic.messages.create(
            system=prompt,
            messages=[...],
        )
    """
    consciousness_block = self.consciousness.get_context()
    return f"{base_prompt}\n\n{consciousness_block}"

def process_response(self, response_text: str, action_taken: str = None):
    """
    Call after receiving LLM response. Updates working memory.
    """
    self.consciousness.add_working(
        f"LLM response received. Action: {action_taken or 'none'}",
        priority="normal"
    )
    self.consciousness.save()

# ─── Skill Execution Wrapper ────────────────────────────────

def execute_skill(self, skill_name: str, method: str,
                  args: dict = None, execute_fn=None):
    """
    Wrap any skill call with automatic consciousness logging.

    Args:
        skill_name:  e.g. "github_skill"
        method:      e.g. "create_issue"
        args:        arguments passed to the skill
        execute_fn:  callable that performs the actual skill work

    Returns:
        The result of execute_fn, with logging side effects.

    Example:
        result = trinity.execute_skill(
            "github_skill", "create_issue",
            args={"title": "Fix auth", "body": "..."},
            execute_fn=lambda: github_skill.create_issue(title="Fix auth", body="...")
        )
    """
    tool = f"{skill_name}.{method}"
    start = time.time()

    self.consciousness.add_working(f"Executing: {tool}", priority="high")

    try:
        result = execute_fn() if execute_fn else None
        duration = (time.time() - start) * 1000

        self.consciousness.log_operation(
            tool=tool,
            args=args or {},
            result="success",
            details=str(result)[:300] if result else "completed",
            duration_ms=duration,
        )
        self.consciousness.save()
        return result

    except Exception as e:
        duration = (time.time() - start) * 1000
        error_details = f"{type(e).__name__}: {str(e)}"

        self.consciousness.log_operation(
            tool=tool,
            args=args or {},
            result="error",
            details=error_details[:300],
            duration_ms=duration,
        )
        self.consciousness.save()
        raise

def decide(self, decision: str, reasoning: str,
           alternatives: list = None, confidence: float = 0.7,
           context: str = ""):
    """
    Log a decision with full reasoning.
    Call this whenever Trinity chooses between options.

    Example:
        trinity.decide(
            decision="Fix auth bug before adding new feature",
            reasoning="3 users reported auth failures in the last hour, "
                      "this is higher severity than the feature request",
            alternatives=["Work on OAuth feature", "Update documentation"],
            confidence=0.85,
            context="Morning triage cycle"
        )
    """
    self.consciousness.log_decision(
        decision=decision,
        reasoning=reasoning,
        alternatives=alternatives,
        confidence=confidence,
        context=context,
    )
    self.consciousness.save()

# ─── Memory Shortcuts ────────────────────────────────────────

def remember(self, what: str, tags: list = None, outcome: str = None,
             importance: float = 0.5):
    """Quick episodic memory."""
    self.consciousness.remember(what, "episodic", tags=tags,
                                outcome=outcome, importance=importance)
    self.consciousness.save()

def learn(self, fact: str, tags: list = None, confidence: float = 0.8):
    """Quick semantic memory."""
    self.consciousness.learn(fact, tags=tags, confidence=confidence)
    self.consciousness.save()

def recall(self, query: str, limit: int = 5) -> list:
    """Search memories."""
    return self.consciousness.recall(query, limit=limit)

def set_focus(self, focus: str):
    self.consciousness.set_focus(focus)
    self.consciousness.save()

@property
def state(self):
    return self.consciousness.get_state()

@property
def stats(self):
    return self.consciousness.get_memory_stats()
```

def conscious_skill(skill_name: str):
“””
Decorator factory for skill methods.
Automatically logs operations through consciousness.

```
Usage:
    class GitHubSkill:
        def __init__(self, trinity: ConsciousTrinity):
            self.trinity = trinity

        @conscious_skill("github")
        def create_issue(self, title, body=""):
            # ... your existing code ...
            return issue

The decorator will:
- Log the call to operations_log
- Track success/failure
- Measure duration
- Store failures as episodic memories
"""
def decorator(fn):
    @wraps(fn)
    def wrapper(self, *args, **kwargs):
        trinity = getattr(self, 'trinity', None)
        if trinity is None:
            return fn(self, *args, **kwargs)

        method = fn.__name__
        tool = f"{skill_name}.{method}"
        start = time.time()

        try:
            result = fn(self, *args, **kwargs)
            duration = (time.time() - start) * 1000
            trinity.consciousness.log_operation(
                tool=tool, args=kwargs or {},
                result="success",
                details=str(result)[:300] if result else "ok",
                duration_ms=duration,
            )
            return result
        except Exception as e:
            duration = (time.time() - start) * 1000
            trinity.consciousness.log_operation(
                tool=tool, args=kwargs or {},
                result="error",
                details=f"{type(e).__name__}: {e}"[:300],
                duration_ms=duration,
            )
            raise

    return wrapper
return decorator
```
