"""Response cleanup and skill-call loop protection for Trinity."""
from __future__ import annotations

import re
from typing import MutableMapping


class ResponseProcessor:
    """Normalize model output and track repeated failing tool calls."""

    def __init__(self, failure_counts: MutableMapping[str, int] | None = None) -> None:
        self.failure_counts = failure_counts if failure_counts is not None else {}

    def bind_failure_counts(self, failure_counts: MutableMapping[str, int]) -> None:
        self.failure_counts = failure_counts

    def fix_skill_call_format(self, content: str) -> str:
        available_skills = ["github", "web", "memory", "search", "code", "business", "calculator", "debug", "computer"]

        def fix_bracket_calls(match):
            inner = re.sub(r"\s*result\s*$", "", match.group(1), flags=re.IGNORECASE).strip()
            if "." in inner:
                skill, method = inner.split(".", 1)
                return f"[{skill.strip().lower()}.{method.strip()}]"
            return match.group(0)

        content = re.sub(
            r"\[([A-Za-z_]+\s*\.\s*[A-Za-z_]+(?:\s+result)?)\]",
            fix_bracket_calls,
            content,
        )

        def fix_skill_call_line(match):
            return f"{match.group(1)}{match.group(2).lower()}.{match.group(3)}"

        content = re.sub(
            r"(SKILL_CALL\s*:?\s*)([A-Za-z_]+)\s*\.\s*(\w+)",
            fix_skill_call_line,
            content,
            flags=re.IGNORECASE,
        )

        for skill in available_skills:
            pattern = re.compile(r"\b(" + skill + r")\s*\.\s*(\w+)", re.IGNORECASE)
            content = pattern.sub(lambda m, s=skill: f"{s}.{m.group(2)}", content)
        return content

    @staticmethod
    def _calls(content: str):
        return re.findall(
            r"(?:SKILL_CALL\s*:?\s*)?(\w+)\s*\.\s*(\w+)",
            content,
            re.IGNORECASE,
        )

    def check_skill_call_loop(self, content: str):
        for skill, method in self._calls(content):
            key = f"{skill.lower()}.{method.lower()}"
            count = self.failure_counts.get(key, 0)
            if count >= 2:
                return True, (
                    f"I've tried {key} {count} times and it keeps failing. "
                    "Let me be honest - this skill call is not working right now. "
                    "I'll note this issue and we can try a different approach."
                )
        return False, ""

    def record_skill_failure(self, content: str) -> None:
        for skill, method in self._calls(content):
            key = f"{skill.lower()}.{method.lower()}"
            self.failure_counts[key] = self.failure_counts.get(key, 0) + 1

    def reset_skill_failures(self) -> None:
        self.failure_counts.clear()

    def clean_response(self, content: str) -> str:
        content = re.sub(
            r"\[\s*\.?\s*(?:\w+\.)?(?:\w+)?\s*result\s*\]\s*",
            "",
            content,
            flags=re.IGNORECASE,
        )
        content = re.sub(r"\{'success':\s*(True|False).*?\}", "", content, flags=re.DOTALL)
        content = re.sub(
            r"\[\s*\{'success':\s*(True|False).*?\}\s*\]",
            "",
            content,
            flags=re.DOTALL,
        )
        content = re.sub(
            r"SKILL_CALL\s*:\s*\w+\.\w+\s*(?:\n(?:\w+:.*(?:\n|$))*|\Z)",
            "",
            content,
            flags=re.IGNORECASE,
        )

        orphan_params = {
            "path:", "repo:", "count:", "url:", "query:", "branch:", "sha:", "commit_sha:"
        }
        cleaned_lines = []
        for line in content.split("\n"):
            stripped = line.strip().lower()
            if any(stripped.startswith(param) and len(stripped.split()) <= 3 for param in orphan_params):
                continue
            cleaned_lines.append(line)
        content = "\n".join(cleaned_lines)
        content = re.sub(r"\*\*(.+?)\*\*", r"\1", content)
        content = re.sub(r"\*(.+?)\*", r"\1", content)
        content = re.sub(r"\n{3,}", "\n\n", content)
        return content.strip()
