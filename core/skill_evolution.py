"""Approval-gated self-improvement for Trinity skills."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.models import ChatMessage


@dataclass(frozen=True)
class SkillProposal:
    id: str
    kind: str
    skill_name: str
    path: str
    content: str
    reason: str
    tool_name: str | None = None


class SkillEvolutionService:
    """Draft skill improvements, but never write code without explicit approval."""

    def __init__(self, host: Any, skills_dir: str | Path = "skills") -> None:
        self.host = host
        self.skills_dir = Path(skills_dir)
        self._pending: dict[str, SkillProposal] = {}
        self._proposal_actions: dict[str, tuple[str, str | None]] = {}

    @staticmethod
    def _strip_code_fences(code: str) -> str:
        code = code.strip()
        if code.startswith("```"):
            code = code.split("\n", 1)[-1]
            if "```" in code:
                code = code.rsplit("```", 1)[0]
        return code.strip()

    def _audit(self, status: str, action: str, action_id=None, *, approved=False, **kwargs):
        audit = getattr(self.host, "audit", None)
        if audit is None:
            return action_id
        return audit.record(
            actor_type="system",
            action=action,
            status=status,
            action_id=action_id,
            permission="confirm",
            approved=approved,
            **kwargs,
        )

    @staticmethod
    def _validate_python(code: str, path: Path, required: tuple[str, ...]) -> str | None:
        missing = next((item for item in required if item not in code), None)
        if missing:
            return f"Generated code is missing '{missing}'"
        try:
            compile(code, str(path), "exec")
        except SyntaxError as exc:
            return f"Generated code has invalid Python syntax: {exc.msg} (line {exc.lineno})"
        return None

    def _notify(self, message: str) -> None:
        notifier = getattr(self.host, "notify", None)
        if callable(notifier):
            notifier(message, category="approval")
            return
        sender = getattr(self.host, "send_telegram", None)
        if callable(sender):
            sender(message)

    def _store_proposal(
        self,
        *,
        kind: str,
        skill_name: str,
        path: Path,
        content: str,
        reason: str,
        tool_name: str | None,
        action: str,
        action_id: str | None,
    ) -> SkillProposal:
        proposal = SkillProposal(
            id=uuid4().hex[:12],
            kind=kind,
            skill_name=skill_name,
            path=str(path).replace("\\", "/"),
            content=content,
            reason=reason,
            tool_name=tool_name,
        )
        self._pending[proposal.id] = proposal
        self._proposal_actions[proposal.id] = (action, action_id)
        self._audit(
            "approval_required",
            action,
            action_id=action_id,
            params={"proposal_id": proposal.id, "path": proposal.path},
        )
        self._notify(
            f"I drafted a Trinity skill improvement ({proposal.id}): {reason}. "
            "Say YES to apply it or NO to cancel it."
        )
        return proposal

    def get_pending_changes(self) -> dict[str, dict]:
        """Return proposal metadata without exposing generated code to status surfaces."""
        return {
            proposal_id: {
                "id": proposal.id,
                "kind": proposal.kind,
                "skill_name": proposal.skill_name,
                "tool_name": proposal.tool_name,
                "path": proposal.path,
                "reason": proposal.reason,
            }
            for proposal_id, proposal in self._pending.items()
        }

    def cancel(self, proposal_id: str) -> bool:
        proposal = self._pending.pop(proposal_id, None)
        action, action_id = self._proposal_actions.pop(proposal_id, ("self_improve", None))
        if proposal is None:
            return False
        self._audit("denied", action, action_id=action_id, error="User cancelled proposal")
        return True

    def _persist_to_github(self, path: Path, content: str, reason: str) -> None:
        """Persist only after the same user approval that applied the local change."""
        try:
            result = self.host.skills.execute(
                "github",
                "self_commit_improvement",
                {
                    "repo": "trinity-ai",
                    "path": str(path).replace("\\", "/"),
                    "content": content,
                    "reason": reason,
                },
                approved=True,
            )
            if isinstance(result, dict) and not result.get("success", True):
                print(f"[SkillEvolution] GitHub persistence skipped: {result.get('error')}")
        except Exception as exc:
            print(f"[SkillEvolution] GitHub persistence error (non-fatal): {exc}")

    def approve(self, proposal_id: str) -> tuple[bool, str]:
        proposal = self._pending.get(proposal_id)
        if proposal is None:
            return False, "Skill improvement proposal not found"

        action, action_id = self._proposal_actions.get(proposal_id, ("self_improve", None))
        path = Path(proposal.path)
        try:
            self._audit("approved", action, action_id=action_id, approved=True)
            self._audit(
                "started",
                action,
                action_id=action_id,
                approved=True,
                params={"proposal_id": proposal.id, "path": proposal.path},
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(proposal.content, encoding="utf-8")

            if proposal.kind == "extend_tool":
                self.host.skills.reload_skill(proposal.skill_name)
                loaded_ok = self.host.skills.get_skill(proposal.skill_name) is not None
            else:
                loaded_ok = self.host.skills.get_skill(proposal.skill_name) is not None
            if not loaded_ok:
                raise RuntimeError(f"Updated skill '{proposal.skill_name}' failed to load")

            self._persist_to_github(path, proposal.content, proposal.reason)
            consciousness = getattr(self.host, "consciousness", None)
            if consciousness is not None:
                consciousness.remember(
                    f"Approved skill improvement: {proposal.reason}",
                    "episodic",
                    tags=["skill_build", "approved", proposal.skill_name],
                    outcome="success",
                    importance=0.8,
                )
            self._audit(
                "completed",
                action,
                action_id=action_id,
                approved=True,
                result={"proposal_id": proposal.id, "path": proposal.path},
            )
            self._pending.pop(proposal_id, None)
            self._proposal_actions.pop(proposal_id, None)
            return True, f"Applied approved skill improvement: {proposal.reason}"
        except Exception as exc:
            self._audit("failed", action, action_id=action_id, approved=True, error=str(exc))
            return False, str(exc)

    def implement_missing_tool(self, skill_name: str, tool_name: str, params: dict, llm) -> bool:
        """Draft a missing-tool patch and wait for approval; never auto-write/retry."""
        skill_path = self.skills_dir / f"{skill_name}_skill.py"
        if not skill_path.exists():
            print(f"[SkillEvolution] Skill file not found: {skill_path}")
            return False

        action = f"self_improve.{skill_name}.{tool_name}"
        action_id = self._audit("requested", action, params={"path": str(skill_path)})
        try:
            current_code = skill_path.read_text(encoding="utf-8")
            param_list = list(params.keys()) if params else []
            param_desc = f"called with params {param_list}" if param_list else "called with no params"
            prompt = (
                f"The tool '{tool_name}' does not exist yet in the '{skill_name}' skill.\n"
                f"It was {param_desc}.\n\nHere is the COMPLETE current skill file:\n\n"
                f"```python\n{current_code}\n```\n\n"
                f"Write the COMPLETE updated Python file with '{tool_name}' fully implemented.\n"
                "Add it to get_tools(), execute() and as a real method. Leave existing behavior unchanged.\n"
                "Every method must return a success/error dict. Return only raw Python."
            )
            response = self.host._invoke_with_failover(
                [
                    ChatMessage("system", "Draft an extension to this Trinity Python skill. Return raw Python only."),
                    ChatMessage("user", prompt),
                ],
                preferred_llm=llm,
            )
            new_code = self._strip_code_fences(response.content)
            error = self._validate_python(new_code, skill_path, (f"def {tool_name}", "class "))
            if error:
                self._audit("failed", action, action_id=action_id, error=error)
                return False

            self._store_proposal(
                kind="extend_tool",
                skill_name=skill_name,
                tool_name=tool_name,
                path=skill_path,
                content=new_code,
                reason=f"Add missing tool {skill_name}.{tool_name}",
                action=action,
                action_id=action_id,
            )
            return False
        except Exception as exc:
            self._audit("failed", action, action_id=action_id, error=str(exc))
            return False

    def build_new_skill(self, skill_name: str, description: str, context: str = ""):
        """Draft a brand-new skill and wait for approval before writing it."""
        skill_name = skill_name.strip().lower().replace(" ", "_").replace("-", "_")
        if not skill_name.replace("_", "").isalpha():
            return False, f"Invalid skill name '{skill_name}' — letters and underscores only."
        skill_path = self.skills_dir / f"{skill_name}_skill.py"
        if skill_path.exists():
            return False, f"'{skill_name}' already exists — use the existing skill or implement a missing tool."

        llm = self.host.llm
        if not llm:
            return False, "LLM not available"

        action = f"self_improve.create_skill.{skill_name}"
        action_id = self._audit("requested", action, params={"path": str(skill_path)})
        try:
            example_path = self.skills_dir / "web_skill.py"
            example_code = example_path.read_text(encoding="utf-8") if example_path.exists() else ""
            class_name = "".join(word.capitalize() for word in skill_name.split("_")) + "Skill"
            prompt = (
                "Draft a complete, working Trinity skill.\n\n"
                f"Skill name: {skill_name}\nClass name: {class_name}\nPurpose: {description}\nContext: {context}\n\n"
                f"Reference skill:\n```python\n{example_code}\n```\n\n"
                "Requirements: exact class/name, get_tools(), execute(), at least 3 practical methods, "
                "success/error dicts, stdlib + requests only, no TODOs. Return raw Python only."
            )
            response = self.host._invoke_with_failover(
                [
                    ChatMessage("system", "Draft a Trinity Python skill. Return raw Python only."),
                    ChatMessage("user", prompt),
                ],
                preferred_llm=llm,
            )
            new_code = self._strip_code_fences(response.content)
            error = self._validate_python(
                new_code,
                skill_path,
                (f"class {class_name}", "def get_tools", "def execute"),
            )
            if error:
                self._audit("failed", action, action_id=action_id, error=error)
                return False, error

            proposal = self._store_proposal(
                kind="new_skill",
                skill_name=skill_name,
                tool_name=None,
                path=skill_path,
                content=new_code,
                reason=f"Create new skill {skill_name}: {description}",
                action=action,
                action_id=action_id,
            )
            return False, f"Drafted skill '{skill_name}' as proposal {proposal.id}; approval required"
        except Exception as exc:
            self._audit("failed", action, action_id=action_id, error=str(exc))
            return False, str(exc)
