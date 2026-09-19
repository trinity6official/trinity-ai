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
from uuid import uuid4

from core.memory_store import MemoryStore


class MemoryService:
    """Single runtime boundary for Trinity's personal and business memory."""

    STATE_NAMESPACE = "personal_profile_v1"
    DEFAULT_LEGACY_BRAIN = "memory/trinity_brain.json"
    OBJECTIVE_STATUSES = frozenset({
        "candidate", "active", "paused", "blocked", "completed", "abandoned", "superseded"
    })
    TERMINAL_OBJECTIVE_STATUSES = frozenset({"completed", "abandoned", "superseded"})

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
    # Objectives and current focus
    # ------------------------------------------------------------------

    def _objective_state(self) -> dict[str, Any]:
        # Structured objective state remains owned by MemoryService.
        state = self.brain.setdefault(
            "objectives",
            {"current_focus_id": None, "items": {}},
        )
        if not isinstance(state, dict):
            raise ValueError("Objective state is corrupted: expected an object")
        items = state.setdefault("items", {})
        if not isinstance(items, dict):
            raise ValueError("Objective state is corrupted: items must be an object")
        state.setdefault("current_focus_id", None)
        return state

    @staticmethod
    def _objective_score(value: float, field: str) -> float:
        score = float(value)
        if not 0.0 <= score <= 1.0:
            raise ValueError(f"{field} must be between 0.0 and 1.0")
        return score

    @staticmethod
    def _objective_criteria(value) -> list[str]:
        if value is None:
            return []
        values = [value] if isinstance(value, str) else list(value)
        return [str(item).strip() for item in values if str(item).strip()]

    def create_objective(
        self,
        title: str,
        *,
        success_criteria=None,
        importance: float = 0.5,
        priority: float = 0.5,
        deadline: str | None = None,
        parent_id: str | None = None,
        make_focus: bool = False,
    ) -> dict[str, Any]:
        # Persist explicit intent only; this never starts work.
        title = str(title or "").strip()
        if not title:
            raise ValueError("Objective title is required")
        state = self._objective_state()
        if parent_id is not None and str(parent_id) not in state["items"]:
            raise KeyError(f"Parent objective not found: {parent_id}")

        now = datetime.now().isoformat()
        objective_id = uuid4().hex[:12]
        objective = {
            "id": objective_id,
            "title": title,
            "status": "active",
            "importance": self._objective_score(importance, "importance"),
            "priority": self._objective_score(priority, "priority"),
            "success_criteria": self._objective_criteria(success_criteria),
            "progress": 0.0,
            "deadline": str(deadline) if deadline else None,
            "parent_id": str(parent_id) if parent_id is not None else None,
            "blocked_reason": None,
            "superseded_by": None,
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
            "status_history": [{"status": "active", "at": now, "reason": "created"}],
        }
        state["items"][objective_id] = objective
        if make_focus:
            state["current_focus_id"] = objective_id
        self.save()
        return dict(objective)

    def get_objective(self, objective_id: str) -> dict[str, Any] | None:
        objective = self._objective_state()["items"].get(str(objective_id))
        return dict(objective) if isinstance(objective, dict) else None

    def list_objectives(self, *, status: str | None = None) -> list[dict[str, Any]]:
        if status is not None:
            status = str(status).strip().lower()
            if status not in self.OBJECTIVE_STATUSES:
                raise ValueError(f"Unknown objective status: {status}")
        items = [
            dict(item)
            for item in self._objective_state()["items"].values()
            if isinstance(item, dict) and (status is None or item.get("status") == status)
        ]
        return sorted(
            items,
            key=lambda item: (
                float(item.get("priority", 0.0)),
                float(item.get("importance", 0.0)),
                str(item.get("updated_at", "")),
            ),
            reverse=True,
        )

    def set_current_focus(self, objective_id: str | None) -> dict[str, Any] | None:
        # Focus is attention, not a replacement for objective lifecycle state.
        state = self._objective_state()
        if objective_id is None:
            state["current_focus_id"] = None
            self.save()
            return None

        objective = state["items"].get(str(objective_id))
        if not isinstance(objective, dict):
            raise KeyError(f"Objective not found: {objective_id}")
        if objective.get("status") not in {"active", "blocked"}:
            raise ValueError(
                "Current focus must be an active or blocked objective; "
                "change its status explicitly first"
            )
        state["current_focus_id"] = str(objective_id)
        self.save()
        return dict(objective)

    def get_current_focus(self) -> dict[str, Any] | None:
        state = self._objective_state()
        focus_id = state.get("current_focus_id")
        if not focus_id:
            return None
        objective = state["items"].get(str(focus_id))
        return dict(objective) if isinstance(objective, dict) else None

    def set_objective_status(
        self,
        objective_id: str,
        status: str,
        *,
        reason: str | None = None,
        blocked_reason: str | None = None,
        superseded_by: str | None = None,
    ) -> dict[str, Any]:
        # Lifecycle transitions retain history; changing focus never deletes goals.
        status = str(status or "").strip().lower()
        if status not in self.OBJECTIVE_STATUSES:
            raise ValueError(f"Unknown objective status: {status}")
        state = self._objective_state()
        objective = state["items"].get(str(objective_id))
        if not isinstance(objective, dict):
            raise KeyError(f"Objective not found: {objective_id}")

        if status == "superseded":
            if not superseded_by or str(superseded_by) == str(objective_id):
                raise ValueError(
                    "superseded objectives require a different replacement objective"
                )
            if str(superseded_by) not in state["items"]:
                raise KeyError(f"Replacement objective not found: {superseded_by}")

        now = datetime.now().isoformat()
        objective["status"] = status
        objective["updated_at"] = now
        objective["blocked_reason"] = (
            str(blocked_reason).strip()
            if status == "blocked" and blocked_reason
            else None
        )
        objective["superseded_by"] = (
            str(superseded_by) if status == "superseded" else None
        )
        objective["completed_at"] = now if status == "completed" else None
        if status == "completed":
            objective["progress"] = 1.0
        objective.setdefault("status_history", []).append(
            {
                "status": status,
                "at": now,
                "reason": str(reason or "").strip() or None,
            }
        )

        if status in self.TERMINAL_OBJECTIVE_STATUSES or status == "paused":
            if state.get("current_focus_id") == str(objective_id):
                state["current_focus_id"] = None
        self.save()
        return dict(objective)

    def update_objective_progress(
        self,
        objective_id: str,
        progress: float,
        *,
        blocked_reason: str | None = None,
    ) -> dict[str, Any]:
        # Progress is evidence state; reaching 1.0 does not silently complete a goal.
        state = self._objective_state()
        objective = state["items"].get(str(objective_id))
        if not isinstance(objective, dict):
            raise KeyError(f"Objective not found: {objective_id}")
        objective["progress"] = self._objective_score(progress, "progress")
        objective["updated_at"] = datetime.now().isoformat()
        if blocked_reason is not None:
            objective["blocked_reason"] = str(blocked_reason).strip() or None
        self.save()
        return dict(objective)

    def update_objective_priority(
        self,
        objective_id: str,
        priority: float,
    ) -> dict[str, Any]:
        # Priority may change without rewriting long-term importance.
        state = self._objective_state()
        objective = state["items"].get(str(objective_id))
        if not isinstance(objective, dict):
            raise KeyError(f"Objective not found: {objective_id}")
        objective["priority"] = self._objective_score(priority, "priority")
        objective["updated_at"] = datetime.now().isoformat()
        self.save()
        return dict(objective)

    def get_objective_context(self, *, limit: int = 5) -> dict[str, Any]:
        # Keep prompt context bounded and exclude completed/abandoned/superseded history.
        focus = self.get_current_focus()
        focus_id = focus.get("id") if focus else None
        active = [
            item
            for item in self.list_objectives()
            if item.get("status") not in self.TERMINAL_OBJECTIVE_STATUSES
            and item.get("id") != focus_id
        ][: max(0, int(limit))]
        return {
            "current_focus": focus,
            "other_open_objectives": active,
        }

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
                "objectives": self.get_objective_context(limit=5),
                "recent_logs": self.get_recent_logs(3),
            },
            indent=2,
        )


# Compatibility import for existing integrations/tests.  The runtime uses the
# canonical MemoryService name; this alias carries no second owner or storage.
TrinityMemory = MemoryService

__all__ = ["MemoryService", "TrinityMemory"]
