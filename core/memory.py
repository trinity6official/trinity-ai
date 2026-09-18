"""Trinity's structured personal-memory service.

The SQLite :class:`core.memory_store.MemoryStore` is the authoritative local
owner for structured profile/business state, durable memories and persistent
conversation history. ``memory/trinity_brain.json`` is supported only as a
one-time migration source for older installations.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from core.memory_store import MemoryStore


class MemoryService:
    """Single runtime boundary for Trinity's personal and business memory."""

    STATE_NAMESPACE = "personal_profile_v1"
    DEFAULT_LEGACY_BRAIN = "memory/trinity_brain.json"

    def __init__(
        self,
        brain_file: str | Path = DEFAULT_LEGACY_BRAIN,
        memory_root: str | Path | None = None,
        db_path: str | Path | None = None,
        *,
        store: MemoryStore | None = None,
    ) -> None:
        # ``brain_file`` is intentionally retained as a compatibility/migration
        # input.  Active writes go to MemoryStore state_documents.
        if store is not None and str(brain_file) == self.DEFAULT_LEGACY_BRAIN and memory_root is None:
            brain_file = store.root / "trinity_brain.json"
        self.brain_file = str(brain_file)
        root = Path(memory_root) if memory_root else Path(self.brain_file).parent
        if str(root) in ("", "."):
            root = Path("memory") if self.brain_file == self.DEFAULT_LEGACY_BRAIN else Path(".")
        self.store = store or MemoryStore(root=root, db_path=db_path)
        self.brain = self.load()

    # ------------------------------------------------------------------
    # Authoritative structured state + legacy import
    # ------------------------------------------------------------------

    def _load_legacy_json(self) -> dict[str, Any]:
        path = Path(self.brain_file)
        try:
            with path.open("r", encoding="utf-8") as handle:
                brain = json.load(handle)
            if isinstance(brain, dict):
                print("Trinity legacy memory loaded for migration")
                return brain
            print("Memory migration source is not a JSON object; starting fresh.")
            return {}
        except FileNotFoundError:
            return {}
        except Exception as exc:
            print(f"Memory migration source error: {exc}")
            return {}

    def load(self) -> dict[str, Any]:
        """Load authoritative structured state, importing legacy JSON once."""
        stored = self.store.load_state(self.STATE_NAMESPACE)
        if stored is not None:
            return stored

        brain = self._load_legacy_json()
        if brain:
            try:
                self.store.import_legacy_brain(brain)
            except Exception as exc:
                print(f"Memory Vault migration warning: {exc}")
        # Persist even an empty state document so a stale legacy file can never
        # reclaim ownership after the first PR #4 startup.
        self.store.save_state(self.STATE_NAMESPACE, brain)
        return brain

    def save(self) -> None:
        """Persist the current structured state to the authoritative store."""
        try:
            self.store.save_state(self.STATE_NAMESPACE, self.brain)
        except Exception as exc:
            print(f"Memory save error: {exc}")

    def export_legacy_json(self, path: str | Path | None = None) -> Path:
        """Explicitly export a compatibility snapshot; never used for ownership."""
        target = Path(path or self.brain_file)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.brain, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return target

    # ------------------------------------------------------------------
    # Structured profile/business state
    # ------------------------------------------------------------------

    def update_last_wakeup(self) -> None:
        """Record when Trinity last woke up."""
        if "identity" not in self.brain:
            self.brain["identity"] = {
                "name": "Trinity",
                "version": "1.0",
                "born": "2026-02-22",
                "days_alive": 0,
                "last_wakeup": None,
                "core_mission": "David's wellbeing and financial growth",
            }
        self.brain["identity"]["last_wakeup"] = datetime.now().isoformat()
        self.brain["identity"]["days_alive"] = self.brain["identity"].get("days_alive", 0) + 1
        self.save()

    def update_david_last_seen(self) -> None:
        """Record when David last interacted."""
        self.brain.setdefault("david", {})["last_seen"] = datetime.now().isoformat()
        self.save()

    def update_david(self, key: str, value: Any) -> None:
        david = self.brain.setdefault("david", {})
        david[str(key)] = value
        david["last_updated"] = datetime.now().isoformat()
        self.save()

    def update_company(self, key: str, value: Any) -> None:
        self.brain.setdefault("company", {})[str(key)] = value
        self.save()

    def add_client(self, name: str, company: str, status: str, notes: str | None = None) -> dict[str, Any]:
        clients = self.brain.setdefault("company", {}).setdefault("clients", [])
        client = {
            "name": name,
            "company": company,
            "status": status,
            "notes": notes or "",
            "added_date": datetime.now().isoformat(),
        }
        clients.append(client)
        self.save()
        return client

    def update_revenue(self, amount: float, source: str) -> float:
        company = self.brain.setdefault("company", {})
        new_total = float(company.get("revenue", 0)) + float(amount)
        company["revenue"] = new_total
        self.add_daily_log(f"Revenue update: +{amount} from {source}. Total: {new_total}")
        self.save()
        return new_total

    def add_daily_log(self, log_entry: str) -> None:
        """Add an activity entry to structured state and the Markdown vault."""
        logs = self.brain.setdefault("history", {}).setdefault("daily_logs", [])
        entry = {
            "timestamp": datetime.now().isoformat(),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "entry": log_entry,
        }
        logs.append(entry)
        self.store.add_daily_entry(log_entry, entry["timestamp"])
        self.save()

    def add_alert(self, alert_type: str, message: str, severity: str = "medium") -> None:
        history = self.brain.setdefault("history", {})
        alerts_sent = history.setdefault("alerts_sent", [])
        active = self.brain.setdefault("monitoring", {}).setdefault("alerts_active", [])
        alert = {
            "timestamp": datetime.now().isoformat(),
            "type": alert_type,
            "message": message,
            "severity": severity,
        }
        alerts_sent.append(alert)
        active.append(alert)
        self.save()

    def clear_alert(self, alert_type: str) -> None:
        if "monitoring" not in self.brain:
            return
        self.brain["monitoring"]["alerts_active"] = [
            alert
            for alert in self.brain["monitoring"].get("alerts_active", [])
            if alert.get("type") != alert_type
        ]
        self.save()

    def update_monitoring_status(self, key: str, value: Any) -> None:
        monitoring = self.brain.setdefault("monitoring", {})
        monitoring[key] = value
        monitoring["last_check"] = datetime.now().isoformat()
        self.save()

    def record_decision(self, decision: str, outcome: str) -> None:
        history = self.brain.setdefault("history", {})
        entries = history.setdefault("decisions_made", [])
        entry = {
            "timestamp": datetime.now().isoformat(),
            "decision": decision,
            "outcome": outcome,
        }
        entries.append(entry)
        self.store.remember(
            f"{decision} — Outcome: {outcome}",
            kind="decision",
            category="trinity",
            importance=0.85,
            metadata=entry,
        )
        self.save()

    def learn(self, category: str, insight: str) -> None:
        knowledge = self.brain.setdefault(
            "knowledge",
            {
                "what_works": [],
                "what_doesnt": [],
                "patterns_noticed": [],
                "improvements_made": [],
            },
        )
        knowledge.setdefault("what_works", [])
        knowledge.setdefault("what_doesnt", [])
        knowledge.setdefault("patterns_noticed", [])
        knowledge.setdefault("improvements_made", [])

        if category == "what_works":
            if insight not in knowledge["what_works"]:
                knowledge["what_works"].append(insight)
        elif category == "what_doesnt":
            if insight not in knowledge["what_doesnt"]:
                knowledge["what_doesnt"].append(insight)
        elif category == "pattern":
            knowledge["patterns_noticed"].append(
                {"timestamp": datetime.now().isoformat(), "pattern": insight}
            )
        elif category == "improvement":
            knowledge["improvements_made"].append(
                {"timestamp": datetime.now().isoformat(), "improvement": insight}
            )

        learning = self.brain.setdefault("learning", {"total_interactions": 0})
        learning["total_interactions"] = learning.get("total_interactions", 0) + 1
        self.save()

    def update_wellbeing(self, score: float, note: str | None = None) -> None:
        david = self.brain.setdefault("david", {})
        david["wellbeing_score"] = score
        if note:
            david.setdefault("notes", []).append(
                {"timestamp": datetime.now().isoformat(), "note": note}
            )
        self.save()

    def pin_memory(self, key: str, value: Any) -> dict[str, Any]:
        """Persist an explicitly pinned fact inside authoritative profile state."""
        pinned = self.brain.setdefault("pinned", {})
        pinned[str(key)] = {
            "value": value,
            "pinned_at": datetime.now().isoformat(),
        }
        self.save()
        return pinned[str(key)]

    def get_pinned(self) -> dict[str, Any]:
        return self.brain.get("pinned", {})

    # ------------------------------------------------------------------
    # Durable/searchable memory
    # ------------------------------------------------------------------

    def remember(
        self,
        content: str,
        kind: str = "semantic",
        category: str = "general",
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        return self.store.remember(
            content,
            kind=kind,
            category=category,
            importance=importance,
            metadata=metadata,
        )

    def recall(self, query: str, limit: int = 10, kind: str | None = None):
        return self.store.search(query, limit=limit, kind=kind)

    def recent_memories(self, limit: int = 10):
        return self.store.recent(limit=limit)

    # ------------------------------------------------------------------
    # Compatibility reads
    # ------------------------------------------------------------------

    def add_conversation(self, role: str, message: str) -> None:
        """Compatibility-only rolling buffer; completed turns use MemoryStore.

        Runtime conversation persistence is owned by ConversationMemoryPipeline.
        This method remains for older callers but is not used by the main
        MessageService after PR #4.
        """
        history = self.brain.setdefault("history", {})
        conversations = history.setdefault("conversations", [])
        conversations.append(
            {
                "timestamp": datetime.now().isoformat(),
                "role": role,
                "message": message,
            }
        )
        if len(conversations) > 100:
            history["conversations"] = conversations[-100:]
        self.save()

    def get_recent_logs(self, days: int = 7):
        logs = self.brain.get("history", {}).get("daily_logs", [])
        return logs[-days * 10 :] if logs else []

    def get_active_alerts(self):
        return self.brain.get("monitoring", {}).get("alerts_active", [])

    def get_company_summary(self):
        company = self.brain.get("company", {})
        return {
            "name": company.get("name"),
            "phase": company.get("current_phase"),
            "next_milestone": company.get("next_milestone"),
            "revenue": company.get("revenue", 0),
            "clients": len(company.get("clients", [])),
            "days_building": company.get("days_building", 0),
        }

    def get_david_summary(self):
        david = self.brain.get("david", {})
        return {
            "wellbeing_score": david.get("wellbeing_score", 100),
            "last_seen": david.get("last_seen"),
            "stress_indicators": david.get("stress_indicators", []),
        }

    def get_days_alive(self) -> int:
        return self.brain.get("identity", {}).get("days_alive", 0)

    def get_full_context(self) -> str:
        """Get profile/business context for prompting; repository data is live."""
        return json.dumps(
            {
                "david": self.brain.get("david", {}),
                "company": self.brain.get("company", {}),
                "knowledge": self.brain.get("knowledge", {}),
                "monitoring": self.brain.get("monitoring", {}),
                "recent_logs": self.get_recent_logs(3),
            },
            indent=2,
        )


# Compatibility import for existing integrations/tests.  The runtime uses the
# canonical MemoryService name; this alias carries no second owner or storage.
TrinityMemory = MemoryService

__all__ = ["MemoryService", "TrinityMemory"]
