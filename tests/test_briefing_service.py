from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from core.briefing import BriefingService


def test_morning_briefing_builds_message_and_updates_day_count():
    skills = MagicMock()
    skills.execute.return_value = {"website_live": True}
    github = MagicMock(); github.get_workflow_runs.return_value = {"runs": []}
    skills.get_skill.return_value = github
    memory = SimpleNamespace(
        brain={"company": {"days_building": 4}},
        get_days_alive=lambda: 3,
        add_daily_log=MagicMock(), save=MagicMock(),
    )
    consciousness = MagicMock()
    sent = []
    host = SimpleNamespace(
        skills=skills, memory=memory, consciousness=consciousness,
        github_context_cache="", respond=sent.append,
        status_service=SimpleNamespace(health_summary=lambda: {"website_live": True}),
    )
    host.execute_skill_conscious = lambda skill, method, args, execute_fn: execute_fn()
    service = BriefingService(host, now=lambda: datetime(2026, 9, 15))
    service.github_context = MagicMock(return_value="repos healthy")
    service.business_summary = MagicMock(return_value={
        "revenue": 10, "total_clients": 2, "next_milestone": "grow", "alerts": []
    })
    text = service.deliver_morning()
    assert "September 15 2026" in text
    assert "Revenue: 10 INR" in text
    assert sent == [text]
    assert memory.brain["company"]["days_building"] == 5
