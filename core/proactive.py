"""Proactive reasoning helpers for Trinity."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SkillRequest:
    name: str
    reason: str


@dataclass(frozen=True)
class ProactiveDecision:
    silent: bool
    message: str = ""
    skill_requests: tuple[SkillRequest, ...] = field(default_factory=tuple)


class ProactiveEngine:
    SILENT_TOKEN = "TRINITY_SILENT"
    SKILL_TOKEN = "TRINITY_SKILL_NEED:"

    def build_prompt(
        self,
        *,
        now: str,
        consciousness_context: str,
        company_context: str,
        awareness_context: str = "",
    ) -> str:
        awareness = f"\nLive awareness:\n{awareness_context}\n" if awareness_context else ""
        return (
            f"You are Trinity, David's personal AI company manager. It is {now} IST.\n\n"
            f"Your state and memories:\n{consciousness_context}\n\n"
            f"Company context:\n{company_context}\n"
            f"{awareness}\n"
            "This is a proactive evaluation. Only speak if there is a concrete risk, "
            "opportunity, deadline, useful new information, or capability gap.\n"
            "Do not send generic check-ins or repeat known information. Keep it short.\n"
            "If a genuinely useful new skill is needed, add: "
            "TRINITY_SKILL_NEED: skill_name | reason\n"
            "If there is nothing useful to say, output only: TRINITY_SILENT"
        )

    def parse(self, text: str) -> ProactiveDecision:
        raw = (text or "").strip()
        if not raw or self.SILENT_TOKEN in raw:
            return ProactiveDecision(silent=True)

        requests = []
        visible_lines = []
        for line in raw.splitlines():
            if self.SKILL_TOKEN in line and "|" in line:
                payload = line.split(self.SKILL_TOKEN, 1)[1]
                name, reason = payload.split("|", 1)
                normalized = name.strip().lower().replace(" ", "_").replace("-", "_")
                if normalized and normalized.replace("_", "").isalpha():
                    requests.append(SkillRequest(normalized, reason.strip()))
                continue
            visible_lines.append(line)

        message = "\n".join(visible_lines).strip()
        return ProactiveDecision(
            silent=not bool(message) and not bool(requests),
            message=message,
            skill_requests=tuple(requests),
        )
