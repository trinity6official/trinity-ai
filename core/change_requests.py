"""GitHub change-request staging for Trinity."""
from __future__ import annotations

from typing import Any


class ChangeRequestService:
    """Parse LLM change blocks and stage them through the permission-aware skill layer."""

    def __init__(self, host: Any) -> None:
        self.host = host

    def process(self, response: str, language: str = "english") -> str:
        try:
            repo, file_path, reason, new_content = self._parse(response)
            if not repo or not file_path or not new_content:
                return "Could not process change. Please try again."

            if not self.host.skills.get_skill("github"):
                return "GitHub skill not available."

            self.host.consciousness.log_decision(
                decision=f"Prepare change to {repo}/{file_path}",
                reasoning=reason,
                alternatives=["Skip change", "Modify different file"],
                confidence=0.75,
                context="GitHub change request from LLM",
            )

            existing = self.host.execute_skill_conscious(
                "github", "read_file",
                args={"repo": repo, "path": file_path},
                execute_fn=lambda: self.host.skills.execute(
                    "github", "read_file", {"repo": repo, "path": file_path}
                ),
            )

            if existing.get("success") and len(new_content) < len(existing["content"]) * 0.5:
                tool = "add_to_file"
                params = {
                    "repo": repo, "path": file_path, "content": new_content,
                    "position": "end", "reason": reason,
                }
            elif existing.get("success"):
                tool = "update_file"
                params = {"repo": repo, "path": file_path, "content": new_content, "reason": reason}
            else:
                tool = "create_file"
                params = {"repo": repo, "path": file_path, "content": new_content, "reason": reason}

            # GitHub write tools stage pending changes. Their metadata explicitly marks
            # them as approval-gated; SkillManager allows staging but not committing.
            result = self.host.skills.execute("github", tool, params)
            if isinstance(result, dict) and result.get("needs_approval"):
                return result.get("error", "Approval is required before this change can be staged.")
            if isinstance(result, dict) and not result.get("success", True) and result.get("error"):
                return f"Error: {result['error']}"

            self.host.consciousness.remember(
                f"Prepared change for {repo}/{file_path}: {reason}",
                "episodic",
                tags=["github", "change_prepared"],
                outcome="success",
                importance=0.6,
            )
            self.host.consciousness.save()
            return result.get("message", "Change prepared.") if isinstance(result, dict) else "Change prepared."
        except Exception as exc:
            self.host.consciousness.remember(
                f"Change request failed: {str(exc)[:200]}",
                "episodic",
                tags=["github", "change_failed", "error"],
                outcome="failure",
                importance=0.7,
            )
            return f"Error: {exc}"

    @staticmethod
    def _parse(response: str) -> tuple[str, str, str, str]:
        repo = file_path = reason = ""
        content_lines: list[str] = []
        in_content = False
        for line in response.split("\n"):
            if line.startswith("repo:"):
                repo = line.replace("repo:", "", 1).strip()
            elif line.startswith("file:"):
                file_path = line.replace("file:", "", 1).strip()
            elif line.startswith("reason:"):
                reason = line.replace("reason:", "", 1).strip()
            elif line == "content:":
                in_content = True
            elif line == "END_TRINITY_CHANGE":
                in_content = False
            elif in_content:
                content_lines.append(line)
        return repo, file_path, reason, "\n".join(content_lines)
