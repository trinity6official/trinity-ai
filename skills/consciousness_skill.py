"""
Trinity AI — Consciousness Skill
==================================
Fits into Trinity's skills/ directory pattern.
Exposes memory operations as skill commands that the LLM brain can invoke.

Usage in skill_manager.py:
    from skills.consciousness_skill import ConsciousnessSkill
    consciousness = ConsciousnessSkill(trinity.consciousness)

The LLM can call:
    ACTION: consciousness.remember(what="deployed v2.1", tags=["deploy"])
    ACTION: consciousness.recall(query="deployment failures")
    ACTION: consciousness.learn(fact="API rate limit is 100/min")
    ACTION: consciousness.reflect()
    ACTION: consciousness.status()
"""

from core.consciousness import Consciousness


class ConsciousnessSkill:
    """Skill interface for Trinity's consciousness system."""

    def __init__(self, consciousness: Consciousness):
        self.c = consciousness
        self.name = "consciousness"
        self.description = "Memory and self-awareness operations"
        self.commands = {
            "remember": self.remember,
            "recall": self.recall,
            "learn": self.learn,
            "learn_procedure": self.learn_procedure,
            "reflect": self.reflect,
            "status": self.status,
            "set_focus": self.set_focus,
            "add_task": self.add_task,
            "complete_task": self.complete_task,
            "search_decisions": self.search_decisions,
            "search_operations": self.search_operations,
        }

    def remember(self, what: str, tags: list = None,
                 outcome: str = None, importance: float = 0.5) -> dict:
        """Store an episodic memory — something that happened."""
        mem = self.c.remember(what, "episodic", tags=tags,
                              outcome=outcome, importance=importance)
        self.c.save()
        return {"stored": True, "id": mem["id"], "type": "episodic"}

    def recall(self, query: str, limit: int = 5,
               memory_types: list = None) -> list:
        """Search memories by relevance to a query."""
        results = self.c.recall(query, memory_types=memory_types, limit=limit)
        return [
            {
                "content": r["memory"]["content"],
                "type": r["type"],
                "score": round(r["score"], 3),
                "tags": r["memory"].get("tags", []),
                "outcome": r["memory"].get("outcome"),
                "timestamp": r["memory"].get("timestamp"),
                "strength": round(r["memory"].get("strength", 0), 2),
            }
            for r in results
        ]

    def learn(self, fact: str, tags: list = None,
              confidence: float = 0.8) -> dict:
        """Store a semantic memory — a fact or piece of knowledge."""
        mem = self.c.learn(fact, tags=tags, confidence=confidence)
        self.c.save()
        return {"learned": True, "id": mem["id"], "type": "semantic"}

    def learn_procedure(self, name: str, steps: list,
                        context: str = "", tags: list = None) -> dict:
        """Store a procedural memory — how to do something."""
        mem = self.c.learn_procedure(name, steps, context=context, tags=tags)
        self.c.save()
        return {"learned": True, "id": mem["id"], "type": "procedural"}

    def reflect(self) -> dict:
        """Trinity reflects on its current state and recent activity."""
        state = self.c.get_state()
        stats = self.c.get_memory_stats()
        recent_failures = self.c.get_recent_failures(limit=3)
        patterns = self.c.brain.get("patterns", [])[-3:]

        reflection = {
            "state": state,
            "stats": stats,
            "recent_failures": [
                {"tool": f["tool"], "details": f["details"][:100]}
                for f in recent_failures
            ],
            "active_patterns": [
                {"type": p["type"], "description": p["description"],
                 "recommendation": p.get("recommendation", "")}
                for p in patterns
            ],
            "assessment": self._self_assess(state, stats, recent_failures),
        }
        return reflection

    def status(self) -> dict:
        """Quick status check."""
        state = self.c.get_state()
        stats = self.c.get_memory_stats()
        return {
            "mood": state["mood"],
            "confidence": f"{state['confidence']:.0%}",
            "energy": f"{state['energy']:.0%}",
            "focus": state.get("current_focus"),
            "active_tasks": state.get("active_tasks", []),
            "memories": f"{stats['episodic_count']}E / {stats['semantic_count']}S / {stats['procedural_count']}P",
            "lifetime_actions": stats["total_actions"],
            "boot_number": stats["total_boots"],
        }

    def set_focus(self, focus: str) -> dict:
        self.c.set_focus(focus)
        self.c.save()
        return {"focus_set": focus}

    def add_task(self, task: str) -> dict:
        self.c.add_task(task)
        self.c.save()
        return {"task_added": task}

    def complete_task(self, task: str) -> dict:
        self.c.complete_task(task)
        self.c.save()
        return {"task_completed": task}

    def search_decisions(self, query: str, limit: int = 5) -> list:
        """Search past decisions."""
        decisions = self.c.brain.get("decision_log", [])
        query_words = set(query.lower().split())
        scored = []
        for d in decisions:
            text = f"{d['decision']} {d['reasoning']} {d.get('context', '')}".lower()
            overlap = sum(1 for w in query_words if w in text)
            if overlap > 0:
                scored.append((overlap, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "decision": d["decision"],
                "reasoning": d["reasoning"][:200],
                "confidence": d["confidence"],
                "timestamp": d["timestamp"],
            }
            for _, d in scored[:limit]
        ]

    def search_operations(self, tool: str = None,
                          result: str = None, limit: int = 10) -> list:
        """Search past operations by tool name or result status."""
        ops = self.c.brain.get("operations_log", [])
        filtered = ops
        if tool:
            filtered = [o for o in filtered if tool.lower() in o["tool"].lower()]
        if result:
            filtered = [o for o in filtered if o["result"] == result]
        return [
            {
                "tool": o["tool"],
                "result": o["result"],
                "details": o.get("details", "")[:100],
                "duration_ms": o.get("duration_ms", 0),
                "timestamp": o["timestamp"],
            }
            for o in filtered[-limit:]
        ]

    def _self_assess(self, state, stats, failures) -> str:
        """Generate a self-assessment string."""
        parts = []

        if state["confidence"] >= 0.8:
            parts.append("Operating with high confidence.")
        elif state["confidence"] <= 0.4:
            parts.append("Confidence is low — consider gathering more data before acting.")

        if state["energy"] <= 0.3:
            parts.append("Energy is low — prioritize critical tasks only.")

        if len(failures) >= 3:
            parts.append(f"Warning: {len(failures)} recent failures detected.")

        if stats["episodic_count"] > 400:
            parts.append("Memory is getting full — older memories will be pruned.")

        if not parts:
            parts.append("All systems nominal.")

        return " ".join(parts)
        
