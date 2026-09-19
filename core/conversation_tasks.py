"""Task execution/follow-up service used by ConversationService.

Conversation prompt assembly and model interaction stay in ``conversation.py``.
This service owns the separate concern of handling a model-requested skill task,
including status output, capability execution, missing-tool proposal routing,
and the one-shot success/failure follow-up prompt.
"""
from __future__ import annotations

import os
import re
from typing import Any

from core.execution import TaskExecutionResult
from core.models import ChatMessage


class ConversationTaskService:
    """Execute skill-call directives without growing ConversationService."""

    STATUS_MESSAGES = {
        "github": "Reading from GitHub ({tool})...",
        "web": "Checking website ({tool})...",
        "memory": "Reading memory ({tool})...",
        "knowledge": "Searching local knowledge ({tool})...",
        "search": "Searching ({tool})...",
        "code": "Reviewing code ({tool})...",
        "business": "Checking business data ({tool})...",
        "debug": "Debugging ({tool})...",
        "computer": "Using local computer ({tool})...",
    }

    def __init__(self, host: Any) -> None:
        self.host = host


    def process_skill_need_directives(self, content: str, question: str) -> None:
        """Route model-declared capability gaps into the governed proposal flow."""
        for line in content.split("\n"):
            if "TRINITY_SKILL_NEED:" not in line or "|" not in line:
                continue
            parts = line.split("TRINITY_SKILL_NEED:", 1)[1].split("|", 1)
            if len(parts) < 2:
                continue
            skill = parts[0].strip().lower().replace(" ", "_").replace("-", "_")
            reason = parts[1].strip()
            if (
                skill
                and skill.replace("_", "").isalpha()
                and not os.path.exists(f"skills/{skill}_skill.py")
            ):
                print(f"[SkillNeed] Trinity wants new skill: {skill}")
                evolution = getattr(self.host, "skill_evolution", None)
                if evolution is not None:
                    evolution.propose_new_skill(skill, reason, question)

    def _status(self, content: str) -> None:
        mcp_match = re.search(r"MCP_CALL\s*:\s*([\w-]+)\.([\w.:/-]+)", content, re.IGNORECASE)
        if mcp_match:
            self.host.respond(f"Using MCP {mcp_match.group(1)} ({mcp_match.group(2)})...")
            return
        match = re.search(r"SKILL_CALL\s*:\s*(\w+)\.(\w+)", content, re.IGNORECASE)
        if not match:
            return
        skill = match.group(1).lower()
        tool = match.group(2).replace("_", " ")
        template = self.STATUS_MESSAGES.get(skill, "Working on it ({tool})...")
        self.host.respond(template.format(tool=tool))

    def _execute(self, content: str) -> TaskExecutionResult:
        if "MCP_CALL" in content.upper():
            return self.host.mcp_execution.process_call(content)
        results, rendered = self.host.skills.process_skill_call(content)
        return TaskExecutionResult(tuple(results or ()), rendered)

    def _propose_unknown_tool(self, execution: TaskExecutionResult, llm: Any) -> None:
        missing = execution.unknown_tool
        if not missing:
            return
        skill = missing.get("skill", "")
        tool = missing.get("tool", "")
        if not tool:
            error = str(missing.get("error", ""))
            tool = error.split(":", 1)[-1].strip() if ":" in error else ""
        if skill and tool:
            evolution = getattr(self.host, "skill_evolution", None)
            if evolution is not None:
                evolution.propose_missing_tool(skill, tool, {}, llm)

    def _followup_messages(
        self,
        *,
        system_prompt: str,
        question: str,
        content: str,
        instruction: str,
    ) -> list[ChatMessage]:
        messages = [ChatMessage("system", system_prompt)]
        for turn in self.host._conversation_history[-6:]:
            role = "user" if turn["role"] == "user" else "assistant"
            messages.append(ChatMessage(role, turn["content"]))
        messages.extend(
            [
                ChatMessage("user", question),
                ChatMessage("assistant", content),
                ChatMessage("user", instruction),
            ]
        )
        return messages

    def handle(
        self,
        *,
        content: str,
        question: str,
        system_prompt: str,
        llm: Any,
    ) -> str | None:
        """Handle one model-requested task; return final text when consumed."""
        is_mcp = "MCP_CALL" in content.upper()
        if "SKILL_CALL" not in content.upper() and not is_mcp:
            return None

        stuck, stuck_message = self.host.response_processor.check_skill_call_loop(content)
        if stuck:
            self.host.consciousness.remember(
                f"Broke out of skill call loop: {stuck_message}",
                "episodic",
                tags=["loop_break", "skill_call", "error"],
                outcome="failure",
                importance=0.7,
            )
            clean = content.split("SKILL_CALL")[0].strip()
            return f"{clean}\n\n{stuck_message}" if clean else stuck_message

        fixed_content = content if is_mcp else self.host.response_processor.fix_skill_call_format(content)
        self._status(fixed_content)
        execution = self._execute(fixed_content)
        if not execution.has_results:
            return None

        if not is_mcp:
            self._propose_unknown_tool(execution, llm)
        result_text = str(list(execution.results))

        first = execution.results[0] if execution.results else None
        if is_mcp and isinstance(first, dict) and first.get("needs_approval"):
            return (
                f"MCP action {first.get('server')}.{first.get('tool')} needs your approval. "
                "Reply YES to approve or NO to cancel."
            )

        if execution.failed:
            self.host.response_processor.record_skill_failure(fixed_content)
            self.host.consciousness.remember(
                f"Skill call failed after format fix: {result_text[:200]}",
                "episodic",
                tags=["skill_call", "failed", "format_fix"],
                outcome="failure",
                importance=0.6,
            )
            try:
                followup = self._followup_messages(
                    system_prompt=system_prompt,
                    question=question,
                    content=content,
                    instruction=(
                        f"That skill call failed: {result_text[:300]}\n\n"
                        "Do NOT retry the same call. Tell David honestly what happened "
                        "and suggest what to do next. Be direct and helpful."
                    ),
                )
                response = self.host._invoke_with_failover(followup, preferred_llm=llm)
                final = self.host.response_processor.clean_response(response.content)
                self.host.conversation._save_to_history(question, final)
                return final
            except Exception as exc:
                self.host.consciousness.remember(
                    f"Retry LLM call failed: {type(exc).__name__}: {str(exc)[:150]}",
                    "episodic",
                    tags=["error", "llm", "retry"],
                    outcome="failure",
                    importance=0.7,
                )
                message = (
                    "I hit an issue getting that information and couldn't recover. "
                    f"Error: {str(exc)[:150]}\n\nPlease try asking again."
                )
                self.host.conversation._save_to_history(question, message)
                return message

        self.host.consciousness.remember(
            f"LLM triggered skill call. Results: {result_text[:200]}",
            "episodic",
            tags=["skill_call", "llm_triggered"],
            outcome="success",
            importance=0.5,
        )
        try:
            followup = self._followup_messages(
                system_prompt=system_prompt,
                question=question,
                content=content,
                instruction=(
                    f"Skill result:\n{result_text[:2000]}\n\n"
                    "Now respond to David using these results. Be direct and useful. "
                    "Do NOT make another skill call. Just answer with the data you have."
                ),
            )
            response = self.host._invoke_with_failover(followup, preferred_llm=llm)
            final = self.host.response_processor.clean_response(response.content)
            self.host.conversation._save_to_history(question, final)
            return final
        except Exception as exc:
            self.host.consciousness.remember(
                f"Follow-up LLM call failed: {type(exc).__name__}: {str(exc)[:150]}",
                "episodic",
                tags=["error", "llm", "followup"],
                outcome="failure",
                importance=0.7,
            )
            message = (
                "I got the data but had trouble summarizing it. "
                f"Error: {str(exc)[:150]}\n\nCould you ask me again?"
            )
            self.host.conversation._save_to_history(question, message)
            return message
