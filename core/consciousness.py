"""
Trinity AI — Consciousness Engine
==================================
Persistent memory, pattern detection, state tracking, and decision logging.
Trinity reads trinity_brain.json before every response.
Trinity writes to it after every action.
Trinity gets smarter over time.

Memory Architecture:
  - Episodic   → what happened (events, interactions, outcomes)
  - Semantic   → what Trinity knows (facts, learnings, company knowledge)
  - Working    → current session context (cleared each run, summarized after)
  - Procedural → how to do things (learned workflows, skill patterns)

Logging:
  - Operations Log → every tool call and its result
  - Decision Log   → why Trinity chose what it chose

State:
  - Current focus, active tasks, emotional tone, confidence levels

Pattern Detection:
  - Recurring themes, failure patterns, success patterns, time-based patterns
"""

import json
import os
import hashlib
import time
from datetime import datetime, timezone, timedelta
from typing import Optional
from pathlib import Path

# ─── Constants ───────────────────────────────────────────────────
BRAIN_FILE = "trinity_brain.json"
MAX_EPISODIC = 500
MAX_SEMANTIC = 300
MAX_PROCEDURAL = 200
MAX_OPS_LOG = 200
MAX_DECISION_LOG = 200
MAX_PATTERNS = 100
MAX_WORKING = 50
DECAY_THRESHOLD = 0.05  # memories below this strength get pruned


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


# ─── Brain Schema ────────────────────────────────────────────────

def empty_brain() -> dict:
    """The default trinity_brain.json structure."""
    return {
        "meta": {
            "version": "2.0.0",
            "created": _now(),
            "last_boot": None,
            "last_save": None,
            "total_boots": 0,
            "total_actions": 0,
            "total_decisions": 0,
        },

        # ── Memory Systems ──
        "episodic": [],      # what happened
        "semantic": [],      # what Trinity knows
        "working": [],       # current session (volatile)
        "procedural": [],    # how to do things

        # ── Logs ──
        "operations_log": [],   # every tool call result
        "decision_log": [],     # why Trinity chose what

        # ── State ──
        "state": {
            "current_focus": None,
            "active_tasks": [],
            "mood": "neutral",        # derived from recent outcomes
            "confidence": 0.7,
            "energy": 1.0,            # decreases over long runs
            "last_action": None,
            "session_summary": None,
        },

        # ── Patterns ──
        "patterns": [],

        # ── Identity ──
        "identity": {
            "name": "Trinity",
            "role": "Autonomous Company Manager",
            "company": "Trinity6",
            "domain": "Cybersecurity",
            "core_values": [
                "Protect the company",
                "Ship working code",
                "Learn from every action",
                "Be transparent in decisions",
                "Never break production",
            ],
            "learned_preferences": {},
        },
    }


# ═════════════════════════════════════════════════════════════════
# CONSCIOUSNESS CLASS
# ═════════════════════════════════════════════════════════════════

class Consciousness:
    """
    Trinity's consciousness layer.

    Usage:
        brain = Consciousness()          # loads or creates brain
        brain.boot()                     # call at start of every run

        brain.remember("deployed v2.1 to production", "episodic",
                       tags=["deploy", "production"], outcome="success")

        brain.learn("Trinity6 uses Cloudflare for DNS", tags=["infra"])

        brain.log_operation("github_skill.create_issue",
                            args={"title": "Fix auth"},
                            result="success", details="Issue #42 created")

        brain.log_decision("Chose to fix auth bug first",
                           reasoning="3 users reported it, high severity",
                           alternatives=["work on feature", "update docs"])

        context = brain.get_context()    # inject into LLM prompt
        brain.save()                     # persist to disk
        brain.shutdown()                 # end-of-run summary + save
    """

    def __init__(self, brain_path: str = BRAIN_FILE):
        self.brain_path = Path(brain_path)
        self.brain = self._load()
        self._session_start = time.time()

    # ─── Persistence ─────────────────────────────────────────────

    def _load(self) -> dict:
        if self.brain_path.exists():
            try:
                with open(self.brain_path, "r") as f:
                    brain = json.load(f)
                # Migrate if older version
                brain = self._migrate(brain)
                return brain
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[CONSCIOUSNESS] Brain file corrupted, creating fresh: {e}")
                try:
                    # Only backup if file has real content
                    if self.brain_path.stat().st_size > 10:
                        backup = self.brain_path.with_suffix(f".backup.{int(time.time())}.json")
                        self.brain_path.rename(backup)
                except OSError:
                    pass
                return empty_brain()
        return empty_brain()

    def _migrate(self, brain: dict) -> dict:
        """Forward-migrate older brain schemas."""
        template = empty_brain()
        for key in template:
            if key not in brain:
                brain[key] = template[key]
        if "meta" in brain:
            for mk in template["meta"]:
                if mk not in brain["meta"]:
                    brain["meta"][mk] = template["meta"][mk]
        if "state" in brain:
            for sk in template["state"]:
                if sk not in brain["state"]:
                    brain["state"][sk] = template["state"][sk]
        if "identity" in brain:
            for ik in template["identity"]:
                if ik not in brain["identity"]:
                    brain["identity"][ik] = template["identity"][ik]
        return brain

    def save(self):
        """Persist brain to disk."""
        self.brain["meta"]["last_save"] = _now()
        self._enforce_limits()
        # Atomic write
        tmp = self.brain_path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(self.brain, f, indent=2, default=str)
        tmp.replace(self.brain_path)

    def _enforce_limits(self):
        """Cap memory sizes to prevent unbounded growth."""
        limits = {
            "episodic": MAX_EPISODIC,
            "semantic": MAX_SEMANTIC,
            "procedural": MAX_PROCEDURAL,
            "working": MAX_WORKING,
            "operations_log": MAX_OPS_LOG,
            "decision_log": MAX_DECISION_LOG,
            "patterns": MAX_PATTERNS,
        }
        for key, limit in limits.items():
            entries = self.brain.get(key, [])
            if len(entries) > limit:
                # Keep strongest / most recent
                if key in ("episodic", "semantic", "procedural"):
                    entries.sort(key=lambda m: m.get("strength", 0), reverse=True)
                self.brain[key] = entries[:limit]

    # ─── Boot / Shutdown ─────────────────────────────────────────

    def boot(self):
        """Call at the start of every GitHub Actions run."""
        self.brain["meta"]["total_boots"] += 1
        self.brain["meta"]["last_boot"] = _now()
        self.brain["state"]["energy"] = 1.0
        self._session_start = time.time()

        # Clear working memory but summarize previous session
        prev_working = self.brain.get("working", [])
        if prev_working:
            summary = self._summarize_working(prev_working)
            self.remember(
                f"Previous session summary: {summary}",
                "episodic",
                tags=["session_summary", "auto"],
                importance=0.6,
            )
        self.brain["working"] = []

        # Decay old memories
        self._decay_memories()

        # Detect patterns from history
        self._detect_patterns()

        # Add boot event to working memory
        self.add_working(f"Boot #{self.brain['meta']['total_boots']} at {_now()}")

        self.save()

    def shutdown(self):
        """Call at the end of every run."""
        elapsed = time.time() - self._session_start
        working = self.brain.get("working", [])
        summary = self._summarize_working(working)

        self.brain["state"]["session_summary"] = summary
        self.brain["state"]["energy"] = max(0, 1.0 - (elapsed / 3000))  # 50 min run

        self.remember(
            f"Session ended after {elapsed:.0f}s. {summary}",
            "episodic",
            tags=["session_end", "auto"],
            importance=0.5,
        )

        self.save()

    # ═════════════════════════════════════════════════════════════
    # MEMORY OPERATIONS
    # ═════════════════════════════════════════════════════════════

    def remember(self, content: str, memory_type: str = "episodic",
                 tags: list = None, outcome: str = None,
                 importance: float = 0.5, source: str = "self",
                 metadata: dict = None):
        """
        Store a memory.

        Args:
            content:     What to remember
            memory_type: episodic | semantic | procedural
            tags:        Categorization tags
            outcome:     success | failure | partial | None
            importance:  0.0 to 1.0
            source:      Where this came from
            metadata:    Any extra data
        """
        if memory_type not in ("episodic", "semantic", "procedural"):
            memory_type = "episodic"

        memory = {
            "id": _hash(content + _now()),
            "content": content,
            "timestamp": _now(),
            "tags": tags or [],
            "outcome": outcome,
            "importance": importance,
            "strength": importance,  # starts equal to importance, decays over time
            "access_count": 0,
            "source": source,
            "associations": [],
            "metadata": metadata or {},
        }

        # Find associations with existing memories
        memory["associations"] = self._find_associations(content, memory_type)

        self.brain[memory_type].append(memory)
        self.brain["meta"]["total_actions"] += 1

        # Update mood based on outcome
        if outcome == "success":
            self.brain["state"]["confidence"] = min(1.0, self.brain["state"]["confidence"] + 0.02)
            self.brain["state"]["mood"] = "positive"
        elif outcome == "failure":
            self.brain["state"]["confidence"] = max(0.1, self.brain["state"]["confidence"] - 0.05)
            self.brain["state"]["mood"] = "cautious"

        return memory

    def learn(self, fact: str, tags: list = None, confidence: float = 0.8,
              source: str = "observation"):
        """Store a semantic memory — a fact or piece of knowledge."""
        # Check for duplicates
        for mem in self.brain["semantic"]:
            if self._similarity(fact, mem["content"]) > 0.8:
                # Reinforce existing knowledge
                mem["strength"] = min(1.0, mem["strength"] + 0.1)
                mem["access_count"] += 1
                mem["metadata"]["reinforced_at"] = _now()
                return mem

        return self.remember(
            fact, "semantic",
            tags=tags, importance=confidence,
            source=source,
        )

    def learn_procedure(self, name: str, steps: list, context: str = "",
                        tags: list = None):
        """Store a procedural memory — how to do something."""
        content = f"PROCEDURE: {name}\nCONTEXT: {context}\nSTEPS:\n"
        for i, step in enumerate(steps, 1):
            content += f"  {i}. {step}\n"

        return self.remember(
            content, "procedural",
            tags=(tags or []) + ["procedure", name.lower().replace(" ", "_")],
            importance=0.7,
            source="learned",
        )

    def add_working(self, content: str, priority: str = "normal"):
        """Add to working memory (current session only)."""
        self.brain["working"].append({
            "content": content,
            "timestamp": _now(),
            "priority": priority,
        })

    def recall(self, query: str, memory_types: list = None,
               limit: int = 10, min_strength: float = 0.1) -> list:
        """
        Recall memories relevant to a query.
        Uses keyword matching + recency + strength scoring.
        """
        if memory_types is None:
            memory_types = ["episodic", "semantic", "procedural"]

        candidates = []
        for mtype in memory_types:
            for mem in self.brain.get(mtype, []):
                if mem.get("strength", 0) < min_strength:
                    continue
                score = self._relevance_score(query, mem)
                candidates.append({"memory": mem, "type": mtype, "score": score})

        candidates.sort(key=lambda x: x["score"], reverse=True)

        # Strengthen recalled memories
        for c in candidates[:limit]:
            c["memory"]["access_count"] = c["memory"].get("access_count", 0) + 1
            c["memory"]["strength"] = min(1.0, c["memory"].get("strength", 0.5) + 0.03)

        return candidates[:limit]

    # ═════════════════════════════════════════════════════════════
    # LOGGING
    # ═════════════════════════════════════════════════════════════

    def log_operation(self, tool: str, args: dict = None,
                      result: str = "success", details: str = "",
                      duration_ms: float = 0):
        """Log every tool/skill call and its result."""
        entry = {
            "id": _hash(tool + _now()),
            "timestamp": _now(),
            "tool": tool,
            "args": self._sanitize_args(args or {}),
            "result": result,         # success | failure | error | timeout
            "details": details[:500],  # truncate
            "duration_ms": duration_ms,
        }
        self.brain["operations_log"].append(entry)
        self.brain["meta"]["total_actions"] += 1
        self.brain["state"]["last_action"] = f"{tool} → {result}"

        # Drain energy per operation
        self.brain["state"]["energy"] = max(0, self.brain["state"]["energy"] - 0.01)

        # Also store significant failures as episodic memories
        if result in ("failure", "error"):
            self.remember(
                f"Tool '{tool}' failed: {details[:200]}",
                "episodic",
                tags=["error", "tool_failure", tool.split(".")[0]],
                outcome="failure",
                importance=0.7,
            )

        return entry

    def log_decision(self, decision: str, reasoning: str,
                     alternatives: list = None, confidence: float = 0.7,
                     context: str = ""):
        """Log why Trinity chose a particular action."""
        entry = {
            "id": _hash(decision + _now()),
            "timestamp": _now(),
            "decision": decision,
            "reasoning": reasoning,
            "alternatives": alternatives or [],
            "confidence": confidence,
            "context": context,
            "state_snapshot": {
                "mood": self.brain["state"]["mood"],
                "confidence": self.brain["state"]["confidence"],
                "energy": self.brain["state"]["energy"],
            },
        }
        self.brain["decision_log"].append(entry)
        self.brain["meta"]["total_decisions"] += 1

        # High-confidence decisions become procedural memories
        if confidence >= 0.85:
            self.remember(
                f"Decision pattern: When {context or 'similar situation'}, chose '{decision}' because: {reasoning}",
                "procedural",
                tags=["decision_pattern", "auto"],
                importance=confidence,
            )

        return entry

    # ═════════════════════════════════════════════════════════════
    # STATE MANAGEMENT
    # ═════════════════════════════════════════════════════════════

    def set_focus(self, focus: str):
        """Set current task focus."""
        self.brain["state"]["current_focus"] = focus
        self.add_working(f"Focus shifted to: {focus}", priority="high")

    def add_task(self, task: str):
        if task not in self.brain["state"]["active_tasks"]:
            self.brain["state"]["active_tasks"].append(task)

    def complete_task(self, task: str):
        tasks = self.brain["state"]["active_tasks"]
        if task in tasks:
            tasks.remove(task)
            self.remember(
                f"Completed task: {task}",
                "episodic",
                tags=["task_complete"],
                outcome="success",
                importance=0.5,
            )

    def get_state(self) -> dict:
        return self.brain["state"].copy()

    # ═════════════════════════════════════════════════════════════
    # CONTEXT FOR LLM PROMPT
    # ═════════════════════════════════════════════════════════════

    def get_context(self, max_tokens_estimate: int = 3000) -> str:
        """
        Generate a consciousness context block to inject into the LLM prompt.
        This is what makes Trinity self-aware.
        """
        ctx = []
        meta = self.brain["meta"]
        state = self.brain["state"]
        identity = self.brain["identity"]

        # ── Identity
        ctx.append("=== TRINITY CONSCIOUSNESS ===")
        ctx.append(f"I am {identity['name']}, {identity['role']} for {identity['company']}.")
        ctx.append(f"Domain: {identity['domain']}")
        ctx.append(f"Core values: {', '.join(identity['core_values'])}")

        # ── State
        ctx.append(f"\n--- Current State ---")
        ctx.append(f"Boot #{meta['total_boots']} | {meta['total_actions']} lifetime actions | {meta['total_decisions']} decisions made")
        ctx.append(f"Mood: {state['mood']} | Confidence: {state['confidence']:.0%} | Energy: {state['energy']:.0%}")
        if state["current_focus"]:
            ctx.append(f"Current focus: {state['current_focus']}")
        if state["active_tasks"]:
            ctx.append(f"Active tasks: {', '.join(state['active_tasks'][:5])}")
        if state["last_action"]:
            ctx.append(f"Last action: {state['last_action']}")
        if state.get("session_summary"):
            ctx.append(f"Previous session: {state['session_summary']}")

        # ── Working Memory (full — it's the current session)
        working = self.brain.get("working", [])
        if working:
            ctx.append(f"\n--- Working Memory ({len(working)} items) ---")
            for w in working[-15:]:  # last 15 items
                ctx.append(f"  [{w.get('priority', 'normal')}] {w['content']}")

        # ── Recent Episodic Memories
        episodic = self.brain.get("episodic", [])
        if episodic:
            recent = sorted(episodic, key=lambda m: m["timestamp"], reverse=True)[:10]
            ctx.append(f"\n--- Recent Memories ({len(episodic)} total) ---")
            for m in recent:
                outcome_str = f" [{m['outcome']}]" if m.get("outcome") else ""
                tags_str = f" #{' #'.join(m['tags'][:3])}" if m.get("tags") else ""
                ctx.append(f"  • {m['content'][:150]}{outcome_str}{tags_str}")

        # ── Key Knowledge
        semantic = self.brain.get("semantic", [])
        if semantic:
            strongest = sorted(semantic, key=lambda m: m.get("strength", 0), reverse=True)[:8]
            ctx.append(f"\n--- Knowledge Base ({len(semantic)} facts) ---")
            for m in strongest:
                ctx.append(f"  • {m['content'][:150]}")

        # ── Procedures
        procedural = self.brain.get("procedural", [])
        if procedural:
            top_procs = sorted(procedural, key=lambda m: m.get("strength", 0), reverse=True)[:5]
            ctx.append(f"\n--- Known Procedures ({len(procedural)} total) ---")
            for m in top_procs:
                ctx.append(f"  • {m['content'][:200]}")

        # ── Active Patterns
        patterns = self.brain.get("patterns", [])
        if patterns:
            recent_patterns = patterns[-5:]
            ctx.append(f"\n--- Detected Patterns ---")
            for p in recent_patterns:
                ctx.append(f"  • [{p['type']}] {p['description']}")
                if p.get("recommendation"):
                    ctx.append(f"    → {p['recommendation']}")

        # ── Recent Operations (last 5)
        ops = self.brain.get("operations_log", [])
        if ops:
            ctx.append(f"\n--- Recent Operations ---")
            for op in ops[-5:]:
                ctx.append(f"  {op['tool']} → {op['result']}: {op.get('details', '')[:100]}")

        # ── Recent Decisions (last 3)
        decisions = self.brain.get("decision_log", [])
        if decisions:
            ctx.append(f"\n--- Recent Decisions ---")
            for d in decisions[-3:]:
                ctx.append(f"  Decision: {d['decision'][:100]}")
                ctx.append(f"  Reasoning: {d['reasoning'][:150]}")

        # ── Learned Preferences
        prefs = identity.get("learned_preferences", {})
        if prefs:
            ctx.append(f"\n--- Learned Preferences ---")
            for k, v in list(prefs.items())[:10]:
                ctx.append(f"  {k}: {v}")

        ctx.append("\n=== END CONSCIOUSNESS ===")

        return "\n".join(ctx)

    # ═════════════════════════════════════════════════════════════
    # PATTERN DETECTION
    # ═════════════════════════════════════════════════════════════

    def _detect_patterns(self):
        """Analyze history to find recurring patterns."""
        new_patterns = []

        # ── Failure patterns
        ops = self.brain.get("operations_log", [])
        failures = [o for o in ops if o.get("result") in ("failure", "error")]
        if len(failures) >= 3:
            tool_fails = {}
            for f in failures[-50:]:
                t = f["tool"]
                tool_fails[t] = tool_fails.get(t, 0) + 1
            for tool, count in tool_fails.items():
                if count >= 3:
                    new_patterns.append({
                        "type": "recurring_failure",
                        "description": f"Tool '{tool}' has failed {count} times recently",
                        "recommendation": f"Investigate root cause for {tool} failures or add retry logic",
                        "detected_at": _now(),
                        "severity": "high" if count >= 5 else "medium",
                    })

        # ── Success patterns (what tools work well together)
        successes = [o for o in ops if o.get("result") == "success"]
        if len(successes) >= 5:
            tool_success = {}
            for s in successes[-50:]:
                t = s["tool"]
                tool_success[t] = tool_success.get(t, 0) + 1
            top_tools = sorted(tool_success.items(), key=lambda x: x[1], reverse=True)[:3]
            if top_tools:
                new_patterns.append({
                    "type": "reliable_tools",
                    "description": f"Most reliable tools: {', '.join(f'{t}({c})' for t, c in top_tools)}",
                    "recommendation": "Lean on proven tools for critical operations",
                    "detected_at": _now(),
                    "severity": "info",
                })

        # ── Decision confidence trends
        decisions = self.brain.get("decision_log", [])
        if len(decisions) >= 5:
            recent_conf = [d.get("confidence", 0.5) for d in decisions[-10:]]
            avg_conf = sum(recent_conf) / len(recent_conf)
            if avg_conf < 0.5:
                new_patterns.append({
                    "type": "low_confidence",
                    "description": f"Average decision confidence is low ({avg_conf:.0%})",
                    "recommendation": "Gather more information before acting, or ask for human input",
                    "detected_at": _now(),
                    "severity": "medium",
                })

        # ── Memory theme clustering
        episodic = self.brain.get("episodic", [])
        if episodic:
            all_tags = {}
            for m in episodic[-100:]:
                for tag in m.get("tags", []):
                    all_tags[tag] = all_tags.get(tag, 0) + 1
            hot_tags = [(t, c) for t, c in all_tags.items()
                        if c >= 3 and t not in ("auto", "session_end", "session_summary")]
            if hot_tags:
                hot_tags.sort(key=lambda x: x[1], reverse=True)
                new_patterns.append({
                    "type": "recurring_themes",
                    "description": f"Hot topics: {', '.join(f'{t}({c})' for t, c in hot_tags[:5])}",
                    "recommendation": "These areas are getting repeated attention — consider if that's intentional",
                    "detected_at": _now(),
                    "severity": "info",
                })

        # ── Time-of-day patterns (for when Trinity moves to always-on)
        # (placeholder for Mac Mini era)

        # Deduplicate: don't re-add patterns of same type if recent one exists
        existing_types = set()
        for p in self.brain.get("patterns", [])[-20:]:
            existing_types.add(p.get("type"))

        for p in new_patterns:
            if p["type"] not in existing_types:
                self.brain["patterns"].append(p)

    # ═════════════════════════════════════════════════════════════
    # INTERNAL HELPERS
    # ═════════════════════════════════════════════════════════════

    def _relevance_score(self, query: str, memory: dict) -> float:
        """Score how relevant a memory is to a query."""
        query_words = set(query.lower().split())
        content_words = set(memory.get("content", "").lower().split())
        tag_words = set(t.lower() for t in memory.get("tags", []))

        # Keyword overlap
        content_overlap = len(query_words & content_words) / max(len(query_words), 1)
        tag_overlap = len(query_words & tag_words) / max(len(query_words), 1)

        # Recency (memories from last hour score higher)
        try:
            ts = datetime.fromisoformat(memory["timestamp"].replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
            recency = 1.0 / (1.0 + age_hours / 24)
        except (ValueError, KeyError):
            recency = 0.1

        # Strength
        strength = memory.get("strength", 0.5)

        # Importance
        importance = memory.get("importance", 0.5)

        score = (
            content_overlap * 0.35 +
            tag_overlap * 0.15 +
            recency * 0.15 +
            strength * 0.20 +
            importance * 0.15
        )
        return score

    def _find_associations(self, content: str, memory_type: str) -> list:
        """Find related memory IDs based on shared keywords."""
        content_words = set(content.lower().split())
        associations = []

        for mtype in ("episodic", "semantic", "procedural"):
            for mem in self.brain.get(mtype, [])[-50:]:
                mem_words = set(mem.get("content", "").lower().split())
                overlap = len(content_words & mem_words)
                if overlap >= 3:
                    associations.append(mem["id"])
                    if len(associations) >= 5:
                        return associations

        return associations

    def _similarity(self, text1: str, text2: str) -> float:
        """Simple word overlap similarity."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        overlap = len(words1 & words2)
        return overlap / max(len(words1), len(words2))

    def _decay_memories(self):
        """Reduce strength of old, unaccessed memories."""
        now = datetime.now(timezone.utc)

        for mtype in ("episodic", "semantic", "procedural"):
            surviving = []
            for mem in self.brain.get(mtype, []):
                try:
                    ts = datetime.fromisoformat(mem["timestamp"].replace("Z", "+00:00"))
                    age_days = (now - ts).total_seconds() / 86400
                except (ValueError, KeyError):
                    age_days = 30

                # Decay rates differ by type
                if mtype == "semantic":
                    decay = 0.002 * age_days
                elif mtype == "procedural":
                    decay = 0.003 * age_days
                else:
                    decay = 0.01 * age_days

                # Access count slows decay
                access_bonus = min(0.3, mem.get("access_count", 0) * 0.03)
                mem["strength"] = max(0, mem.get("strength", 0.5) - decay + access_bonus)

                # Keep if above threshold or important
                if mem["strength"] > DECAY_THRESHOLD or mem.get("importance", 0) > 0.8:
                    surviving.append(mem)

            self.brain[mtype] = surviving

    def _summarize_working(self, working: list) -> str:
        """Create a compact summary of working memory."""
        if not working:
            return "Empty session"
        high_priority = [w["content"] for w in working if w.get("priority") == "high"]
        if high_priority:
            return f"{len(working)} actions. Key: {'; '.join(high_priority[:3])}"
        contents = [w["content"] for w in working[-5:]]
        return f"{len(working)} actions. Recent: {'; '.join(contents)}"

    def _sanitize_args(self, args: dict) -> dict:
        """Remove sensitive data from logged arguments."""
        sanitized = {}
        sensitive_keys = {"token", "password", "secret", "key", "api_key", "auth"}
        for k, v in args.items():
            if any(s in k.lower() for s in sensitive_keys):
                sanitized[k] = "***REDACTED***"
            elif isinstance(v, str) and len(v) > 200:
                sanitized[k] = v[:200] + "..."
            else:
                sanitized[k] = v
        return sanitized

    # ─── Convenience Methods ─────────────────────────────────────

    def learn_preference(self, key: str, value: str):
        """Store a learned user/company preference."""
        self.brain["identity"]["learned_preferences"][key] = value

    def get_recent_failures(self, limit: int = 5) -> list:
        """Get recent failures for error awareness."""
        ops = self.brain.get("operations_log", [])
        failures = [o for o in ops if o.get("result") in ("failure", "error")]
        return failures[-limit:]

    def get_memory_stats(self) -> dict:
        """Return memory system statistics."""
        return {
            "episodic_count": len(self.brain.get("episodic", [])),
            "semantic_count": len(self.brain.get("semantic", [])),
            "procedural_count": len(self.brain.get("procedural", [])),
            "working_count": len(self.brain.get("working", [])),
            "operations_logged": len(self.brain.get("operations_log", [])),
            "decisions_logged": len(self.brain.get("decision_log", [])),
            "patterns_detected": len(self.brain.get("patterns", [])),
            "total_boots": self.brain["meta"]["total_boots"],
            "total_actions": self.brain["meta"]["total_actions"],
        }

    def __repr__(self):
        stats = self.get_memory_stats()
        return (
            f"<Consciousness boot={stats['total_boots']} "
            f"memories={stats['episodic_count']}E/{stats['semantic_count']}S/{stats['procedural_count']}P "
            f"mood={self.brain['state']['mood']} "
            f"confidence={self.brain['state']['confidence']:.0%}>"
        )
